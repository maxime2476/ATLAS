"""Étape 31 : température de surface MODIS (MOD11A2, LST de jour) agrégée par département, masque maïs.

Usage : uv run python scripts/31_lst_aggregate.py   (après scripts/30_lst_appeears.py telecharger)
Entrées : data/raw/nasa_appeears_lst/<task_id>/*.tif ; data/processed/weights_cell_dep_maize.parquet
Sorties : data/processed/lst_dep_composite.parquet (département × composite de 8 jours)
          data/processed/lst_dep_ja.parquet (département × année : lst_ja, nombre de composites valides)

Règles :
- pixel valide : LST ≠ 0 ; QC_Day bits 0-1 = 00, ou = 01 avec erreur de LST ≤ 2 K (bits 6-7 ≤ 01) ;
  LST (°C) = valeur × 0,02 − 273,15 ;
- pixel -> maille SIM par son centre ; maille valide si ≥ 25 % de pixels valides ;
- maille -> département, poids maïs renormalisés ; manquant si < 50 % du poids est valide ;
- lst_ja = moyenne des composites valides de l'été ; manquante si moins de 6 composites valides.
Même construction que le NDVI (scripts/18_ndvi_aggregate.py), dont on reprend la correspondance pixel -> maille.
"""

import importlib.util
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import rasterio

from atlas.download import ROOT

_spec = importlib.util.spec_from_file_location("ndvi_agg", ROOT / "scripts" / "18_ndvi_aggregate.py")
ndvi_agg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ndvi_agg)

RAW = ROOT / "data" / "raw" / "nasa_appeears_lst"
PROC = ROOT / "data" / "processed"
PAT = re.compile(r"_LST_Day_1km_doy(\d{4})(\d{3})\d*_aid\d+\.tif$")
MIN_COMPOSITES = 6


def valid_pixels(lst: np.ndarray, qc: np.ndarray) -> np.ndarray:
    """Pixels retenus selon les bits de qualité de MOD11A2 (voir l'en-tête)."""
    mandatory = qc & 0b11
    error = (qc >> 6) & 0b11
    return (lst != 0) & ((mandatory == 0) | ((mandatory == 1) & (error <= 1)))


def main() -> None:
    files = sorted(f for f in RAW.rglob("*.tif") if PAT.search(f.name))
    print(f"{len(files)} composites LST trouvés")
    grid, lambx, lamby = ndvi_agg.pixel_cells(files[0])
    weights = pd.read_parquet(PROC / "weights_cell_dep_maize.parquet")
    cells = weights[["LAMBX", "LAMBY"]].drop_duplicates().reset_index(drop=True)
    cells["cid"] = np.arange(len(cells))
    code = pd.MultiIndex.from_arrays([lambx, lamby]).map(
        dict(zip(zip(cells.LAMBX, cells.LAMBY), cells.cid))).fillna(-1).to_numpy().astype(int)  # -1 : hors masque
    in_cell = code >= 0
    n_cells = len(cells)

    out = []
    for f in files:
        year, doy = map(int, PAT.search(f.name).groups())
        start = date(year, 1, 1) + timedelta(days=doy - 1)
        if not (date(year, 7, 1) <= start <= date(year, 8, 31)):
            continue                                   # composite commencé hors de la fenêtre
        qc_file = f.with_name(f.name.replace("_LST_Day_1km_", "_QC_Day_"))
        with rasterio.open(f) as rl, rasterio.open(qc_file) as rq:
            if not ((rl.transform, rl.width, rl.height) == grid and (rq.transform, rq.width, rq.height) == grid):
                raise RuntimeError("grille raster différente de celle du premier composite")
            lst = rl.read(1).ravel().astype(np.int64)
            qc = rq.read(1).ravel().astype(np.int64)
        valid = in_cell & valid_pixels(lst, qc)
        total = np.bincount(code[in_cell], minlength=n_cells)
        nval = np.bincount(code[valid], minlength=n_cells)
        s = np.bincount(code[valid], weights=lst[valid] * 0.02 - 273.15, minlength=n_cells)
        c = cells.assign(lst=np.where(nval > 0, s / np.maximum(nval, 1), np.nan),
                         ok=(total > 0) & (nval >= 0.25 * total))
        w = weights.merge(c, on=["LAMBX", "LAMBY"], validate="many_to_one")
        w["w_ok"] = w["w_maize"] * w["ok"]
        w["wx"] = w["w_ok"] * np.nan_to_num(w["lst"])
        g = w.groupby("dep_code")[["w_ok", "wx", "w_maize"]].sum()
        g["lst"] = np.where(g["w_ok"] >= 0.5 * g["w_maize"], g["wx"] / g["w_ok"].replace(0, np.nan), np.nan)
        out.append(g.reset_index()[["dep_code", "lst", "w_ok"]].rename(columns={"w_ok": "part_poids_valide"})
                   .assign(annee=year, doy=doy, debut=pd.Timestamp(start)))
    comp = pd.concat(out, ignore_index=True)
    if comp.duplicated(["dep_code", "annee", "doy"]).any():
        raise RuntimeError("doublons (dep_code, annee, doy)")
    comp.to_parquet(PROC / "lst_dep_composite.parquet", index=False)

    ja = comp.groupby(["dep_code", "annee"]).agg(lst_ja=("lst", "mean"), n_composites_valides=("lst", "count"),
                                                 n_composites=("lst", "size")).reset_index()
    ja.loc[ja.n_composites_valides < MIN_COMPOSITES, "lst_ja"] = np.nan
    ja.to_parquet(PROC / "lst_dep_ja.parquet", index=False)
    print(f"{len(comp)} département-composites ; {len(ja)} département-années, dont "
          f"{int(ja.lst_ja.isna().sum())} manquantes ; composites par été : {ja.n_composites.min()}-{ja.n_composites.max()}")


if __name__ == "__main__":
    main()
