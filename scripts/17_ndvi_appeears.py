"""Étape 17 : commande NDVI MODIS (MOD13Q1 v6.1, 250 m, 16 jours) via l'API AppEEARS de la NASA.

Usage :
  uv run python scripts/17_ndvi_appeears.py soumettre --annees 2022          # commande de test (une année)
  uv run python scripts/17_ndvi_appeears.py soumettre --annees 2010-2021,2023-2025
  uv run python scripts/17_ndvi_appeears.py statut
  uv run python scripts/17_ndvi_appeears.py telecharger --tache <task_id>

Authentification : APPEEARS_TOKEN dans .env (non versionné), obtenu par l'utilisateur avec ses identifiants
Earthdata ; le jeton n'est jamais affiché. API : https://appeears.earthdatacloud.nasa.gov/api/
Requête : contour simplifié de la France métropolitaine (ADMIN EXPRESS), avril-juin de chaque année,
couches NDVI et pixel_reliability, GeoTIFF en projection géographique (EPSG:4326).
Les fichiers téléchargés vont dans data/raw/nasa_appeears/<task_id>/ et sont inscrits au manifeste.
"""

import argparse
import csv
import json
import pathlib
import urllib.error
import urllib.request

import geopandas as gpd

from atlas.download import ROOT, sha256_of_file

API = "https://appeears.earthdatacloud.nasa.gov/api"
RAW = ROOT / "data" / "raw" / "nasa_appeears"
LAYERS = [{"product": "MOD13Q1.061", "layer": "_250m_16_days_NDVI"},
          {"product": "MOD13Q1.061", "layer": "_250m_16_days_pixel_reliability"}]


def token() -> str:
    env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines()
               if "=" in line and not line.startswith("#"))
    tok = env.get("APPEEARS_TOKEN", "").strip()
    if not tok:
        raise SystemExit("APPEEARS_TOKEN absent de .env")
    return tok


def call(path: str, method: str = "GET", body: dict | None = None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def france_outline() -> dict:
    dep = gpd.read_parquet(ROOT / "data" / "raw" / "ign_admin_express" /
                           "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    dep = dep[dep["code_insee"].str.len() == 2]
    # Contour simplifié (≈ 2 km en Lambert 93), légèrement élargi pour ne perdre aucun pixel de bord.
    shape = dep.to_crs(2154).union_all().buffer(2000).simplify(2000).buffer(0)
    geo = gpd.GeoSeries([shape], crs=2154).to_crs(4326)
    return json.loads(geo.to_json())


def submit(years: list[int]) -> None:
    task = {"task_type": "area", "task_name": f"atlas_ndvi_{years[0]}_{years[-1]}",
            "params": {"dates": [{"startDate": f"04-01-{y}", "endDate": f"06-30-{y}"} for y in years],
                       "layers": LAYERS, "geo": france_outline(),
                       "output": {"format": {"type": "geotiff"}, "projection": "geographic"}}}
    res = call("/task", "POST", task)
    print("commande soumise :", res)


def status() -> None:
    for t in call("/task"):
        print(t["task_id"], t["task_name"], t["status"], t.get("created"), t.get("estimate", {}))


def download(task_id: str) -> None:
    out = RAW / task_id
    out.mkdir(parents=True, exist_ok=True)
    files = call(f"/bundle/{task_id}")["files"]
    rows = []
    for f in files:
        dest = out / pathlib.Path(f["file_name"]).name
        if not dest.exists():
            req = urllib.request.Request(f"{API}/bundle/{task_id}/{f['file_id']}",
                                         headers={"Authorization": f"Bearer {token()}"})
            tmp = dest.with_name(dest.name + ".part")
            # Redirection vers S3 : urllib la suit ; le jeton n'est pas transmis à un autre hôte
            # (urllib retire Authorization lors d'un changement d'hôte).
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as fh:
                for block in iter(lambda: r.read(1 << 20), b""):
                    fh.write(block)
            tmp.replace(dest)
        digest = sha256_of_file(dest)
        if f.get("sha256") and f["sha256"] != digest:
            raise RuntimeError(f"SHA-256 différent de celui annoncé par AppEEARS : {dest.name}")
        rows.append({"source": "nasa_appeears", "file": str(dest.relative_to(ROOT)),
                     "url": f"{API}/bundle/{task_id}/{f['file_id']}",
                     "size_bytes": dest.stat().st_size, "sha256": digest})
    manifest = ROOT / "docs" / "manifest_raw.csv"
    with open(manifest, newline="") as fh:
        old = [r for r in csv.DictReader(fh) if r["file"] not in {x["file"] for x in rows}]
    with open(manifest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "file", "url", "size_bytes", "sha256"])
        w.writeheader()
        w.writerows(sorted(old + rows, key=lambda r: r["file"]))
    print(f"{len(rows)} fichiers dans {out.relative_to(ROOT)} ({sum(r['size_bytes'] for r in rows) / 1e6:.0f} Mo), manifeste mis à jour")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("soumettre")
    s.add_argument("--annees", required=True)
    sub.add_parser("statut")
    d = sub.add_parser("telecharger")
    d.add_argument("--tache", required=True)
    a = p.parse_args()
    try:
        if a.cmd == "soumettre":
            # Plages séparées par des virgules, ex. « 2010-2021,2023-2025 ».
            years = []
            for part in a.annees.split(","):
                lo, _, hi = part.partition("-")
                years += list(range(int(lo), int(hi or lo) + 1))
            submit(sorted(set(years)))
        elif a.cmd == "statut":
            status()
        else:
            download(a.tache)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"AppEEARS : HTTP {e.code} {e.reason} — {e.read(300)!r}")


if __name__ == "__main__":
    main()
