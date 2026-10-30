"""Correspondance spatiale entre la grille SIM (8 km) et les départements.

Choix retenus :
- CRS de travail : EPSG:27572 (NTF Paris / Lambert zone II étendu), celui de la grille SIM ;
  les coordonnées LAMBX/LAMBY sont en hectomètres, centre de maille.
- Une maille est le carré de 8 km centré sur son point ; c'est une approximation de la
  maille réelle, cohérente avec le pas observé de 80 hm dans les deux directions.
- Poids d'une maille dans un département = surface de l'intersection maille ∩ département
  (prédicat : intersection de polygones), normalisée pour sommer à 1 par département.
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

GRID_CRS = "EPSG:27572"
CELL_SIZE_M = 8_000


def sim_cells(grid_csv) -> gpd.GeoDataFrame:
    """Polygones des 9 892 mailles SIM, avec leurs identifiants LAMBX/LAMBY (hm)."""
    g = pd.read_csv(grid_csv, sep=";", decimal=",")
    g.columns = ["LAMBX", "LAMBY", "lat", "lon"]
    half = CELL_SIZE_M / 2
    geoms = [box(x * 100 - half, y * 100 - half, x * 100 + half, y * 100 + half)
             for x, y in zip(g["LAMBX"], g["LAMBY"])]
    return gpd.GeoDataFrame(g[["LAMBX", "LAMBY"]], geometry=geoms, crs=GRID_CRS)


def departements(admin_parquet, metropole_only: bool = True) -> gpd.GeoDataFrame:
    """Contours ADMIN EXPRESS (WGS84) reprojetés dans le CRS de la grille."""
    dep = gpd.read_parquet(admin_parquet)[["code_insee", "nom_officiel", "geometrie"]]
    dep = dep.rename(columns={"code_insee": "dep_code", "nom_officiel": "dep_nom"})
    dep = dep.set_geometry("geometrie")
    if metropole_only:
        dep = dep[dep["dep_code"].str.len() == 2]  # les DROM ont des codes à 3 caractères
    return dep.to_crs(GRID_CRS)


def area_weights(cells: gpd.GeoDataFrame, dep: gpd.GeoDataFrame) -> pd.DataFrame:
    """Table (LAMBX, LAMBY, dep_code, surface d'intersection, poids normalisé)."""
    inter = gpd.overlay(cells, dep[["dep_code", "geometrie"]], how="intersection",
                        keep_geom_type=True)
    inter["area_m2"] = inter.geometry.area
    inter = inter[inter["area_m2"] > 0]
    w = inter.groupby(["LAMBX", "LAMBY", "dep_code"], as_index=False)["area_m2"].sum()
    w["w_area"] = w["area_m2"] / w.groupby("dep_code")["area_m2"].transform("sum")
    return w.sort_values(["dep_code", "LAMBX", "LAMBY"]).reset_index(drop=True)


def weighted_mean(cell_values: pd.DataFrame, weights: pd.DataFrame, value_cols: list[str],
                  weight_col: str = "w_area", keys: list[str] | None = None) -> pd.DataFrame:
    """Moyenne pondérée par département des valeurs de maille.

    cell_values : colonnes LAMBX, LAMBY, `keys` (ex. année, mois) et `value_cols`.
    Les poids sont renormalisés sur les mailles effectivement présentes.
    Une valeur de maille manquante rend la moyenne du département manquante
    (pas de moyenne silencieuse sur une partie du territoire).
    """
    keys = keys or []
    m = cell_values.merge(weights[["LAMBX", "LAMBY", "dep_code", weight_col]],
                          on=["LAMBX", "LAMBY"], how="inner", validate="many_to_many")
    for c in value_cols:
        m[c] = m[c] * m[weight_col]
    g = m.groupby(["dep_code"] + keys)
    out = g[value_cols + [weight_col]].sum()
    out[value_cols] = out[value_cols].div(out[weight_col], axis=0)
    complete = g[value_cols].count().eq(g.size(), axis=0)
    out[value_cols] = out[value_cols].where(complete)
    return out.drop(columns=weight_col).reset_index()
