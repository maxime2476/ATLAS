"""Étape 5 : indicateurs météo mensuels par maille, puis par département (poids surfaciques).

Usage : uv run python scripts/05_build_weather_monthly.py
Entrées : data/raw/meteofrance_sim/QUOT_SIM2_1958..2025.csv.gz, data/processed/weights_cell_dep_area.parquet
Sorties :
  data/interim/weather_cell_month.parquet       maille × mois (mailles françaises seulement)
  data/processed/weather_dep_month_area.parquet département × mois, pondération surfacique
"""

import time

import pandas as pd

from atlas.download import ROOT
from atlas.spatial import weighted_mean
from atlas.weather import MEAN_VARS, SUM_VARS, daily_indicators, monthly, read_year

SIM = ROOT / "data" / "raw" / "meteofrance_sim"
WEIGHTS = ROOT / "data" / "processed" / "weights_cell_dep_area.parquet"
OUT_CELL = ROOT / "data" / "interim" / "weather_cell_month.parquet"
OUT_DEP = ROOT / "data" / "processed" / "weather_dep_month_area.parquet"
YEARS = range(1958, 2026)  # 1958 (dès le 1er août) : semis de la récolte 1959 (Q2, phase 2 bis)


def main() -> None:
    weights = pd.read_parquet(WEIGHTS)
    french_cells = weights[["LAMBX", "LAMBY"]].drop_duplicates()
    parts = []
    for year in YEARS:
        t0 = time.perf_counter()
        nxt = SIM / f"QUOT_SIM2_{year + 1}.csv.gz"
        df = read_year(SIM / f"QUOT_SIM2_{year}.csv.gz", nxt if nxt.exists() else None)
        df = df.merge(french_cells, on=["LAMBX", "LAMBY"], how="inner")
        m = monthly(daily_indicators(df))
        n_missing = m[SUM_VARS + MEAN_VARS].isna().any(axis=1).sum()
        print(f"{year}: {len(df):,} lignes maille-jour -> {len(m):,} maille-mois "
              f"(mois incomplets : {n_missing}) en {time.perf_counter() - t0:.0f} s")
        parts.append(m)
    cell_month = pd.concat(parts, ignore_index=True)
    OUT_CELL.parent.mkdir(parents=True, exist_ok=True)
    cell_month.to_parquet(OUT_CELL, index=False)

    dep_month = weighted_mean(cell_month, weights, SUM_VARS + MEAN_VARS, "w_area", ["year", "month"])
    dep_month.to_parquet(OUT_DEP, index=False)
    print(f"maille-mois : {len(cell_month):,} | département-mois : {len(dep_month):,} "
          f"({dep_month.dep_code.nunique()} départements)")


if __name__ == "__main__":
    main()
