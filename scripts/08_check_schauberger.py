"""Étape 8 : compatibilité Schauberger et al. (2022) / SAA sur le recouvrement 2010-2018 (blé tendre d'hiver).

Usage : uv run python scripts/08_check_schauberger.py
Sortie : data/interim/schauberger_wheat_winter_raw.parquet ; verdict imprimé selon les seuils fixés en phase 2.
"""

import importlib.util

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from atlas.download import ROOT
from atlas.schauberger import normalize_name, read_crop

RAW = ROOT / "data" / "raw"
OVERLAP = range(2010, 2019)

# Réutilise la définition de la population et les résidus à deux effets fixes de l'étape 6.
_spec = importlib.util.spec_from_file_location("exposure", ROOT / "scripts" / "06_exposure_check.py")
exposure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exposure)


def main() -> None:
    admin = pq.read_table(RAW / "ign_admin_express" / "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet",
                          columns=["code_insee", "nom_officiel"]).to_pandas()
    admin = admin[admin["code_insee"].str.len() == 2]
    name_to_code = dict(zip(admin["nom_officiel"].map(normalize_name), admin["code_insee"]))

    zip_path = RAW / "pik_schauberger" / "2021-001_Schauberger-et-al_Data.zip"
    filtered = read_crop(zip_path, "wheat_winter", name_to_code, version="FILTERED")
    sch = read_crop(zip_path, "wheat_winter", name_to_code, version="RAW")
    sch.to_parquet(ROOT / "data" / "interim" / "schauberger_wheat_winter_raw.parquet", index=False)

    saa = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    pop = exposure.wheat_population(saa)
    # Pourquoi RAW : les valeurs masquées par FILTERED sont surtout des chutes de rendement.
    f = filtered[filtered["dep_code"].isin(pop) & filtered["annee"].between(1990, 2018)].set_index(["dep_code", "annee"])
    r = sch[sch["dep_code"].isin(pop) & sch["annee"].between(1990, 2018)].set_index(["dep_code", "annee"])
    masked = f["rendement_q_ha"].isna() & r["rendement_q_ha"].notna()
    print(f"valeurs masquées par FILTERED (1990-2018, population) : {int(masked.sum())} ; "
          f"par année : {masked.groupby(level='annee').sum().loc[lambda s: s > 0].to_dict()}")
    print(f"manquants dans RAW : {int(r['rendement_q_ha'].isna().sum())}")
    a = saa[(saa["culture_code"] == "01") & saa["dep_code"].isin(pop) & saa["annee"].isin(OVERLAP)]
    b = sch[sch["dep_code"].isin(pop) & sch["annee"].isin(OVERLAP)]
    m = a[["dep_code", "annee", "rendement_q_ha"]].merge(
        b[["dep_code", "annee", "rendement_q_ha"]], on=["dep_code", "annee"], how="outer",
        suffixes=("_saa", "_sch"), validate="one_to_one", indicator=True)
    print("appariement :", m["_merge"].value_counts().to_dict())
    both = m[(m["_merge"] == "both")].dropna(subset=["rendement_q_ha_saa", "rendement_q_ha_sch"]).copy()
    print(f"paires utilisables : {len(both)} / {len(pop) * len(OVERLAP)} "
          f"(manquants Schauberger, valeurs filtrées comprises : {m['rendement_q_ha_sch'].isna().sum()})")

    rel = both["rendement_q_ha_sch"] / both["rendement_q_ha_saa"] - 1
    both["log_saa"], both["log_sch"] = np.log(both["rendement_q_ha_saa"]), np.log(both["rendement_q_ha_sch"])
    # Résidus à deux effets fixes sur le sous-échantillon commun (équilibré si aucune paire manquante).
    balanced = both.groupby("dep_code")["annee"].transform("size").eq(len(OVERLAP))
    bb = both[balanced]
    r_saa, r_sch = exposure.twoway_residuals(bb, "log_saa"), exposure.twoway_residuals(bb, "log_sch")
    corr_resid = float(np.corrcoef(r_saa, r_sch)[0, 1])
    med_abs = float(rel.abs().median())

    print(f"écart relatif Schauberger/SAA : médiane {rel.median():+.4f}, |médiane| {med_abs:.4f}, "
          f"p5 {rel.quantile(.05):+.4f}, p95 {rel.quantile(.95):+.4f}")
    print(f"part des paires identiques à ±0,5 q/ha : "
          f"{((both['rendement_q_ha_sch'] - both['rendement_q_ha_saa']).abs() <= 0.5).mean():.3f}")
    print("écart relatif médian par année :", rel.groupby(both["annee"]).median().round(4).to_dict())
    print(f"corrélation des niveaux : {np.corrcoef(both['rendement_q_ha_saa'], both['rendement_q_ha_sch'])[0, 1]:.4f}")
    print(f"corrélation des résidus (effets fixes), {bb['dep_code'].nunique()} départements équilibrés : {corr_resid:.4f}")

    ok_a, ok_b = corr_resid >= 0.90, med_abs <= 0.03
    verdict = ("COMPATIBLE" if ok_a and ok_b else
               "COMPATIBLE AVEC EFFET FIXE DÉPARTEMENT × SOURCE" if ok_a else "INCOMPATIBLE : allongement abandonné")
    print(f"\nCRITÈRES : (a) corr ≥ 0,90 -> {ok_a} ; (b) |écart| médian ≤ 3 % -> {ok_b} => {verdict}")


if __name__ == "__main__":
    main()
