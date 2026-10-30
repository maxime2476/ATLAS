"""Étape 13 : altitude moyenne des mailles SIM (robustesse R13, départements « de montagne »).

Usage : uv run python scripts/13_cell_altitude.py
Source : service de calcul altimétrique de la Géoplateforme IGN (ressource ign_rge_alti_wld, RGE ALTI),
         https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json ; limites : 5 000 points
         par requête, 5 requêtes par seconde ; contenus sous licence Etalab 2.0.
Méthode : 16 points par maille (sous-grille 4 × 4, décalages ±1 et ±3 km autour du centre, Lambert II étendu).
Sorties :
  data/raw/ign_altimetrie/sim_cells_subgrid_altitude.parquet  réponse brute (un point par ligne), au manifeste
  data/processed/cell_altitude.parquet                         altitude moyenne par maille
  data/processed/dep_montagne.parquet                          part du blé à ≥ 600 m et indicatrice R13
"""

import csv
import json
import time
import urllib.request

import numpy as np
import pandas as pd
from pyproj import Transformer

from atlas.download import ROOT, USER_AGENT, sha256_of_file, tls_context

URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
RAW = ROOT / "data" / "raw" / "ign_altimetrie" / "sim_cells_subgrid_altitude.parquet"
PROC = ROOT / "data" / "processed"
# Hors couverture RGE ALTI (mer, étranger), le service renvoie -99999, et des valeurs interpolées aberrantes
# sur les côtes (ex. -99885, -6 080 361) : on ne garde que les altitudes plausibles en métropole.
VALID_RANGE = (-50, 4810)


def fetch(lon, lat) -> list[float]:
    body = json.dumps({"lon": "|".join(f"{v:.6f}" for v in lon), "lat": "|".join(f"{v:.6f}" for v in lat),
                       "resource": "ign_rge_alti_wld", "delimiter": "|", "zonly": "true"}).encode()
    req = urllib.request.Request(URL, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, context=tls_context(), timeout=120) as r:
        return json.load(r)["elevations"]


def collect() -> None:
    cells = pd.read_parquet(PROC / "weights_cell_dep_area.parquet")[["LAMBX", "LAMBY"]].drop_duplicates()
    offsets = np.array([-3000, -1000, 1000, 3000])
    dx, dy = np.meshgrid(offsets, offsets)
    pts = pd.DataFrame({
        "LAMBX": np.repeat(cells["LAMBX"].to_numpy(), 16), "LAMBY": np.repeat(cells["LAMBY"].to_numpy(), 16),
        "x_m": np.repeat(cells["LAMBX"].to_numpy() * 100, 16) + np.tile(dx.ravel(), len(cells)),
        "y_m": np.repeat(cells["LAMBY"].to_numpy() * 100, 16) + np.tile(dy.ravel(), len(cells))})
    pts["lon"], pts["lat"] = Transformer.from_crs(27572, 4326, always_xy=True).transform(pts.x_m, pts.y_m)
    alt = []
    for start in range(0, len(pts), 5000):
        chunk = pts.iloc[start:start + 5000]
        alt += fetch(chunk["lon"], chunk["lat"])
        time.sleep(0.3)  # < 5 requêtes par seconde
    pts["altitude_m"] = alt
    RAW.parent.mkdir(parents=True, exist_ok=True)
    pts.to_parquet(RAW, index=False)
    # Ajout au manifeste (même format que scripts/01_download_raw.py).
    manifest = ROOT / "docs" / "manifest_raw.csv"
    with open(manifest, newline="") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r["file"] != str(RAW.relative_to(ROOT))]
    rows.append({"source": "ign_altimetrie", "file": str(RAW.relative_to(ROOT)), "url": URL + " (POST, ign_rge_alti_wld)",
                 "size_bytes": RAW.stat().st_size, "sha256": sha256_of_file(RAW)})
    with open(manifest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "file", "url", "size_bytes", "sha256"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["file"]))


def main() -> None:
    if not RAW.exists():
        collect()
    pts = pd.read_parquet(RAW)
    valid = pts[pts["altitude_m"].between(*VALID_RANGE)]
    cell = valid.groupby(["LAMBX", "LAMBY"]).agg(altitude_moy_m=("altitude_m", "mean"),
                                                 n_points_valides=("altitude_m", "size")).reset_index()
    print(f"points : {len(pts):,} ; exclus (hors plage plausible) : {len(pts) - len(valid):,} ; "
          f"mailles avec altitude : {len(cell)} ; altitude moyenne de maille : min {cell.altitude_moy_m.min():.0f} m, "
          f"max {cell.altitude_moy_m.max():.0f} m")
    cell.to_parquet(PROC / "cell_altitude.parquet", index=False)

    w = pd.read_parquet(PROC / "weights_cell_dep_wheat.parquet").merge(cell, on=["LAMBX", "LAMBY"], how="left")
    # 2 mailles côtières (29, 50 ; 16 ha de blé, poids <= 0,02 %) n'ont aucun point valide (presque
    # entièrement en mer) : altitude fixée à 0 m (niveau de la mer), sans effet mesurable sur le critère.
    n_missing = int(w["altitude_moy_m"].isna().sum())
    if not (n_missing <= 5 and w.loc[w["altitude_moy_m"].isna(), "wheat_ha"].sum() < 100):
        raise RuntimeError("trop de blé sans altitude")
    w["altitude_moy_m"] = w["altitude_moy_m"].fillna(0.0)
    print(f"mailles de blé sans point valide (altitude fixée à 0 m) : {n_missing}")
    dep = w.assign(haut=lambda d: d.w_wheat * (d.altitude_moy_m >= 600)).groupby("dep_code").agg(
        part_ble_600m=("haut", "sum"),
        altitude_ble_moy_m=("altitude_moy_m", lambda s: np.average(s, weights=w.loc[s.index, "w_wheat"])))
    dep["montagne_r13"] = dep["part_ble_600m"] >= 0.25  # critère fixé
    dep.reset_index().to_parquet(PROC / "dep_montagne.parquet", index=False)
    print("départements « de montagne » (≥ 25 % du blé à ≥ 600 m) :")
    print(dep[dep.montagne_r13].sort_values("part_ble_600m", ascending=False).round(2).to_string())


if __name__ == "__main__":
    main()
