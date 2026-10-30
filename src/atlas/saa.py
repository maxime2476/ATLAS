"""Lecture des séries longues départementales de la Statistique agricole annuelle (SAA).

Le fichier source est en format large (SURF_2010 ... PROD_2025) avec des libellés
concaténés (« 077 - Seine-et-Marne »). On le passe en format long, une ligne par
(département, culture, année), sans modifier les valeurs.

Unités (en-tête de la feuille COP) : surface en ha, production en quintaux (q),
rendement en q/ha. 1 q = 100 kg.
"""

import re
import zipfile
from pathlib import Path

import pandas as pd

XLSX_DEP = "SAA_2010-2025_provisoires_donnees_departementales.xlsx"
HEADER_ROW = 5  # ligne 6 du classeur (0-indexée)
YEARS = list(range(2010, 2026))
PROVISIONAL_YEARS = {2025}  # « Données 2025 provisoires » (données arrêtées au 30/03/2026)
ID_COLUMNS = ["LIB_REG2", "LIB_DEP", "LIB_SAA", "STATUT_QUALITE"]
MEASURES = {"SURF": "surface_ha", "REND": "rendement_q_ha", "PROD": "production_q"}


def dep_code_from_label(label: str) -> str:
    """« 077 - Seine-et-Marne » -> « 77 » ; « 02A - Corse-du-Sud » -> « 2A » ; « 971 - ... » -> « 971 ».

    Cette normalisation suit le Code officiel géographique de l'INSEE, utilisé par ADMIN EXPRESS.
    """
    code = label.split(" - ", 1)[0].strip()
    if not re.fullmatch(r"\d{3}|0[2][AB]", code):
        raise ValueError(f"Libellé de département inattendu : {label!r}")
    return code[1:] if code.startswith("0") else code


def read_sheet_wide(zip_path: Path, sheet: str) -> pd.DataFrame:
    """Lit une feuille du classeur départemental, en texte, sans conversion de valeurs."""
    with zipfile.ZipFile(zip_path) as z, z.open(XLSX_DEP) as f:
        df = pd.read_excel(f, sheet_name=sheet, header=HEADER_ROW, dtype=str)
    return df.dropna(subset=["LIB_DEP"])


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    """Format large -> long : une ligne par (département, culture, année)."""
    values = wide.set_index(ID_COLUMNS)
    # Colonnes « SURF_2010 » -> MultiIndex (mesure, année), puis empilement des années.
    values.columns = pd.MultiIndex.from_tuples(
        [(c.split("_")[0], int(c.split("_")[1])) for c in values.columns], names=["mesure", "annee"])
    values = values.apply(pd.to_numeric, errors="raise")
    long = values.stack("annee", future_stack=True).reset_index().rename(columns=MEASURES)

    out = pd.DataFrame({
        "dep_code": long["LIB_DEP"].map(dep_code_from_label),
        "dep_libelle": long["LIB_DEP"].str.split(" - ", n=1).str[1],
        "reg_libelle": long["LIB_REG2"],
        "culture_code": long["LIB_SAA"].str.split(" - ", n=1).str[0],
        "culture_libelle": long["LIB_SAA"].str.split(" - ", n=1).str[1],
        "statut_qualite": long["STATUT_QUALITE"],
        "annee": long["annee"],
        "surface_ha": long["surface_ha"],
        "rendement_q_ha": long["rendement_q_ha"],
        "production_q": long["production_q"],
    })
    out["provisoire"] = out["annee"].isin(PROVISIONAL_YEARS)
    out["metropole"] = ~out["dep_code"].str.startswith("97")
    return out.sort_values(["dep_code", "culture_code", "annee"]).reset_index(drop=True)
