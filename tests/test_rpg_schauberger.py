"""Tests du masque blé (RPG) et de la lecture des rendements Schauberger."""

import numpy as np
import pandas as pd
import pytest

from atlas.download import ROOT
from atlas.rpg import cell_of
from atlas.schauberger import normalize_name

GRID = ROOT / "data" / "raw" / "meteofrance_sim" / "coordonnees_grille_safran_lambert-2-etendu.csv"
WHEAT_AREA = ROOT / "data" / "processed" / "wheat_area_cell_dep_rpg.parquet"
WEIGHTS_WHEAT = ROOT / "data" / "processed" / "weights_cell_dep_wheat.parquet"
SAA = ROOT / "data" / "interim" / "saa_cop_departements_long.parquet"


def test_cell_of_returns_the_centre_for_points_inside_the_cell():
    # Centre (600, 24010) hm ; un point à 3,9 km du centre reste dans la maille, à 4,1 km il en sort.
    cx, cy = 600 * 100, 24010 * 100
    assert cell_of(cx + 3900, cy - 3900) == (600, 24010)
    assert cell_of(cx + 4100, cy)[0] == 680


def test_cell_of_maps_real_grid_centres_onto_themselves():
    if not GRID.exists():
        pytest.skip("grille SIM absente")
    g = pd.read_csv(GRID, sep=";", decimal=",").iloc[:, :2]
    x, y = cell_of(g.iloc[:, 0].to_numpy() * 100, g.iloc[:, 1].to_numpy() * 100)
    assert (x == g.iloc[:, 0].to_numpy()).all() and (y == g.iloc[:, 1].to_numpy()).all()


@pytest.mark.parametrize("raw, norm", [("Côtes-d'Armor", "cotesdarmor"), ("Cotes_d_Armor", "cotesdarmor"),
                                       ("Seine-Saint-Denis", "seinesaintdenis")])
def test_normalize_name(raw, norm):
    assert normalize_name(raw) == norm


def test_wheat_weights_sum_to_one():
    if not WEIGHTS_WHEAT.exists():
        pytest.skip("exécuter scripts/07_build_wheat_mask.py")
    w = pd.read_parquet(WEIGHTS_WHEAT)
    assert np.allclose(w.groupby("dep_code")["w_wheat"].sum(), 1.0)
    assert (w["wheat_ha"] > 0).all()
    assert not w.duplicated(["LAMBX", "LAMBY", "dep_code"]).any()


def test_rpg_wheat_area_consistent_with_saa():
    """Surface BTH du RPG ≈ surface SAA de blé tendre d'hiver (contrôle de mesure du masque)."""
    if not (WHEAT_AREA.exists() and SAA.exists()):
        pytest.skip("exécuter scripts/03 et 07")
    rpg = pd.read_parquet(WHEAT_AREA).groupby("millesime")["surf_ha"].sum()
    s = pd.read_parquet(SAA)
    saa = s[(s.culture_code == "01") & s.metropole & s.annee.between(2015, 2017)].groupby("annee")["surface_ha"].sum()
    ratio = rpg.to_numpy() / saa.to_numpy()
    assert np.all((ratio > 0.97) & (ratio < 1.03))
