"""Étape 9 : panels d'analyse blé tendre d'hiver (aucune estimation ici).

Usage : uv run python scripts/09_build_panel.py
Sorties :
  data/processed/panel_ble.parquet       85 départements × récoltes 2010-2025 (spécification principale)
  data/processed/panel_ble_long.parquet  85 départements × récoltes 1990-2025 (robustesse)
  data/processed/panel_ble_1959.parquet  85 départements × récoltes 1959-2025 (Q2, phase 0 bis ; non équilibré)
Imprime un tableau de contrôle des jointures.

Choix :
- population : surface moyenne 2010-2012 de blé tendre d'hiver (SAA) ≥ 1000 ha (85 départements) ;
- échantillon principal : statut qualité SAA 1 (83 départements), colonne `echantillon_principal` ;
- poids de régression : cette même surface fixe (pas la surface de l'année, qui dépend de la météo) ;
- météo : pondération par le masque blé RPG 2015-2017 ;
- rendement 1990-2009 (panel long) : Schauberger et al. RAW ; 2010-2025 : SAA.
"""

import importlib.util

import geopandas as gpd
import numpy as np
import pandas as pd

from atlas.download import ROOT

PROC = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"
_spec = importlib.util.spec_from_file_location("exposure", ROOT / "scripts" / "06_exposure_check.py")
exposure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exposure)
WINDOWS = ["automne", "hiver", "printemps", "remplissage"]


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Degrés-jours de croissance entre 0 et 32 °C (et 30 °C) par fenêtre : dd_0 - dd_seuil."""
    for w in WINDOWS:
        df[f"gdd_0_32_{w}"] = df[f"dd_0_{w}"] - df[f"dd_32_{w}"]
        df[f"gdd_0_30_{w}"] = df[f"dd_0_{w}"] - df[f"dd_30_{w}"]
    return df


def centroids() -> pd.DataFrame:
    """Centroïde de chaque département (calculé en Lambert 93, exprimé en WGS84) pour les erreurs de Conley."""
    dep = gpd.read_parquet(ROOT / "data" / "raw" / "ign_admin_express" /
                           "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    dep = dep[dep["code_insee"].str.len() == 2].to_crs(2154)
    c = dep.geometry.centroid.to_crs(4326)
    return pd.DataFrame({"dep_code": dep["code_insee"].to_numpy(), "lat_centroide": c.y.to_numpy(),
                         "lon_centroide": c.x.to_numpy()})


def control(name: str, before: int, after: int, **extra) -> dict:
    return {"étape": name, "lignes avant": before, "lignes après": after, **extra}


def main() -> None:
    saa = pd.read_parquet(INTERIM / "saa_cop_departements_long.parquet")
    pop = exposure.wheat_population(saa)
    ctl = []

    wheat = saa[(saa["culture_code"] == "01") & saa["metropole"]].copy()
    ref = (wheat[wheat["annee"].between(2010, 2012)].groupby("dep_code")["surface_ha"].mean()
           .rename("surface_ref_ha"))
    y = wheat[wheat["dep_code"].isin(pop)][["dep_code", "dep_libelle", "reg_libelle", "annee", "statut_qualite",
                                           "provisoire", "surface_ha", "rendement_q_ha", "production_q"]]
    ctl.append(control("SAA blé tendre d'hiver, métropole -> population", len(wheat), len(y),
                       departements=y["dep_code"].nunique()))
    y = y.merge(ref, on="dep_code", how="left", validate="many_to_one").assign(source_rendement="SAA")
    y = y.merge(centroids(), on="dep_code", how="left", validate="many_to_one")

    w = pd.read_parquet(PROC / "weather_dep_harvest_wheat.parquet")
    panel = y.merge(w, on=["dep_code", "annee"], how="left", validate="one_to_one", indicator=True)
    ctl.append(control("jointure météo (masque blé) 2010-2025", len(y), len(panel),
                       appariees=int((panel["_merge"] == "both").sum()),
                       non_appariees=int((panel["_merge"] != "both").sum())))
    panel = add_derived(panel.drop(columns="_merge"))
    panel["log_rendement"] = np.log(panel["rendement_q_ha"])
    # Échantillon principal (phase 0, § 5) : départements en statut qualité 1. Le statut ne décrit
    # que la dernière année publiée ; 90 et 91 (statut 2, 0,74 % du poids) restent pour la robustesse.
    statut1 = set(panel.loc[panel["statut_qualite"] == "1", "dep_code"])
    panel["echantillon_principal"] = panel["dep_code"].isin(statut1)
    panel = panel.sort_values(["dep_code", "annee"]).reset_index(drop=True)
    panel.to_parquet(PROC / "panel_ble.parquet", index=False)

    # --- Panels longs : Schauberger RAW (début..2009) + SAA 2010-2025 ------------------
    # 1990 : robustesse de la phase 4 (panel_ble_long) ; 1959 : question Q2 de la phase 0 bis (panel_ble_1959).
    # Les rendements manquants avant 2010 restent manquants (pas d'imputation) ; ils sont comptés ci-dessous.
    sch = pd.read_parquet(INTERIM / "schauberger_wheat_winter_raw.parquet")
    labels = y.drop_duplicates("dep_code")[["dep_code", "dep_libelle", "reg_libelle", "surface_ref_ha",
                                            "lat_centroide", "lon_centroide"]]
    longs = {}
    for first, fname in [(1990, "panel_ble_long"), (1959, "panel_ble_1959")]:
        old = sch[sch["dep_code"].isin(pop) & sch["annee"].between(first, 2009)][["dep_code", "annee", "rendement_q_ha"]]
        old = old.assign(source_rendement="Schauberger_RAW", provisoire=False)
        old = old.merge(labels, on="dep_code", how="left", validate="many_to_one")
        long_y = pd.concat([old, y[old.columns.tolist() + ["statut_qualite", "surface_ha", "production_q"]]],
                           ignore_index=True)
        w_long = pd.read_parquet(PROC / f"weather_dep_harvest_wheat_{first}.parquet")
        long = long_y.merge(w_long, on=["dep_code", "annee"], how="left", validate="one_to_one", indicator=True)
        ctl.append(control(f"panel {first}-2025 : rendements {first}-2009 + 2010-2025 -> météo",
                           len(long_y), len(long), appariees=int((long["_merge"] == "both").sum()),
                           rendement_manquant=int(long["rendement_q_ha"].isna().sum())))
        long = add_derived(long.drop(columns="_merge"))
        long["log_rendement"] = np.log(long["rendement_q_ha"])
        long["echantillon_principal"] = long["dep_code"].isin(statut1)
        long = long.sort_values(["dep_code", "annee"]).reset_index(drop=True)
        long.to_parquet(PROC / f"{fname}.parquet", index=False)
        longs[fname] = long

    print(pd.DataFrame(ctl).to_string(index=False))
    weather_cols = [c for c in panel.columns if c.endswith(tuple(WINDOWS))]
    print(f"\npanel_ble : {len(panel)} lignes, {panel.dep_code.nunique()} départements, "
          f"{panel.annee.min()}-{panel.annee.max()}, {len(weather_cols)} variables météo ; "
          f"valeurs manquantes (rendement / météo) : {panel.rendement_q_ha.isna().sum()} / "
          f"{panel[weather_cols].isna().sum().sum()}")
    for fname, long in longs.items():
        miss = long.loc[long.rendement_q_ha.isna(), ["dep_code", "annee"]]
        print(f"{fname} : {len(long)} lignes, {long.annee.min()}-{long.annee.max()} ; rendements manquants : "
              f"{len(miss)} (années : {sorted(miss.annee.unique().tolist())[:15]})")


if __name__ == "__main__":
    main()
