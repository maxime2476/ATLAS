"""Tests synthétiques de trois transformations sans données réelles : Tmin du lendemain (SIM),
rattachement des parcelles aux mailles et aux départements (RPG), niveau d'un arrêté (VigiEau)."""

import importlib.util

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from atlas.download import ROOT
from atlas.rpg import cell_of, wheat_area_by_cell_dep
from atlas.weather import COLUMNS, read_year


def write_sim(path, rows):
    """Petit fichier au format SIM2 (séparateur ;, DATE en AAAAMMJJ)."""
    cols = [c.strip() for c in COLUMNS.split(",")]
    df = pd.DataFrame(rows, columns=["LAMBX", "LAMBY", "DATE", "TINF_H"])
    for c in cols:
        if c not in df:
            df[c] = 1.0
    df[cols].to_csv(path, sep=";", index=False)


def test_read_year_next_day_tmin_and_december_31(tmp_path):
    # Deux mailles, trois derniers jours de 2009, lignes volontairement dans le désordre.
    write_sim(tmp_path / "y2009.csv", [
        (680, 16170, 20091231, 3.0), (600, 16170, 20091230, 2.0), (600, 16170, 20091229, 1.0),
        (680, 16170, 20091229, 5.0), (600, 16170, 20091231, 4.0), (680, 16170, 20091230, 6.0),
    ])
    write_sim(tmp_path / "y2010.csv", [
        (600, 16170, 20100101, 10.0), (680, 16170, 20100101, 20.0),
        (600, 16170, 20100102, 99.0), (680, 16170, 20100102, 99.0),   # le 2 janvier ne doit pas servir
    ])
    df = read_year(tmp_path / "y2009.csv", tmp_path / "y2010.csv")
    got = df.set_index(["LAMBX", "LAMBY", "DATE"])["tmin_next"]
    # Tmin du lendemain dans la même maille, jamais celle d'une autre maille.
    assert got[(600, 16170, 20091229)] == 2.0 and got[(600, 16170, 20091230)] == 4.0
    assert got[(680, 16170, 20091229)] == 6.0 and got[(680, 16170, 20091230)] == 3.0
    # 31 décembre : Tmin du 1er janvier suivant, maille par maille.
    assert got[(600, 16170, 20091231)] == 10.0 and got[(680, 16170, 20091231)] == 20.0
    assert len(df) == 6

    # Sans fichier suivant, le 31 décembre reste manquant (et non une valeur inventée).
    alone = read_year(tmp_path / "y2009.csv").set_index(["LAMBX", "LAMBY", "DATE"])["tmin_next"]
    assert np.isnan(alone[(600, 16170, 20091231)]) and alone[(600, 16170, 20091230)] == 4.0


def test_cell_of_grid_arithmetic():
    # Origine 600 / 16170 hm, pas de 80 hm : un point est rattaché au centre de maille le plus proche.
    x, y = cell_of([60000, 63000, 64500], [1617000, 1620000, 1612500])
    assert x.tolist() == [600, 600, 680] and y.tolist() == [16170, 16170, 16090]


def test_wheat_area_by_cell_dep_synthetic():
    crs = "EPSG:27572"   # même CRS pour parcelles et départements : la reprojection est l'identité
    dep = gpd.GeoDataFrame({"dep_code": ["01", "02"]},
                           geometry=[box(56000, 1609000, 72000, 1625000), box(72000, 1609000, 88000, 1625000)],
                           crs=crs).rename_geometry("geometrie")
    centers = [(60000, 1617000), (61000, 1618000),    # dép. 01, maille (600, 16170)
               (76000, 1617000),                       # dép. 02, maille (760, 16170)
               (100000, 1617000),                      # hors de tout département
               (60000, 1610500)]                       # dép. 01, maille (600, 16090) absente de la grille
    surf = [2.0, 3.0, 4.0, 5.0, 7.0]
    parcels = gpd.GeoDataFrame({"SURF_PARC": surf, "CODE_CULTU": "BTH"},
                               geometry=[box(x - 50, y - 50, x + 50, y + 50) for x, y in centers], crs=crs)
    # La maille (1000, 16170) du point hors département est sur la grille : sinon ce point serait compté à la
    # fois « hors département » et « hors grille » (les deux contrôles peuvent se recouvrir).
    grid = pd.DataFrame({"LAMBX": [600, 760, 1000], "LAMBY": [16170, 16170, 16170]})

    area, ctl = wheat_area_by_cell_dep(parcels, dep, grid)
    got = area.set_index(["LAMBX", "LAMBY", "dep_code"])["surf_ha"].to_dict()
    assert got == {(600, 16170, "01"): 5.0, (760, 16170, "02"): 4.0}
    assert ctl == {"parcelles": 5, "surface_ha": 21.0, "hors_departement_ha": 5.0, "hors_grille_ha": 7.0}
    # Conservation : surface rattachée + hors département + hors grille = surface totale.
    assert area["surf_ha"].sum() + ctl["hors_departement_ha"] + ctl["hors_grille_ha"] == ctl["surface_ha"]


def test_decree_level_takes_most_severe_zone():
    spec = importlib.util.spec_from_file_location("vigieau", ROOT / "scripts" / "23_vigieau_indicators.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.decree_level("crise") == 4
    assert mod.decree_level('["vigilance","alerte_renforcee","alerte"]') == 3
    assert mod.decree_level('["vigilance","vigilance"]') == 1
    # Niveau manquant ou inconnu : 0, donc l'arrêté n'est pas compté (sous-estimation documentée).
    assert mod.decree_level(np.nan) == 0 and mod.decree_level("[]") == 0 and mod.decree_level("inconnu") == 0
