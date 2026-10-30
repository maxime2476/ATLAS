"""Étape 12 : indicateurs par demi-mois pour les robustesses R11, R12 et R14.

Usage : uv run python scripts/12_build_semimonthly.py   (durée : voir data/README.md)
Entrées : SIM quotidienne 2010-2025 (avril-juillet ; plus le 1er janvier 2026 s'il est présent, sans effet ici), poids du masque blé (data/processed/weights_cell_dep_wheat.parquet)
Sortie : data/processed/weather_dep_harvest_wheat_extra.parquet (département × récolte 2010-2025) :
  gdd_0_32_m2s, dd_32_m2s   fenêtre décalée de -2 semaines (16 avril - 15 juin)
  gdd_0_32_p2s, dd_32_p2s   fenêtre décalée de +2 semaines (16 mai - 15 juillet)
  bin_<a>_<b>               jours passés dans [a, b) °C en mai-juin (double sinus), 10 classes
Demi-mois : jours 1 à 15 (demi = 1), puis 16 à la fin du mois (demi = 2).
"""

import time

import numpy as np
import pandas as pd

from atlas.degree_days import double_sine, double_sine_time_in_bin
from atlas.download import ROOT
from atlas.spatial import weighted_mean
from atlas.weather import read_year

SIM = ROOT / "data" / "raw" / "meteofrance_sim"
PROC = ROOT / "data" / "processed"
EDGES = [-np.inf, 9, 12, 15, 18, 21, 24, 27, 30, 33, np.inf]
BIN_NAMES = ["bin_lt9"] + [f"bin_{a}_{b}" for a, b in zip(EDGES[1:-2], EDGES[2:-1])] + ["bin_ge33"]
WINDOWS = {  # (mois, demi) de l'année de récolte
    "m2s": [(4, 2), (5, 1), (5, 2), (6, 1)],
    "p2s": [(5, 2), (6, 1), (6, 2), (7, 1)],
    "remplissage": [(5, 1), (5, 2), (6, 1), (6, 2)],
}


def main() -> None:
    weights = pd.read_parquet(PROC / "weights_cell_dep_wheat.parquet")
    cells = weights[["LAMBX", "LAMBY"]].drop_duplicates()
    parts = []
    for year in range(2010, 2026):  # seuls avril-juillet de l'année de récolte sont nécessaires
        t0 = time.perf_counter()
        nxt = SIM / f"QUOT_SIM2_{year + 1}.csv.gz"
        df = read_year(SIM / f"QUOT_SIM2_{year}.csv.gz", nxt if nxt.exists() else None)
        df = df[df["date"].dt.month.between(4, 7)].merge(cells, on=["LAMBX", "LAMBY"], how="inner")
        tmin, tmax, tnext = (df[c].to_numpy(float) for c in ["TINF_H", "TSUP_H", "tmin_next"])
        out = df[["LAMBX", "LAMBY"]].copy()
        out["year"], out["month"] = df["date"].dt.year, df["date"].dt.month
        out["demi"] = np.where(df["date"].dt.day <= 15, 1, 2)
        out["dd_0"] = double_sine(tmin, tmax, tnext, 0)
        out["dd_32"] = double_sine(tmin, tmax, tnext, 32)
        for name, lo, hi in zip(BIN_NAMES, EDGES[:-1], EDGES[1:]):
            out[name] = double_sine_time_in_bin(tmin, tmax, tnext, lo, hi)
        # Masquage strict, comme weather.monthly : un jour manquant rend la variable du demi-mois manquante.
        g = out.groupby(["LAMBX", "LAMBY", "year", "month", "demi"])
        agg = g.sum().where(g.count().eq(g.size(), axis=0)).reset_index()
        parts.append(agg)
        print(f"{year}: {len(df):,} maille-jours -> {len(agg):,} maille-demi-mois ({time.perf_counter() - t0:.0f} s)")
    cell = pd.concat(parts, ignore_index=True)
    values = ["dd_0", "dd_32"] + BIN_NAMES
    dep = weighted_mean(cell, weights, values, "w_wheat", ["year", "month", "demi"])

    res = None
    for w, periods in WINDOWS.items():
        sel = dep.merge(pd.DataFrame(periods, columns=["month", "demi"]), on=["month", "demi"])
        g = sel.groupby(["dep_code", "year"])
        if not ((g.size() == len(periods)).all()):
            raise RuntimeError(f"demi-mois manquants dans la fenêtre {w}")
        block = g[values].sum().reset_index().rename(columns={"year": "annee"})
        if w == "remplissage":
            block = block[["dep_code", "annee"] + BIN_NAMES]
        else:
            block = block[["dep_code", "annee", "dd_0", "dd_32"]].assign(gdd_0_32=lambda d: d.dd_0 - d.dd_32)
            block = block.rename(columns={"dd_32": f"dd_32_{w}", "gdd_0_32": f"gdd_0_32_{w}"}).drop(columns="dd_0")
        res = block if res is None else res.merge(block, on=["dep_code", "annee"], validate="one_to_one")
    if not (res.notna().all().all() and np.allclose(res[BIN_NAMES].sum(axis=1), 61)):  # mai + juin = 61 jours
        raise RuntimeError("valeurs manquantes ou classes de température ne sommant pas à 61 jours")
    res.to_parquet(PROC / "weather_dep_harvest_wheat_extra.parquet", index=False)
    print(f"écrit {len(res)} lignes ; somme des classes = 61 jours vérifiée ; "
          f"jours ≥ 33 °C en mai-juin : moyenne {res.bin_ge33.mean():.3f}, max {res.bin_ge33.max():.2f}")


if __name__ == "__main__":
    main()
