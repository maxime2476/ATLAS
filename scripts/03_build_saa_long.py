"""Étape 3 : SAA départementale (feuille COP, grandes cultures) en format long.

Usage : uv run python scripts/03_build_saa_long.py

Entrée  : data/raw/agreste_saa/SAA-SeriesLongues-2010-2025_...zip (non modifié)
Sortie  : data/interim/saa_cop_departements_long.parquet
Ce n'est pas encore le panel d'analyse : aucune sélection de culture ni de département.
"""

from atlas.download import ROOT
from atlas.saa import read_sheet_wide, to_long

RAW_ZIP = (ROOT / "data" / "raw" / "agreste_saa"
           / "SAA-SeriesLongues-2010-2025_DonneesProvisoires-DepartementalesRegionales.zip")
OUT = ROOT / "data" / "interim" / "saa_cop_departements_long.parquet"


def main() -> None:
    wide = read_sheet_wide(RAW_ZIP, "COP")
    long = to_long(wide)
    # Contrôles avant écriture (explicites, actifs même sous python -O).
    if long.duplicated(["dep_code", "culture_code", "annee"]).any():
        raise RuntimeError("Clé (dep_code, culture_code, annee) non unique")
    if len(long) != len(wide) * 16:
        raise RuntimeError(f"Nombre de lignes inattendu : {len(long)} pour {len(wide)} lignes larges")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    long.to_parquet(OUT, index=False)
    print(f"{len(wide)} lignes larges -> {len(long)} lignes longues ; écrit {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
