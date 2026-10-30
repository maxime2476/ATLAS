"""Étape 14 : variables de prévision aux dates du 1er juin et du 1er juillet (spécification de la phase 5).

Usage : uv run python scripts/14_forecast_features.py
Entrées : data/processed/weather_dep_month_wheat.parquet (1989-2025), data/processed/panel_ble_long.parquet
Sortie : data/processed/forecast_features.parquet (département × récolte 1990-2025)

Fenêtres disponibles à chaque date (aucune information postérieure à la date de prévision) :
  1er juin    : automne (sept.-nov. t-1), hiver (déc.-févr.), printemps (mars-avril), mai
  1er juillet : automne, hiver, printemps, remplissage (mai-juin)
"""

import pandas as pd

from atlas.download import ROOT
from atlas.weather import WINDOWS, harvest_year_windows

PROC = ROOT / "data" / "processed"
VARS = ["gdd_0_32", "dd_32", "hot_30", "prec", "etp", "swi", "swi_dry", "tmin", "tmax"]
FC_WINDOWS = {**WINDOWS, "mai": [(0, 5)]}


def main() -> None:
    dep_month = pd.read_parquet(PROC / "weather_dep_month_wheat.parquet")
    h = harvest_year_windows(dep_month, range(1990, 2026), windows=FC_WINDOWS)
    for w in FC_WINDOWS:
        h[f"gdd_0_32_{w}"] = h[f"dd_0_{w}"] - h[f"dd_32_{w}"]
    # 9 variables × 5 fenêtres, plus dd_0_automne requise par L1 (spécification M1 de la phase 4).
    keep = [f"{v}_{w}" for w in FC_WINDOWS for v in VARS] + ["dd_0_automne"]
    panel = pd.read_parquet(PROC / "panel_ble_long.parquet")[
        ["dep_code", "annee", "log_rendement", "rendement_q_ha", "surface_ref_ha", "echantillon_principal",
         "source_rendement", "provisoire"]]
    out = panel.merge(h[["dep_code", "annee"] + keep], on=["dep_code", "annee"], how="left", validate="one_to_one")
    if not (out[keep].notna().all().all() and len(out) == len(panel)):
        raise RuntimeError("variables manquantes ou lignes perdues")
    out.to_parquet(PROC / "forecast_features.parquet", index=False)
    print(f"{len(out)} lignes, {len(keep)} variables météo ({len(VARS)} × {len(FC_WINDOWS)} fenêtres)")


if __name__ == "__main__":
    main()
