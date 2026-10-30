"""Tests de la correspondance grille SIM -> départements."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from atlas.download import ROOT
from atlas.spatial import GRID_CRS, area_weights, weighted_mean

WEIGHTS = ROOT / "data" / "processed" / "weights_cell_dep_area.parquet"


def test_area_weights_on_artificial_case():
    """Deux mailles de 8 km, un département qui couvre toute la première et un quart de la seconde."""
    cells = gpd.GeoDataFrame({"LAMBX": [40, 120], "LAMBY": [40, 40]},
                             geometry=[box(0, 0, 8000, 8000), box(8000, 0, 16000, 8000)], crs=GRID_CRS)
    dep = gpd.GeoDataFrame({"dep_code": ["99"]}, geometry=[box(0, 0, 10000, 8000)], crs=GRID_CRS)
    dep = dep.rename_geometry("geometrie")
    w = area_weights(cells, dep).set_index("LAMBX")
    assert w.loc[40, "area_m2"] == pytest.approx(64e6)
    assert w.loc[120, "area_m2"] == pytest.approx(16e6)
    assert w.loc[40, "w_area"] == pytest.approx(0.8)
    assert w["w_area"].sum() == pytest.approx(1.0)


def test_weighted_mean_known_values_and_nan_propagation():
    weights = pd.DataFrame({"LAMBX": [1, 2, 3], "LAMBY": [0, 0, 0],
                            "dep_code": ["A", "A", "B"], "w_area": [0.75, 0.25, 1.0]})
    values = pd.DataFrame({"LAMBX": [1, 2, 3, 1, 2, 3], "LAMBY": [0] * 6,
                           "month": [1, 1, 1, 2, 2, 2],
                           "x": [10.0, 20.0, 5.0, 10.0, np.nan, 7.0]})
    out = weighted_mean(values, weights, ["x"], keys=["month"]).set_index(["dep_code", "month"])["x"]
    assert out[("A", 1)] == pytest.approx(12.5)
    assert np.isnan(out[("A", 2)])       # une maille manquante -> département manquant
    assert out[("B", 2)] == pytest.approx(7.0)


@pytest.fixture(scope="module")
def weights():
    if not WEIGHTS.exists():
        pytest.skip("poids absents : exécuter scripts/04_build_spatial_weights.py")
    return pd.read_parquet(WEIGHTS)


def test_real_weights_cover_96_departements_and_sum_to_one(weights):
    assert weights["dep_code"].nunique() == 96
    sums = weights.groupby("dep_code")["w_area"].sum()
    assert np.allclose(sums, 1.0)
    assert not weights.duplicated(["LAMBX", "LAMBY", "dep_code"]).any()
    assert (weights["area_m2"] <= 64e6 * (1 + 1e-9)).all()  # une intersection ne dépasse pas une maille
