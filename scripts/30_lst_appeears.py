"""Étape 30 : commande de la température de surface MODIS (MOD11A2 v6.1, LST de jour, 1 km, 8 jours) via AppEEARS.

Usage :
  uv run python scripts/30_lst_appeears.py soumettre        # juillet-août 2000-2025, France métropolitaine
  uv run python scripts/30_lst_appeears.py statut
  uv run python scripts/30_lst_appeears.py telecharger --tache <task_id>
Réutilise l'authentification, l'appel à l'API et le téléchargement de scripts/17_ndvi_appeears.py (jeton dans .env,
jamais affiché). Les fichiers vont dans data/raw/nasa_appeears_lst/<task_id>/ (et non dans nasa_appeears/, que
scripts/18_ndvi_aggregate.py lit en entier) et sont inscrits au manifeste.
"""

import argparse
import importlib.util
import urllib.error

from atlas.download import ROOT

_spec = importlib.util.spec_from_file_location("ndvi", ROOT / "scripts" / "17_ndvi_appeears.py")
ndvi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ndvi)
ndvi.RAW = ROOT / "data" / "raw" / "nasa_appeears_lst"   # dossier de destination de ndvi.download()

YEARS = range(2000, 2026)
LAYERS = [{"product": "MOD11A2.061", "layer": "LST_Day_1km"},
          {"product": "MOD11A2.061", "layer": "QC_Day"}]


def submit() -> None:
    task = {"task_type": "area", "task_name": "atlas_lst_ja_2000_2025",
            "params": {"dates": [{"startDate": f"07-01-{y}", "endDate": f"08-31-{y}"} for y in YEARS],
                       "layers": LAYERS, "geo": ndvi.france_outline(),
                       "output": {"format": {"type": "geotiff"}, "projection": "geographic"}}}
    print("commande soumise :", ndvi.call("/task", "POST", task))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("soumettre")
    sub.add_parser("statut")
    d = sub.add_parser("telecharger")
    d.add_argument("--tache", required=True)
    a = p.parse_args()
    try:
        if a.cmd == "soumettre":
            submit()
        elif a.cmd == "statut":
            ndvi.status()
        else:
            ndvi.download(a.tache)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"AppEEARS : HTTP {e.code} {e.reason} — {e.read(300)!r}")


if __name__ == "__main__":
    main()
