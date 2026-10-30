"""Tests des panels d'analyse (clés, équilibre, plages, cohérence entre panels)."""

import numpy as np
import pandas as pd
import pytest

from atlas.download import ROOT

PANEL = ROOT / "data" / "processed" / "panel_ble.parquet"
LONG = ROOT / "data" / "processed" / "panel_ble_long.parquet"
WINDOWS = ["automne", "hiver", "printemps", "remplissage"]


def load(path):
    if not path.exists():
        pytest.skip("exécuter scripts/09_build_panel.py")
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def panel():
    return load(PANEL)


@pytest.fixture(scope="module")
def long():
    return load(LONG)


def test_key_and_balance(panel, long):
    for df, years in [(panel, range(2010, 2026)), (long, range(1990, 2026))]:
        assert not df.duplicated(["dep_code", "annee"]).any()
        assert df["dep_code"].nunique() == 85
        assert (df.groupby("dep_code")["annee"].apply(set) == set(years)).all()


def test_no_missing_in_main_panel(panel):
    cols = ["rendement_q_ha", "log_rendement", "surface_ref_ha"] + \
           [c for c in panel.columns if c.endswith(tuple(WINDOWS))]
    assert panel[cols].notna().all().all()


def test_population_and_fixed_weights(panel):
    assert (panel["surface_ref_ha"] >= 1000).all()
    assert (panel.groupby("dep_code")["surface_ref_ha"].nunique() == 1).all()  # poids fixes


def test_flags_and_sources(panel, long):
    assert set(panel.loc[panel["provisoire"], "annee"]) == {2025}
    assert set(long.loc[long["annee"] < 2010, "source_rendement"]) == {"Schauberger_RAW"}
    assert set(long.loc[long["annee"] >= 2010, "source_rendement"]) == {"SAA"}


def test_yield_ranges_and_log(panel, long):
    for df in (panel, long):
        assert df["rendement_q_ha"].between(15, 130).all()
        assert np.allclose(np.exp(df["log_rendement"]), df["rendement_q_ha"])


def test_gdd_plus_edd_equals_dd0(panel):
    for w in WINDOWS:
        assert np.allclose(panel[f"gdd_0_32_{w}"] + panel[f"dd_32_{w}"], panel[f"dd_0_{w}"])


def test_long_panel_matches_main_panel_after_2010(panel, long):
    """La partie 2010-2025 du panel long est identique au panel principal (rendements et météo)."""
    cols = ["rendement_q_ha", "dd_32_remplissage", "swi_remplissage", "prec_printemps", "dd_0_automne"]
    a = panel.set_index(["dep_code", "annee"])[cols]
    b = long[long["annee"] >= 2010].set_index(["dep_code", "annee"])[cols].loc[a.index]
    assert np.allclose(a.to_numpy(), b.to_numpy())


def test_main_sample_is_quality_status_1(panel):
    s = panel.drop_duplicates("dep_code").set_index("dep_code")
    assert s["echantillon_principal"].sum() == 83
    assert (s.loc[s["echantillon_principal"], "statut_qualite"] == "1").all()
    assert set(s.index[~s["echantillon_principal"]]) == {"90", "91"}


def test_production_is_area_times_yield(panel):
    ratio = panel["production_q"] / (panel["surface_ha"] * panel["rendement_q_ha"])
    assert ratio.between(0.99, 1.01).all()


def test_heat_indicators_consistent(panel):
    for w in WINDOWS:
        assert (panel[f"hot_32_{w}"] <= panel[f"hot_30_{w}"]).all()
        assert ((panel[f"dd_32_{w}"] > 0) <= (panel[f"hot_30_{w}"] > 0)).all()  # pas de dd_32 sans jour > 30 °C
        assert (panel[f"tmin_{w}"] <= panel[f"tmean_{w}"]).all() and (panel[f"tmean_{w}"] <= panel[f"tmax_{w}"]).all()
