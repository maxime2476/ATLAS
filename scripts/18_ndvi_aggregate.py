"""Étape 18 : NDVI MOD13Q1 (AppEEARS) agrégé par département, pondéré par le masque blé.

Usage : uv run python scripts/18_ndvi_aggregate.py
Entrées : data/raw/nasa_appeears/<task_id>/*.tif (toutes les commandes téléchargées),
          data/processed/weights_cell_dep_wheat.parquet
Sortie : data/processed/ndvi_dep_composite.parquet (département × composite de 16 jours)

Règles :
- pixels valides : fiabilité 0 ou 1, NDVI différent de -3000 ; NDVI = valeur × 0,0001 ;
- pixel -> maille SIM par son centre (EPSG:4326 -> EPSG:27572) ; maille valide si >= 25 % de pixels valides ;
- maille -> département avec les poids blé renormalisés sur les mailles valides ;
  NDVI départemental manquant si moins de 50 % du poids de blé est valide.
"""

import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from atlas.download import ROOT
from atlas.rpg import cell_of

RAW = ROOT / "data" / "raw" / "nasa_appeears"
PROC = ROOT / "data" / "processed"
PAT = re.compile(r"_250m_16_days_NDVI_doy(\d{4})(\d{3})\d*_aid\d+\.tif$")


def pixel_cells(profile_file):
    """Code de maille SIM de chaque pixel de la grille (même grille pour tous les fichiers)."""
    with rasterio.open(profile_file) as r:
        rows, cols = np.indices((r.height, r.width))
        lon, lat = rasterio.transform.xy(r.transform, rows.ravel(), cols.ravel())
        grid = (r.transform, r.width, r.height)
    x, y = Transformer.from_crs(4326, 27572, always_xy=True).transform(np.asarray(lon), np.asarray(lat))
    lambx, lamby = cell_of(x, y)
    return grid, lambx, lamby


def main() -> None:
    files = sorted(f for f in RAW.rglob("*.tif") if PAT.search(f.name))
    print(f"{len(files)} composites NDVI trouvés")
    grid, lambx, lamby = pixel_cells(files[0])
    weights = pd.read_parquet(PROC / "weights_cell_dep_wheat.parquet")
    cells = weights[["LAMBX", "LAMBY"]].drop_duplicates().reset_index(drop=True)
    cells["cid"] = np.arange(len(cells))
    code = pd.MultiIndex.from_arrays([lambx, lamby]).map(
        dict(zip(zip(cells.LAMBX, cells.LAMBY), cells.cid))).fillna(-1).to_numpy().astype(int)  # -1 : hors mailles de blé
    in_cell = code >= 0
    n_cells = len(cells)

    out = []
    for f in files:
        year, doy = map(int, PAT.search(f.name).groups())
        rel_file = f.with_name(f.name.replace("_NDVI_", "_pixel_reliability_"))
        with rasterio.open(f) as rn, rasterio.open(rel_file) as rr:
            if not ((rn.transform, rn.width, rn.height) == grid and (rr.transform, rr.width, rr.height) == grid):
                raise RuntimeError("grille raster différente de celle du premier composite")
            ndvi = rn.read(1).ravel()
            rel = rr.read(1).ravel()
        valid = in_cell & (ndvi != -3000) & np.isin(rel, [0, 1])
        total = np.bincount(code[in_cell], minlength=n_cells)
        nval = np.bincount(code[valid], minlength=n_cells)
        s = np.bincount(code[valid], weights=ndvi[valid] * 1e-4, minlength=n_cells)
        cell_ndvi = np.where(nval > 0, s / np.maximum(nval, 1), np.nan)
        cell_ok = (total > 0) & (nval >= 0.25 * total)
        c = cells.assign(ndvi=cell_ndvi, ok=cell_ok)
        w = weights.merge(c, on=["LAMBX", "LAMBY"])
        w["w_ok"] = w["w_wheat"] * w["ok"]
        w["wx"] = w["w_ok"] * np.nan_to_num(w["ndvi"])
        g = w.groupby("dep_code")[["w_ok", "wx", "w_wheat"]].sum()
        g["ndvi"] = np.where(g["w_ok"] >= 0.5 * g["w_wheat"], g["wx"] / g["w_ok"].replace(0, np.nan), np.nan)
        start = date(year, 1, 1) + timedelta(days=doy - 1)
        out.append(g.reset_index()[["dep_code", "ndvi", "w_ok"]].rename(columns={"w_ok": "part_poids_valide"})
                   .assign(annee=year, doy=doy, debut=pd.Timestamp(start), fin=pd.Timestamp(start + timedelta(days=15))))
        print(f"{f.name[:60]} : {start} | départements avec NDVI : {int(g['ndvi'].notna().sum())}/{len(g)} | "
              f"NDVI médian {np.nanmedian(g['ndvi']):.3f}")
    res = pd.concat(out, ignore_index=True)
    if res.duplicated(["dep_code", "annee", "doy"]).any():
        raise RuntimeError("doublons (dep_code, annee, doy)")
    res.to_parquet(PROC / "ndvi_dep_composite.parquet", index=False)
    print(f"écrit {len(res)} lignes (département × composite)")


if __name__ == "__main__":
    main()
