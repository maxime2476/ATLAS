"""Étape 25 : masque maïs 2008 (RPG 1.0, îlots du groupe 02) et météo juillet-août associée (Q1-R9).

Usage : uv run python scripts/25_build_maize_mask_2008.py
Entrées : data/raw/ign_rpg/RPG_1-0__SHP_LAMB93_<région>_2008-01-01.7z (4 régions, --rpg1 2008)
Sorties :
  data/processed/weights_cell_dep_maize2008.parquet
  data/processed/weather_dep_harvest_maize2008.parquet   (dep_code, annee, dd_32_ja, swi_ja ; 2000-2025)
Les couches extraites (data/interim/rpg1/) sont supprimées à la fin (régénérables depuis raw/).
"""

import subprocess

import pandas as pd

from atlas.download import ROOT
from atlas.rpg import rpg1_islands, wheat_area_by_cell_dep
from atlas.spatial import departements, weighted_mean
from atlas.weather import MEAN_VARS, SUM_VARS, harvest_year_windows

RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim" / "rpg1"
PROC = ROOT / "data" / "processed"
REGIONS = ["R24", "R27", "R44", "R84"]


def main() -> None:
    dep = departements(RAW / "ign_admin_express" / "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    grid = pd.read_csv(RAW / "meteofrance_sim" / "coordonnees_grille_safran_lambert-2-etendu.csv",
                       sep=";", decimal=",").iloc[:, :2]
    grid.columns = ["LAMBX", "LAMBY"]
    parts = []
    for reg in REGIONS:
        out = INTERIM / reg
        out.mkdir(parents=True, exist_ok=True)
        archive = RAW / "ign_rpg" / f"RPG_1-0__SHP_LAMB93_{reg}_2008-01-01.7z"
        subprocess.run(["7z", "e", "-y", "-bso0", "-bsp0", str(archive), f"-o{out}", "*/ILOTS_ANONYMES.*", "-r"],
                       check=True)
        area, ctl = wheat_area_by_cell_dep(rpg1_islands(out / "ILOTS_ANONYMES.shp"), dep, grid)
        print(f"{reg} : {ctl['parcelles']:,} îlots groupe 02, {ctl['surface_ha'] / 1e3:.0f} kha ; "
              f"hors département {ctl['hors_departement_ha']:.0f} ha, hors grille {ctl['hors_grille_ha']:.0f} ha")
        parts.append(area)
        # Suppression limitée aux fichiers extraits par 7z (le dossier n'est retiré que s'il est vide).
        for f in out.glob("ILOTS_ANONYMES.*"):
            f.unlink()
        out.rmdir()
    INTERIM.rmdir()
    # Un îlot proche d'une frontière régionale peut tomber dans un département d'une autre région : on somme.
    area = pd.concat(parts).groupby(["LAMBX", "LAMBY", "dep_code"], as_index=False)["surf_ha"].sum()
    area["w_maize2008"] = area["surf_ha"] / area.groupby("dep_code")["surf_ha"].transform("sum")
    area.to_parquet(PROC / "weights_cell_dep_maize2008.parquet", index=False)

    cell_month = pd.read_parquet(ROOT / "data" / "interim" / "weather_cell_month.parquet")
    dm = weighted_mean(cell_month, area, SUM_VARS + MEAN_VARS, "w_maize2008", ["year", "month"])
    h = harvest_year_windows(dm, range(2000, 2026), windows={"ja": [(0, 7), (0, 8)]})
    h = h[["dep_code", "annee", "dd_32_ja", "swi_ja"]]
    h.to_parquet(PROC / "weather_dep_harvest_maize2008.parquet", index=False)
    print(f"{h.dep_code.nunique()} départements × {h.annee.nunique()} années ; valeurs manquantes : {int(h.isna().sum().sum())}")


if __name__ == "__main__":
    main()
