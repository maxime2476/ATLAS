"""Étape 16 : données des extensions exploratoires (spécification de la phase 6).

Usage : uv run python scripts/16_phase6_build.py
Sorties :
  data/processed/prix_ble_tendre.parquet          prix du blé tendre 2010-2025 (€/q), IPPAP raccordé à Eurostat
  reports/tables/phase6_pertes_valeur.csv         pertes nationales de blé tendre d'hiver en volume et en valeur
  data/processed/panel_mais.parquet               écart maïs irrigué / non irrigué et météo juillet-août
"""

import importlib.util
import json
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from atlas.download import ROOT
from atlas.weather import harvest_year_windows

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "09_build_panel.py")
panel_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panel_mod)


def read_ippap() -> pd.Series:
    root = ET.parse(RAW / "prix" / "insee_ippap_ble_tendre_010776425.xml").getroot()
    obs = {int(o.attrib["TIME_PERIOD"]): float(o.attrib["OBS_VALUE"]) for o in root.iter() if o.tag.endswith("Obs")}
    return pd.Series(obs).sort_index()


def read_eurostat() -> pd.Series:
    with open(RAW / "prix" / "eurostat_apri_ap_crpouta_FR_ble_tendre.json") as f:
        d = json.load(f)
    idx = {v: int(k) for k, v in d["dimension"]["time"]["category"]["index"].items()}
    return pd.Series({idx[int(k)]: v for k, v in d["value"].items()}).sort_index()


def prices() -> pd.DataFrame:
    ippap, eur = read_ippap(), read_eurostat()
    ratio = (eur / ippap).loc[2012:2016]
    # Contrôle du raccord fixé dans la spécification : rapport stable sur 2012-2016.
    if not (ratio.max() - ratio.min() < 0.002):
        raise RuntimeError(f"rapport Eurostat / IPPAP instable sur 2012-2016 : {ratio}")
    k = ratio.mean()
    out = pd.DataFrame({"annee": range(2010, 2026)})
    out["ippap_base2020"] = out["annee"].map(ippap)
    out["prix_eur_q"] = k * out["ippap_base2020"]
    out["prix_eurostat_eur_q"] = out["annee"].map(eur)
    print(f"raccord IPPAP -> €/q : {k:.4f} (2012-2016, écart max {ratio.max() - ratio.min():.4f}) ; "
          f"Eurostat 2010-2011 / IPPAP : {(eur / ippap).loc[2010:2011].round(3).to_dict()} (non utilisé)")
    return out


def wheat_losses(price: pd.DataFrame) -> pd.DataFrame:
    saa = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    w = saa[(saa["culture_code"] == "01") & saa["metropole"] & (saa["surface_ha"] > 0)].copy()
    rows = []
    for t in range(2010, 2026):
        # Normale descriptive : moyenne de toutes les AUTRES années 2010-2025, futures et provisoire 2025
        # comprises, sans tendance. Ce n'est pas une prévision disponible l'année t.
        normal = w[w["annee"] != t].groupby("dep_code")["rendement_q_ha"].mean()
        cur = w[w["annee"] == t].assign(normal=lambda d: d["dep_code"].map(normal)).dropna(subset=["normal"])
        p = float(price.set_index("annee").loc[t, "prix_eur_q"])
        vol = ((cur["normal"] - cur["rendement_q_ha"]) * cur["surface_ha"]).sum()   # q
        prod = (cur["rendement_q_ha"] * cur["surface_ha"]).sum()
        rows.append({"annee": t, "production_Mq": prod / 1e6, "perte_volume_Mq": vol / 1e6,
                     "perte_pct_production_normale": 100 * vol / (prod + vol), "prix_eur_q": p,
                     "perte_valeur_Meur": vol * p / 1e6, "valeur_production_Meur": prod * p / 1e6})
    return pd.DataFrame(rows)


def maize_panel() -> pd.DataFrame:
    saa = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    m = saa[saa["culture_code"].isin(["14", "15"]) & saa["metropole"]]
    wide = m.pivot_table(index=["dep_code", "annee"], columns="culture_code",
                         values=["rendement_q_ha", "surface_ha"]).reset_index()
    # 14 = maïs grain irrigué, 15 = maïs grain non irrigué (SAA) : renommage par (mesure, code), pas par position.
    names = {("dep_code", ""): "dep_code", ("annee", ""): "annee",
             ("rendement_q_ha", "14"): "rdt_irrigue", ("rendement_q_ha", "15"): "rdt_non_irrigue",
             ("surface_ha", "14"): "surf_irrigue", ("surface_ha", "15"): "surf_non_irrigue"}
    wide.columns = [names[c] for c in wide.columns]
    ref = wide[wide["annee"].between(2010, 2012)].groupby("dep_code")[["surf_irrigue", "surf_non_irrigue"]].mean()
    pop = ref[(ref["surf_irrigue"] >= 1000) & (ref["surf_non_irrigue"] >= 1000)].index
    wide = wide[wide["dep_code"].isin(pop)].copy()
    wide["surface_ref_ha"] = wide["dep_code"].map(ref.sum(axis=1))
    statut = m[m["culture_code"] == "14"].drop_duplicates("dep_code").set_index("dep_code")["statut_qualite"]
    wide["statut_irrigue"] = wide["dep_code"].map(statut)
    wide["echantillon_principal"] = wide["statut_irrigue"] == "1"
    # Jura (39) 2016 et 2018 : surface irriguée nulle, donc pas de rendement irrigué (artefact probable de la
    # SAA) ; ces 2 observations sans écart calculable sont retirées (docs/resultats_phase6.md).
    n0 = len(wide)
    wide = wide.dropna(subset=["rdt_irrigue", "rdt_non_irrigue"])
    print(f"maïs : {n0 - len(wide)} observation(s) retirée(s) faute de rendement irrigué ou non irrigué")
    wide["ecart_log"] = np.log(wide["rdt_irrigue"]) - np.log(wide["rdt_non_irrigue"])

    dep_month = pd.read_parquet(PROC / "weather_dep_month_area.parquet")  # pas de masque maïs : surfacique
    h = harvest_year_windows(dep_month, range(2010, 2026), windows={"ja": [(0, 7), (0, 8)]})
    wide = wide.merge(h[["dep_code", "annee", "dd_32_ja", "swi_ja", "prec_ja"]], on=["dep_code", "annee"],
                      how="left", validate="one_to_one")
    wide = wide.merge(panel_mod.centroids(), on="dep_code", how="left", validate="many_to_one")
    if not (wide[["ecart_log", "dd_32_ja", "swi_ja", "lat_centroide"]].notna().all().all()):
        raise RuntimeError("valeurs manquantes dans le panel maïs")
    if wide.duplicated(["dep_code", "annee"]).any():
        raise RuntimeError("doublons (dep_code, annee)")
    return wide


def main() -> None:
    price = prices()
    price.to_parquet(PROC / "prix_ble_tendre.parquet", index=False)
    losses = wheat_losses(price)
    losses.to_csv(ROOT / "reports" / "tables" / "phase6_pertes_valeur.csv", index=False)
    print(losses.round(1).to_string(index=False))
    maize = maize_panel()
    maize.to_parquet(PROC / "panel_mais.parquet", index=False)
    s = maize.drop_duplicates("dep_code")
    print(f"\nmaïs : {maize.dep_code.nunique()} départements ({int(s.echantillon_principal.sum())} en statut 1), "
          f"{len(maize)} observations ; écart médian irrigué/non irrigué = {100 * (np.exp(maize.ecart_log.median()) - 1):.1f} %")


if __name__ == "__main__":
    main()
