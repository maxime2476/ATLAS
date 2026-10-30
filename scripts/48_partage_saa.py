"""Étape 48 : repérage des rendements calculés à partir de la production dans le partage irrigué / non irrigué de la SAA.

Usage : uv run python scripts/48_partage_saa.py   (après scripts/22_build_panel_mais.py)
Entrées :
  data/raw/agreste_saa_ancienne/FDS_DEVELOPPE_2.zip           SAA « anciennes séries » 2000-2009
  data/interim/saa_cop_departements_long.parquet               SAA séries longues 2010-2025 (codes 14 et 15)
  data/processed/panel_mais_long.parquet                       paires du panel maïs (population de 38 départements)
Sortie : data/processed/maize_partage_saa.parquet (une ligne par paire département × année du panel)

Règle : un rendement est dit « dérivé » si
|production − rendement × surface| ≥ 0,5 q, c'est-à-dire si la production publiée n'est pas le produit du rendement
par la surface. Le rendement est alors calculé à partir de la production (par exemple comme résidu du total), au lieu
d'être la valeur saisie. Un rendement dérivé peut tomber par hasard sur un entier et passer pour saisi : la part des
rendements dérivés est donc un minimum.
"""

import io
import zipfile

import pandas as pd

from atlas.download import ROOT

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
MOD = {"Maïs grain irrigué": "irrigue", "Maïs grain non irrigué": "non_irrigue"}
IND = {"Production (volume)": "production_q", "Rendement": "rendement_q_ha", "Superficie développée": "surface_ha"}


def derived(production: pd.Series, rendement: pd.Series, surface: pd.Series) -> pd.Series:
    """Vrai si la production publiée n'est pas le produit du rendement par la surface (à 0,5 q près)."""
    return (production - rendement * surface).abs() >= 0.5


def old_series() -> pd.DataFrame:
    z = zipfile.ZipFile(RAW / "agreste_saa_ancienne" / "FDS_DEVELOPPE_2.zip")
    parts = []
    for y in range(2000, 2010):
        d = pd.read_csv(io.BytesIO(z.read(f"FDS_DEVELOPPE_{y}.csv")), sep=";", dtype=str)
        parts.append(d[d["N306_LIB"].isin(MOD) & d["N027_LIB"].isin(IND) & (d["DEP"] != "...")])
    d = pd.concat(parts)
    d["valeur"] = pd.to_numeric(d["VALEUR"], errors="coerce")
    out = d.pivot_table(index=["DEP", "ANNREF", "N306_LIB"], columns="N027_LIB", values="valeur").reset_index()
    out = out.rename(columns={"DEP": "dep_code", "ANNREF": "annee", "N306_LIB": "modalite", **IND})
    out["annee"] = out["annee"].astype(int)
    out["modalite"] = out["modalite"].map(MOD)
    return out[["dep_code", "annee", "modalite", *IND.values()]]


def new_series() -> pd.DataFrame:
    s = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    s = s[s["culture_code"].isin(["14", "15"]) & s["metropole"] & (s["annee"] >= 2010)].copy()
    s["modalite"] = s["culture_code"].map({"14": "irrigue", "15": "non_irrigue"})
    return s[["dep_code", "annee", "modalite", *IND.values()]]


def main() -> None:
    saa = pd.concat([old_series(), new_series()], ignore_index=True)
    saa["derive"] = derived(saa["production_q"], saa["rendement_q_ha"], saa["surface_ha"])
    wide = saa.pivot_table(index=["dep_code", "annee"], columns="modalite",
                           values=["production_q", "rendement_q_ha", "surface_ha", "derive"], aggfunc="first")
    wide.columns = [f"{v}_{m}" for v, m in wide.columns]
    wide = wide.reset_index()

    # Paires du panel (mêmes départements-années que le modèle) : contrôle que rendements et surfaces sont les mêmes.
    m = pd.read_parquet(PROC / "panel_mais_long.parquet")
    pairs = m.pivot_table(index=["dep_code", "annee"], columns="modalite", values=["rendement_q_ha", "surface_ha"])
    pairs.columns = [f"{v}_{mo}_panel" for v, mo in pairs.columns]
    pairs = pairs.dropna().reset_index()
    pairs = pairs.merge(m.drop_duplicates(["dep_code", "annee"])[["dep_code", "annee", "echantillon_principal"]],
                        on=["dep_code", "annee"], validate="one_to_one")
    out = pairs.merge(wide, on=["dep_code", "annee"], how="left", validate="one_to_one")
    print(f"paires du panel : {len(pairs)} ; sans production dans la SAA : {out['production_q_non_irrigue'].isna().sum()}")
    for mo in ["irrigue", "non_irrigue"]:
        for v in ["rendement_q_ha", "surface_ha"]:
            gap = (out[f"{v}_{mo}"] - out[f"{v}_{mo}_panel"]).abs().max()
            if gap > 1e-9:
                raise SystemExit(f"{v} {mo} différent du panel (écart max {gap})")
    out = out.drop(columns=[c for c in out.columns if c.endswith("_panel")])
    for mo in ["irrigue", "non_irrigue"]:
        out[f"derive_{mo}"] = out[f"derive_{mo}"].astype(bool)
    out.to_parquet(PROC / "maize_partage_saa.parquet", index=False)

    princ = out[out["echantillon_principal"]].assign(periode=lambda d: d["annee"].le(2009).map({True: "2000-2009", False: "2010-2025"}))
    print(princ.groupby("periode")[["derive_irrigue", "derive_non_irrigue"]].agg(["mean", "sum", "size"]).round(3).to_string())


if __name__ == "__main__":
    main()
