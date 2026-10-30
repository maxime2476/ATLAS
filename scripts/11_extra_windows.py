"""Étape 11 : fenêtre alternative de remplissage (mai-juillet) pour la robustesse R10 de la phase 4.

Usage : uv run python scripts/11_extra_windows.py
Sortie : data/processed/weather_dep_harvest_wheat_mjj.parquet
         (dep_code, annee, dd_0_mjj, dd_32_mjj, gdd_0_32_mjj), masque blé, récoltes 2010-2025.
Fenêtre construite à partir des mois complets. Les fenêtres décalées de ±2 semaines (R11, R12), qui demandent un
calcul par demi-mois, sont produites par scripts/12_build_semimonthly.py.
"""

import pandas as pd

from atlas.weather import harvest_year_windows
from atlas.download import ROOT

PROC = ROOT / "data" / "processed"


def main() -> None:
    dep_month = pd.read_parquet(PROC / "weather_dep_month_wheat.parquet")
    # Fenêtre unique : mai à juillet de l'année de récolte t.
    h = harvest_year_windows(dep_month, range(2010, 2026), windows={"mjj": [(0, 5), (0, 6), (0, 7)]})
    out = h[["dep_code", "annee", "dd_0_mjj", "dd_32_mjj"]].copy()
    out["gdd_0_32_mjj"] = out["dd_0_mjj"] - out["dd_32_mjj"]
    if out.isna().any().any() or out.duplicated(["dep_code", "annee"]).any():
        raise RuntimeError("valeurs manquantes ou doublons (dep_code, annee)")
    out.to_parquet(PROC / "weather_dep_harvest_wheat_mjj.parquet", index=False)
    print(f"{len(out)} lignes ; dd_32_mjj moyenne {out.dd_32_mjj.mean():.2f}, max {out.dd_32_mjj.max():.1f}")


if __name__ == "__main__":
    main()
