"""Étape 7 : masque fixe d'une culture (RPG 2015-2017) et météo pondérée par ce masque.

Usage : uv run python scripts/07_build_wheat_mask.py                  # blé tendre d'hiver (BTH), phases 2-6
        uv run python scripts/07_build_wheat_mask.py --culture MIS    # maïs grain (code MIS), phase 2 bis
Prérequis : couches PARCELLES_GRAPHIQUES extraites dans data/interim/rpg/<année>/ (voir data/raw/ign_rpg/README.md)
Sorties (suffixe « wheat » pour BTH, « maize » pour MIS) :
  data/processed/<culture>_area_cell_dep_rpg.parquet   surface par (maille, dép., millésime)
  data/processed/weights_cell_dep_<culture>.parquet     poids = surface moyenne 2015-2017, normalisée par département
  data/processed/weather_dep_month_<culture>.parquet    météo département × mois pondérée par la culture
"""

import argparse
import time

import pandas as pd

from atlas.download import ROOT
from atlas.rpg import wheat_area_by_cell_dep, wheat_parcels
from atlas.spatial import departements, weighted_mean
from atlas.weather import MEAN_VARS, SUM_VARS

RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROC = ROOT / "data" / "processed"
YEARS = [2015, 2016, 2017]
CROPS = {"BTH": "wheat", "MIS": "maize", "MIE": "fodder"}  # code RPG -> suffixe des fichiers (MIE : maïs ensilage, réplication fourrage)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--culture", default="BTH", choices=sorted(CROPS))
    code = parser.parse_args().culture
    name = CROPS[code]
    dep = departements(RAW / "ign_admin_express" / "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    grid = pd.read_csv(RAW / "meteofrance_sim" / "coordonnees_grille_safran_lambert-2-etendu.csv",
                       sep=";", decimal=",").iloc[:, :2]
    grid.columns = ["LAMBX", "LAMBY"]

    parts = []
    for year in YEARS:
        t0 = time.perf_counter()
        parcels = wheat_parcels(INTERIM / "rpg" / str(year) / "PARCELLES_GRAPHIQUES.shp", crop_code=code)
        area, ctl = wheat_area_by_cell_dep(parcels, dep, grid)
        print(f"{year}: {ctl['parcelles']:,} parcelles {code}, {ctl['surface_ha'] / 1e6:.3f} Mha ; "
              f"hors département {ctl['hors_departement_ha']:.0f} ha, hors grille {ctl['hors_grille_ha']:.0f} ha "
              f"({time.perf_counter() - t0:.0f} s)")
        parts.append(area.assign(millesime=year))
    area = pd.concat(parts, ignore_index=True)
    area.to_parquet(PROC / f"{name}_area_cell_dep_rpg.parquet", index=False)

    # Poids fixes : moyenne des trois millésimes (une maille absente une année compte pour 0).
    mean_area = (area.pivot_table(index=["LAMBX", "LAMBY", "dep_code"], columns="millesime",
                                  values="surf_ha", fill_value=0).mean(axis=1).rename(f"{name}_ha").reset_index())
    w_col = f"w_{name}"
    mean_area[w_col] = mean_area[f"{name}_ha"] / mean_area.groupby("dep_code")[f"{name}_ha"].transform("sum")
    mean_area.to_parquet(PROC / f"weights_cell_dep_{name}.parquet", index=False)
    print(f"départements avec la culture {code} (RPG) : {mean_area.dep_code.nunique()} ; "
          f"sans la culture : {sorted(set(dep.dep_code) - set(mean_area.dep_code))}")

    cell_month = pd.read_parquet(INTERIM / "weather_cell_month.parquet")
    dep_month = weighted_mean(cell_month, mean_area, SUM_VARS + MEAN_VARS, w_col, ["year", "month"])
    dep_month.to_parquet(PROC / f"weather_dep_month_{name}.parquet", index=False)
    print(f"écrit weather_dep_month_{name}.parquet ({len(dep_month):,} lignes)")


if __name__ == "__main__":
    main()
