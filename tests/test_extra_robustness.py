"""Tests des données des robustesses R11-R14 (fenêtres par demi-mois, classes de température, altitude)."""

import numpy as np
import pandas as pd
import pytest

from atlas.download import ROOT

EXTRA = ROOT / "data" / "processed" / "weather_dep_harvest_wheat_extra.parquet"
PANEL = ROOT / "data" / "processed" / "panel_ble.parquet"
MONT = ROOT / "data" / "processed" / "dep_montagne.parquet"
ALT = ROOT / "data" / "processed" / "cell_altitude.parquet"


def load(path):
    if not path.exists():
        pytest.skip(f"{path.name} absent : exécuter scripts/12 et 13")
    return pd.read_parquet(path)


def test_bins_sum_to_61_days_and_are_nonnegative():
    e = load(EXTRA)
    bins = [c for c in e.columns if c.startswith("bin_")]
    assert len(bins) == 10
    assert (e[bins] >= -1e-9).all().all()
    assert np.allclose(e[bins].sum(axis=1), 61)


def test_semimonthly_windows_consistent_with_hot_days():
    """dd_32 > 0 dans une fenêtre exige des jours chauds : cohérence d'ordre de grandeur avec le panel."""
    e, p = load(EXTRA), load(PANEL)
    m = p.merge(e, on=["dep_code", "annee"], validate="one_to_one")
    assert (m["dd_32_m2s"] >= 0).all() and (m["dd_32_p2s"] >= 0).all()
    # La fenêtre décalée de +2 semaines inclut le cœur de l'été : exposition moyenne plus forte que mai-juin.
    assert m["dd_32_p2s"].mean() > m["dd_32_remplissage"].mean() > m["dd_32_m2s"].mean()
    # Les jours au-dessus de 33 °C correspondent à une exposition au-delà de 32 °C.
    assert ((m["bin_ge33"] > 0) <= (m["dd_32_remplissage"] > 0)).all()


def test_altitude_plausible_and_mountain_flags():
    alt, mont = load(ALT), load(MONT)
    assert alt["altitude_moy_m"].between(-50, 4810).all()
    assert mont["part_ble_600m"].between(0, 1 + 1e-9).all()
    assert set(mont.loc[mont["montagne_r13"], "dep_code"]) >= {"48", "15", "43"}   # Lozère, Cantal, Haute-Loire
    assert not mont.set_index("dep_code").loc[["28", "51", "80"], "montagne_r13"].any()  # Beauce, Marne, Somme
