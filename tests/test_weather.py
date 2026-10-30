"""Tests de l'agrégation temporelle (mois -> fenêtres de l'année de récolte)."""

import numpy as np
import pandas as pd
import pytest

from atlas.download import ROOT
from atlas.weather import MEAN_VARS, SUM_VARS, WINDOWS, harvest_year_windows, monthly


def synthetic_dep_month(years=(2009, 2010)):
    rows = []
    for y in years:
        for m in range(1, 13):
            row = {"dep_code": "01", "year": y, "month": m}
            row.update({v: float(m) for v in SUM_VARS})          # valeur = numéro du mois
            row.update({v: float(100 * (y - 2000) + m) for v in MEAN_VARS})
            rows.append(row)
    return pd.DataFrame(rows)


def test_autumn_uses_previous_year_and_sums_months():
    out = harvest_year_windows(synthetic_dep_month(), [2010]).iloc[0]
    assert out["dd_32_automne"] == 9 + 10 + 11          # sept-nov 2009
    assert out["dd_32_hiver"] == 12 + 1 + 2             # déc 2009 + jan-fév 2010
    assert out["dd_32_remplissage"] == 5 + 6


def test_means_are_weighted_by_days():
    out = harvest_year_windows(synthetic_dep_month(), [2010]).iloc[0]
    # mai 2010 (31 j) = 1005, juin 2010 (30 j) = 1006
    assert out["tmean_remplissage"] == pytest.approx((1005 * 31 + 1006 * 30) / 61)


def test_window_missing_if_a_month_is_missing():
    dm = synthetic_dep_month()
    dm = dm[~((dm.year == 2009) & (dm.month == 10))]
    out = harvest_year_windows(dm, [2010]).iloc[0]
    assert np.isnan(out["dd_32_automne"]) and np.isnan(out["tmean_automne"])
    assert out["dd_32_remplissage"] == 11


def test_windows_do_not_overlap():
    months = [m for w in WINDOWS.values() for m in w]
    assert len(months) == len(set(months))


def test_monthly_masks_only_the_incomplete_variable():
    dates = pd.date_range("2025-12-30", "2025-12-31")
    daily = pd.DataFrame({"LAMBX": 1, "LAMBY": 1, "date": dates})
    for v in SUM_VARS + MEAN_VARS:
        daily[v] = 1.0
    daily.loc[1, "dd_32"] = np.nan   # 31 décembre sans Tmin du lendemain
    m = monthly(daily).iloc[0]
    assert np.isnan(m["dd_32"]) and m["tmean"] == 1.0 and m["prec"] == 2.0


# --- Table réelle département × récolte (pondération surfacique) -----------------

HARVEST = ROOT / "data" / "processed" / "weather_dep_harvest_area.parquet"


@pytest.fixture(scope="module")
def harvest():
    if not HARVEST.exists():
        pytest.skip("exécuter scripts/05 puis 06")
    return pd.read_parquet(HARVEST)


def test_harvest_table_keys_and_completeness(harvest):
    assert not harvest.duplicated(["dep_code", "annee"]).any()
    assert harvest["dep_code"].nunique() == 96
    assert set(harvest["annee"]) == set(range(2010, 2026))
    assert harvest.drop(columns=["dep_code", "annee"]).notna().all().all()


def test_degree_days_decrease_with_threshold(harvest):
    for w in WINDOWS:
        cols = [f"dd_{b}_{w}" for b in [0, 28, 29, 30, 31, 32, 33, 34]]
        diffs = np.diff(harvest[cols].to_numpy(), axis=1)
        assert (diffs <= 1e-9).all(), w
    assert (harvest["hot_32_remplissage"] <= harvest["hot_30_remplissage"]).all()


def test_plausible_ranges(harvest):
    assert harvest["swi_dry_remplissage"].between(0, 61).all()       # mai + juin = 61 jours
    assert harvest["tmean_remplissage"].between(5, 25).all()
    assert (harvest["prec_printemps"] >= 0).all()
    assert harvest["swi_remplissage"].between(-0.1, 1.5).all()
