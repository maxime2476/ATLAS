"""Masque blé tendre d'hiver à partir du RPG (parcelles, version 2.0, millésimes 2015-2017).

Règle d'agrégation :
- on ne retient que les parcelles CODE_CULTU = 'BTH' (blé tendre d'hiver) ;
- chaque parcelle est rattachée à la maille SIM qui contient son centroïde
  (arithmétique sur la grille régulière de 80 hm) et au département qui contient
  ce centroïde ; une parcelle (quelques ha) est petite devant une maille (6 400 ha) ;
- la surface retenue est SURF_PARC (ha, surface graphique déclarée).
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer

GRID_X0, GRID_Y0, STEP_HM = 600, 16170, 80  # origine et pas de la grille SIM (hm, Lambert II étendu)


def cell_of(x_m, y_m):
    """Centre de maille SIM (LAMBX, LAMBY en hm) contenant des points en mètres EPSG:27572."""
    x_hm, y_hm = np.asarray(x_m) / 100, np.asarray(y_m) / 100
    lambx = GRID_X0 + STEP_HM * np.round((x_hm - GRID_X0) / STEP_HM)
    lamby = GRID_Y0 + STEP_HM * np.round((y_hm - GRID_Y0) / STEP_HM)
    return lambx.astype(int), lamby.astype(int)


def wheat_parcels(shp_path, crop_code: str = "BTH") -> gpd.GeoDataFrame:
    """Parcelles d'une culture, lues avec un filtre attributaire (sans charger tout le RPG)."""
    return pyogrio.read_dataframe(shp_path, columns=["SURF_PARC", "CODE_CULTU"],
                                  where=f"CODE_CULTU = '{crop_code}'")


def wheat_area_by_cell_dep(parcels: gpd.GeoDataFrame, dep_27572: gpd.GeoDataFrame,
                           grid_cells: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Surface de blé (ha) par (maille, département) et tableau de contrôle."""
    cent = parcels.geometry.centroid  # en Lambert 93 (mètres), CRS projeté : centroïde valide
    to_grid = Transformer.from_crs(parcels.crs, dep_27572.crs, always_xy=True)
    x, y = to_grid.transform(cent.x.to_numpy(), cent.y.to_numpy())
    pts = gpd.GeoDataFrame({"surf_ha": parcels["SURF_PARC"].to_numpy()},
                           geometry=gpd.points_from_xy(x, y), crs=dep_27572.crs)
    pts["LAMBX"], pts["LAMBY"] = cell_of(x, y)
    joined = gpd.sjoin(pts, dep_27572[["dep_code", "geometrie"]], how="left", predicate="within")
    if joined.index.duplicated().any():
        raise RuntimeError("Un centroïde tombe dans plusieurs départements")
    known = grid_cells[["LAMBX", "LAMBY"]].assign(on_grid=True)
    # many_to_one : une maille dupliquée dans la grille doublerait les surfaces sans erreur.
    joined = joined.merge(known, on=["LAMBX", "LAMBY"], how="left", validate="many_to_one")
    # Les deux surfaces « hors » peuvent se recouvrir (point hors département et hors grille).
    control = {
        "parcelles": len(pts),
        "surface_ha": float(pts["surf_ha"].sum()),
        "hors_departement_ha": float(joined.loc[joined["dep_code"].isna(), "surf_ha"].sum()),
        "hors_grille_ha": float(joined.loc[joined["on_grid"].isna(), "surf_ha"].sum()),
    }
    ok = joined.dropna(subset=["dep_code"]).loc[lambda d: d["on_grid"].notna()]
    area = ok.groupby(["LAMBX", "LAMBY", "dep_code"], as_index=False)["surf_ha"].sum()
    return area, control


def rpg1_islands(shp_path, group_code: int = 2) -> gpd.GeoDataFrame:
    """Îlots RPG 1.0 (2007-2014) dont le groupe de cultures majoritaire vaut `group_code` (02 = maïs grain et
    ensilage). La version 1.0 n'a pas de champ de surface : SURF_PARC est la surface graphique de l'îlot (ha),
    pour réutiliser wheat_area_by_cell_dep. L'îlot entier est compté pour son groupe majoritaire."""
    isl = pyogrio.read_dataframe(shp_path, columns=["CODE_CULTU"], where=f"CODE_CULTU = {int(group_code)}")
    isl["SURF_PARC"] = isl.geometry.area / 1e4
    return isl
