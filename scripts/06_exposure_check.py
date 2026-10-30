"""Étape 6 : fenêtres de l'année de récolte et comptage obligatoire de l'exposition thermique.

Usage : uv run python scripts/06_exposure_check.py [--weights area|wheat] [--first-year 1990]
Entrées : data/processed/weather_dep_month_<weights>.parquet, data/interim/saa_cop_departements_long.parquet
Sorties : data/processed/weather_dep_harvest_<weights>[_<first-year>].parquet, tableau imprimé
(période principale 2010-2025 ; --first-year 1990 pour la robustesse sur période longue ; --first-year 1959
pour la série blé longue de la phase 4 bis)

Applique la règle de repli fixée (N_eff < 4 -> 30 °C).
Aucune régression du rendement sur la météo n'est estimée ici.
"""

import argparse

import numpy as np
import pandas as pd

from atlas.download import ROOT
from atlas.weather import harvest_year_windows

PROC = ROOT / "data" / "processed"
SAA = ROOT / "data" / "interim" / "saa_cop_departements_long.parquet"


def wheat_population(saa: pd.DataFrame) -> list[str]:
    """Départements métropolitains avec une surface moyenne 2010-2012 de blé tendre d'hiver ≥ 1000 ha."""
    w = saa[(saa["culture_code"] == "01") & saa["metropole"] & saa["annee"].between(2010, 2012)]
    ref = w.groupby("dep_code")["surface_ha"].mean()
    return sorted(ref[ref >= 1000].index)


def twoway_residuals(df: pd.DataFrame, col: str) -> pd.Series:
    """x - moyenne département - moyenne année + moyenne générale (panel équilibré)."""
    x = df[col]
    return (x - df.groupby("dep_code")[col].transform("mean")
            - df.groupby("annee")[col].transform("mean") + x.mean())


def exposure_table(panel: pd.DataFrame, col: str) -> tuple[pd.DataFrame, float]:
    r = twoway_residuals(panel, col)
    by_year = panel.assign(r2=r ** 2).groupby("annee").agg(
        n_dep_expose=(col, lambda s: int((s > 0.5).sum())),  # > 0,5 °C·jour : exposition non négligeable
        moyenne=(col, "mean"), maximum=(col, "max"), ss_resid=("r2", "sum"))
    by_year["part_variance"] = by_year["ss_resid"] / by_year["ss_resid"].sum()
    n_eff = 1 / (by_year["part_variance"] ** 2).sum()
    return by_year, n_eff


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default="area", choices=["area", "wheat"])
    parser.add_argument("--first-year", type=int, default=2010)
    args = parser.parse_args()
    years = list(range(args.first_year, 2026))
    suffix = "" if args.first_year == 2010 else f"_{args.first_year}"

    dep_month = pd.read_parquet(PROC / f"weather_dep_month_{args.weights}.parquet")
    harvest = harvest_year_windows(dep_month, years)
    harvest.to_parquet(PROC / f"weather_dep_harvest_{args.weights}{suffix}.parquet", index=False)

    saa = pd.read_parquet(SAA)
    pop = wheat_population(saa)
    panel = harvest[harvest["dep_code"].isin(pop)].copy()
    if len(panel) != len(pop) * len(years):
        raise RuntimeError("panel météo non équilibré")
    print(f"pondération : {args.weights} | population : {len(pop)} départements × {len(years)} récoltes = {len(panel)}")

    results = {}
    for b in [28, 29, 30, 31, 32, 33, 34]:
        _, n_eff = exposure_table(panel, f"dd_{b}_remplissage")
        results[b] = n_eff
    print("N_eff (mai-juin) par seuil :", {b: round(v, 2) for b, v in results.items()})

    for b in [32, 30]:
        table, n_eff = exposure_table(panel, f"dd_{b}_remplissage")
        print(f"\n== Degrés-jours > {b} °C en mai-juin (dd_{b}_remplissage), °C·jour")
        print(table.round({"moyenne": 2, "maximum": 1, "ss_resid": 1, "part_variance": 3}).to_string())
        print(f"N_eff = {n_eff:.2f}")

    if args.first_year != 2010:
        print("\nPériode longue : MDE et règle non recalculés (la règle porte sur 2010-2025).")
        return
    # Effet minimal détectable (informatif) : écart-type résiduel du log-rendement après les deux effets fixes.
    y = saa[(saa["culture_code"] == "01") & saa["dep_code"].isin(pop)][["dep_code", "annee", "rendement_q_ha"]]
    y = y.assign(log_y=np.log(y["rendement_q_ha"]))
    if not (len(y) == len(panel) and y["log_y"].notna().all()):
        raise RuntimeError("rendements manquants ou lignes perdues dans la jointure")
    e = twoway_residuals(y, "log_y")
    sigma = np.sqrt((e ** 2).sum() / (len(y) - len(pop) - len(years) + 1))
    print(f"\nσ résiduel du log-rendement (effets fixes seuls) : {sigma:.4f}")
    for b in [32, 30]:
        r = twoway_residuals(panel, f"dd_{b}_remplissage")
        se = sigma / np.sqrt((r ** 2).sum())
        mde = 2.8 * se
        print(f"  seuil {b} °C : MDE₈₀ ≈ {mde:.4f} log-points par °C·jour "
              f"soit {100 * (np.exp(10 * mde) - 1):.1f} % pour +10 °C·jour (borne basse)")

    chosen = 32 if results[32] >= 4 else 30
    print(f"\nRÈGLE : N_eff(32) = {results[32]:.2f} -> seuil retenu = {chosen} °C")


if __name__ == "__main__":
    main()
