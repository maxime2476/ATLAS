"""Tests de lecture des fichiers SIM bruts (rapides : en-têtes et grille).

Les contrôles de couverture complets (jours × mailles) sont plus longs (~80 s) et
sont lancés par : uv run python scripts/02_check_sim.py --all-years
"""

import gzip

import duckdb
import pytest

from atlas.download import ROOT

SIM_DIR = ROOT / "data" / "raw" / "meteofrance_sim"
EXPECTED_HEADER = (
    "LAMBX;LAMBY;DATE;PRENEI;PRELIQ;T;FF;Q;DLI;SSI;HU;EVAP;ETP;PE;SWI;SSWI_10J;DRAINC;RUNC;"
    "RESR_NEIGE;RESR_NEIGE6;HTEURNEIGE;HTEURNEIGE6;HTEURNEIGEX;SNOW_FRAC;ECOULEMENT;"
    "WG_RACINE;WGI_RACINE;TINF_H;TSUP_H"
)
YEARS = range(2009, 2026)  # septembre 2009 nécessaire pour les semis de la récolte 2010


@pytest.mark.parametrize("year", YEARS)
def test_sim_file_present_with_expected_header(year):
    path = SIM_DIR / f"QUOT_SIM2_{year}.csv.gz"
    if not path.exists():
        pytest.skip(f"{path.name} absent : exécuter scripts/01_download_raw.py --sim-years 2009-2025")
    with gzip.open(path, "rt", encoding="latin-1") as f:
        header, first = f.readline().strip(), f.readline().strip()
    assert header == EXPECTED_HEADER
    assert first.split(";")[2].startswith(str(year))  # première date dans l'année du fichier


def test_grid_file_has_9892_unique_cells():
    path = SIM_DIR / "coordonnees_grille_safran_lambert-2-etendu.csv"
    if not path.exists():
        pytest.skip("grille SIM absente")
    n, n_unique, lat_min, lat_max = duckdb.sql(f"""
        SELECT count(*), count(DISTINCT ("LAMBX (hm)", "LAMBY (hm)")), min(LAT_DG), max(LAT_DG)
        FROM read_csv('{path}', delim=';', header=true, decimal_separator=',')""").fetchone()
    assert n == n_unique == 9892
    assert 41 < lat_min and lat_max < 52  # France métropolitaine (Corse incluse)
