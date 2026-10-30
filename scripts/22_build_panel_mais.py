"""Étape 22 : panel maïs grain irrigué / non irrigué 2000-2025 (Q1, phase 0 bis).

Usage : uv run python scripts/22_build_panel_mais.py
Entrées :
  data/raw/agreste_saa_ancienne/FDS_DEVELOPPE_2.zip           SAA « anciennes séries » 2000-2009 (non recalées)
  data/interim/saa_cop_departements_long.parquet               SAA séries longues 2010-2025 (codes 14 et 15)
  data/processed/weather_dep_month_maize.parquet / _area       météo pondérée par le maïs (RPG MIS) / par la surface
  data/processed/vigieau_dep_ete.parquet                       restrictions d'eau juillet-août 2012-2025
Sortie : data/processed/panel_mais_long.parquet (format long : une ligne par département × année × modalité)

Raccord des sources : 2000-2009 depuis les anciennes séries, 2010-2025 depuis les séries longues. Sur 2010-2020,
les deux versions sont identiques pour 94-95 % des paires (écart médian nul).
Population : surfaces moyennes 2010-2012 irrigué ET non irrigué ≥ 1000 ha chacune (38 départements, phase 6).
Échantillon principal : statut qualité 1 du maïs irrigué (statut publié en 2025, appliqué à toute la période).
"""

import importlib.util
import io
import zipfile

import numpy as np
import pandas as pd

from atlas.download import ROOT
from atlas.weather import harvest_year_windows

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "09_build_panel.py")
panel_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panel_mod)
MOD = {"Maïs grain irrigué": "irrigue", "Maïs grain non irrigué": "non_irrigue"}
IND = {"Rendement": "rendement_q_ha", "Superficie développée": "surface_ha"}


def old_series() -> pd.DataFrame:
    z = zipfile.ZipFile(RAW / "agreste_saa_ancienne" / "FDS_DEVELOPPE_2.zip")
    parts = []
    for y in range(2000, 2010):
        d = pd.read_csv(io.BytesIO(z.read(f"FDS_DEVELOPPE_{y}.csv")), sep=";", dtype=str)
        d = d[d["N306_LIB"].isin(MOD) & d["N027_LIB"].isin(IND) & (d["DEP"] != "...")]
        parts.append(d)
    d = pd.concat(parts)
    d["valeur"] = pd.to_numeric(d["VALEUR"], errors="coerce")
    out = d.pivot_table(index=["DEP", "ANNREF", "N306_LIB"], columns="N027_LIB", values="valeur").reset_index()
    out = out.rename(columns={"DEP": "dep_code", "ANNREF": "annee", "N306_LIB": "modalite", **IND})
    out["annee"] = out["annee"].astype(int)
    out["modalite"] = out["modalite"].map(MOD)
    return out.assign(source="SAA_ancienne_serie")[["dep_code", "annee", "modalite", "rendement_q_ha", "surface_ha", "source"]]


def new_series(saa: pd.DataFrame) -> pd.DataFrame:
    m = saa[saa["culture_code"].isin(["14", "15"]) & saa["metropole"]].copy()
    m["modalite"] = m["culture_code"].map({"14": "irrigue", "15": "non_irrigue"})
    return m.assign(source="SAA_series_longues")[["dep_code", "annee", "modalite", "rendement_q_ha", "surface_ha", "source"]]


def main() -> None:
    saa = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    new = new_series(saa)
    ref = (new[new["annee"].between(2010, 2012)].groupby(["dep_code", "modalite"])["surface_ha"].mean()
           .unstack())
    pop = ref[(ref["irrigue"] >= 1000) & (ref["non_irrigue"] >= 1000)].index
    statut = saa[(saa["culture_code"] == "14")].drop_duplicates("dep_code").set_index("dep_code")["statut_qualite"]

    y = pd.concat([old_series(), new], ignore_index=True)
    n_all = len(y)
    y = y[y["dep_code"].isin(pop)]
    ctl = [("rendements (2000-2025, deux modalités) -> population de 38 départements", n_all, len(y))]
    # Valeurs inexploitables : rendement manquant ou nul (surface nulle), ex. Jura 2016 et 2018 en irrigué.
    bad = y["rendement_q_ha"].isna() | (y["rendement_q_ha"] <= 0)
    ctl.append(("retrait des rendements manquants ou nuls", len(y), int(len(y) - bad.sum())))
    removed = y[bad][["dep_code", "annee", "modalite"]].values.tolist()
    y = y[~bad].copy()
    y["log_rendement"] = np.log(y["rendement_q_ha"])
    y["surface_ref_ha"] = y["dep_code"].map(ref.sum(axis=1))          # maïs grain total 2010-2012 (fixe)
    y["statut_irrigue"] = y["dep_code"].map(statut)
    y["echantillon_principal"] = y["statut_irrigue"] == "1"

    meteo = []
    for w in ["maize", "area"]:
        dm = pd.read_parquet(PROC / f"weather_dep_month_{w}.parquet")
        h = harvest_year_windows(dm, range(2000, 2026), windows={"ja": [(0, 7), (0, 8)], "juillet": [(0, 7)]})
        for win in ["ja", "juillet"]:
            h[f"gdd_0_32_{win}"] = h[f"dd_0_{win}"] - h[f"dd_32_{win}"]
        cols = [f"{v}_{win}" for win in ["ja", "juillet"] for v in ["dd_32", "dd_30", "gdd_0_32", "swi", "prec", "etp", "hot_30"]]
        h = h[["dep_code", "annee"] + cols]
        if w == "area":
            h = h.rename(columns={c: f"{c}_surf" for c in cols})
        meteo.append(h)
    out = y.merge(meteo[0], on=["dep_code", "annee"], how="left", validate="many_to_one")
    out = out.merge(meteo[1], on=["dep_code", "annee"], how="left", validate="many_to_one")
    vig = pd.read_parquet(PROC / "vigieau_dep_ete.parquet")
    out = out.merge(vig, on=["dep_code", "annee"], how="left", validate="many_to_one")
    out = out.merge(panel_mod.centroids(), on="dep_code", how="left", validate="many_to_one")
    ctl.append(("jointure météo (maïs, surface) + VigiEau + centroïdes", len(y), len(out)))

    if out.duplicated(["dep_code", "annee", "modalite"]).any():
        raise RuntimeError("doublons (dep_code, annee, modalite)")
    if not (out["dd_32_ja"].notna().all() and out["dd_32_ja_surf"].notna().all() and out["lat_centroide"].notna().all()):
        raise RuntimeError("chaleur ou centroïde manquant dans le panel maïs")
    out = out.sort_values(["dep_code", "annee", "modalite"]).reset_index(drop=True)
    out.to_parquet(PROC / "panel_mais_long.parquet", index=False)

    print(pd.DataFrame(ctl, columns=["étape", "lignes avant", "lignes après"]).to_string(index=False))
    print("observations retirées (rendement manquant ou nul) :", removed)
    wide = out.pivot_table(index=["dep_code", "annee"], columns="modalite", values="log_rendement").dropna()
    print(f"département-années avec les deux modalités : {len(wide)} ; départements : {out.dep_code.nunique()} "
          f"(dont {out.loc[out.echantillon_principal, 'dep_code'].nunique()} en statut 1) ; "
          f"années : {out.annee.min()}-{out.annee.max()}")
    print("VigiEau disponible (2012-2025) :", int(out["jours_crise_ja"].notna().sum()), "lignes")


if __name__ == "__main__":
    main()
