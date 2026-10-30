"""Étape 27 : degrés-jours au-dessus de 32 °C en juillet-août recalculés avec E-OBS (vérification de Q1).

Usage : uv run python scripts/27_eobs_heat.py
Entrées :
  data/raw/eobs/{tn,tx}_ens_mean_0.1deg_reg_{1995-2010,2011-2025}_v33.0e.nc   (--eobs dans 01_download_raw.py)
  data/raw/meteofrance_sim/coordonnees_grille_safran_lambert-2-etendu.csv      (lat/lon des mailles SIM)
  data/processed/weights_cell_dep_maize.parquet                                (masque maïs RPG 2015-2017)
Sortie : data/processed/weather_dep_eobs_ja.parquet (dep_code, annee, dd_32_ja_eobs ; 2000-2025)

Seule la source de température change par rapport à `dd_32_ja` : même double sinus (Tmin du jour, Tmax du jour,
Tmin du lendemain ; le 31 août utilise le 1er septembre), même fenêtre (1er juillet - 31 août de l'année de
récolte), mêmes poids du masque maïs. Chaque maille SIM reçoit le point E-OBS le plus proche (grille régulière
de 0,1°, centre de maille SIM en WGS84).
"""

import datetime as dt

import h5py
import numpy as np
import pandas as pd

from atlas.degree_days import double_sine
from atlas.download import ROOT
from atlas.spatial import weighted_mean

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
YEARS = range(2000, 2026)
EPOCH = dt.date(1950, 1, 1)  # unité du temps E-OBS : jours depuis le 1950-01-01


def eobs_file(var: str, year: int):
    period = "1995-2010" if year <= 2010 else "2011-2025"
    return RAW / "eobs" / f"{var}_ens_mean_0.1deg_reg_{period}_v33.0e.nc"


def nearest_index(values, grid) -> np.ndarray:
    """Indice du point de grille régulière le plus proche (pas constant, premier point grid[0])."""
    step = grid[1] - grid[0]
    return np.rint((np.asarray(values) - grid[0]) / step).astype(int)


def read_window(var: str, year: int, i_lat, i_lon) -> np.ndarray:
    """Valeurs (°C) du 1er juillet au 1er septembre inclus, tableau (jours × mailles) ; NaN si manquant."""
    with h5py.File(eobs_file(var, year), "r") as f:
        t = f["time"][:]
        start = (dt.date(year, 7, 1) - EPOCH).days
        end = (dt.date(year, 9, 1) - EPOCH).days
        k0, k1 = np.searchsorted(t, start), np.searchsorted(t, end)
        if t[k0] != start or t[k1] != end or k1 - k0 != 62:
            raise RuntimeError(f"jours manquants dans {eobs_file(var, year).name} pour {year}")
        v = f[var]
        # Lecture d'un bloc rectangulaire couvrant les mailles, puis sélection des points.
        lat0, lat1, lon0, lon1 = i_lat.min(), i_lat.max() + 1, i_lon.min(), i_lon.max() + 1
        block = v[k0:k1 + 1, lat0:lat1, lon0:lon1]
        raw = block[:, i_lat - lat0, i_lon - lon0].astype(float)
        fill, scale = v.attrs["_FillValue"][0], float(v.attrs["scale_factor"][0])
    return np.where(raw == fill, np.nan, raw * scale)


def main() -> None:
    weights = pd.read_parquet(PROC / "weights_cell_dep_maize.parquet")
    grid = pd.read_csv(RAW / "meteofrance_sim" / "coordonnees_grille_safran_lambert-2-etendu.csv",
                       sep=";", decimal=",")
    grid.columns = ["LAMBX", "LAMBY", "lat", "lon"]
    cells = weights[["LAMBX", "LAMBY"]].drop_duplicates().merge(grid, on=["LAMBX", "LAMBY"], how="left",
                                                                 validate="one_to_one")
    if cells["lat"].isna().any():
        raise RuntimeError("maille du masque maïs absente de la grille SIM")
    with h5py.File(eobs_file("tx", 2000), "r") as f:
        lat, lon = f["latitude"][:], f["longitude"][:]
    cells["i_lat"] = nearest_index(cells["lat"], lat)
    cells["i_lon"] = nearest_index(cells["lon"], lon)
    cells["dist_deg"] = np.hypot(lat[cells.i_lat] - cells.lat, lon[cells.i_lon] - cells.lon)
    print(f"{len(cells)} mailles du masque ; distance au point E-OBS : médiane {cells.dist_deg.median():.3f}°, "
          f"max {cells.dist_deg.max():.3f}° ; {cells[['i_lat', 'i_lon']].drop_duplicates().shape[0]} points E-OBS")

    parts = []
    for year in YEARS:
        tn = read_window("tn", year, cells.i_lat.to_numpy(), cells.i_lon.to_numpy())
        tx = read_window("tx", year, cells.i_lat.to_numpy(), cells.i_lon.to_numpy())
        # 62 jours (juillet-août) ; le Tmin du lendemain du 31 août est celui du 1er septembre.
        dd = double_sine(tn[:-1], tx[:-1], tn[1:], 32)
        total = np.where(np.isnan(dd).any(axis=0), np.nan, dd.sum(axis=0))  # un jour manquant -> maille manquante
        part = cells[["LAMBX", "LAMBY"]].assign(annee=year, dd_32_ja_eobs=total)
        n_missing = int(part.dd_32_ja_eobs.isna().sum())
        if n_missing:
            print(f"{year} : {n_missing} mailles avec au moins un jour manquant (laissées manquantes)")
        parts.append(part)
    cell_year = pd.concat(parts, ignore_index=True)

    out = weighted_mean(cell_year, weights, ["dd_32_ja_eobs"], "w_maize", ["annee"])
    out = out.sort_values(["dep_code", "annee"]).reset_index(drop=True)
    out.to_parquet(PROC / "weather_dep_eobs_ja.parquet", index=False)
    print(f"{out.dep_code.nunique()} départements × {out.annee.nunique()} années ; "
          f"département-années manquantes : {int(out.dd_32_ja_eobs.isna().sum())}")


if __name__ == "__main__":
    main()
