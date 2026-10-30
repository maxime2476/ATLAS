"""Intégrité des données brutes : chaque fichier présent doit correspondre au manifeste.

Détecte une corruption, une modification manuelle ou le remplacement d'un fichier
SIM révisé par Météo-France sans mise à jour tracée du manifeste.
Lecture d'environ 50 Go : environ deux minutes (un test par fichier du manifeste, plus un test de doublons).
"""

import csv

import pytest

from atlas.download import ROOT, sha256_of_file

MANIFEST = ROOT / "docs" / "manifest_raw.csv"
with open(MANIFEST, newline="") as f:
    ROWS = list(csv.DictReader(f))


def test_manifest_has_no_duplicate_files():
    files = [r["file"] for r in ROWS]
    assert len(files) == len(set(files))


@pytest.mark.parametrize("row", ROWS, ids=[r["file"].rsplit("/", 1)[1] for r in ROWS])
def test_raw_file_matches_manifest(row):
    path = ROOT / row["file"]
    if not path.exists():
        pytest.skip(f"{row['file']} absent (non téléchargé)")
    assert path.stat().st_size == int(row["size_bytes"])
    assert sha256_of_file(path) == row["sha256"]


# Fichiers de data/raw qui ne sont pas des téléchargements contrôlés par le manifeste (documentés dans data/README.md) :
# notices README, cache Crossref de la vérification bibliographique (script 47), journaux de commande des portails
# DRIAS écrits par les scripts 37 et 41 (fenêtres TRACC relevées sur le portail : copie versionnée
# dans reports/tables/phase7_drias_fenetres_tracc.csv).
HORS_MANIFESTE = {"data/raw/drias/commandes.csv", "data/raw/drias/fenetres_tracc.csv",
                  "data/raw/drias_eau/commandes.csv"}


def test_raw_files_outside_manifest_are_documented():
    raw = ROOT / "data" / "raw"
    if not raw.exists():
        pytest.skip("data/raw absent")
    listed = {r["file"] for r in ROWS}
    extra = sorted(str(p.relative_to(ROOT)) for p in raw.rglob("*") if p.is_file())
    extra = [f for f in extra if f not in listed and not f.endswith("README.md")
             and not f.startswith("data/raw/bib_metadata/") and f not in HORS_MANIFESTE]
    assert extra == [], f"fichiers bruts hors manifeste et non documentés : {extra}"
