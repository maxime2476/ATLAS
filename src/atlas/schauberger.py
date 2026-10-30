"""Lecture des rendements départementaux de Schauberger et al. (2022), GFZ, CC-BY 4.0.

Fichiers texte « ; », un par culture, indexés par NOM de département ; rendement en t/ha
(converti ici en q/ha pour être comparable à la SAA).

Version RAW par défaut : la version « FILTERED » masque des valeurs jugées aberrantes
par les auteurs, mais ce sont surtout des années de pertes réelles (2016 : 39 départements
masqués sur 85 ; 2003 : 16). L'utiliser sélectionnerait sur la variable expliquée.
"""

import io
import re
import unicodedata
import zipfile

import pandas as pd

INNER = "2021-001_Schauberger-et-al_Data/2021-001_Schauberger-et-al_Data_{version}/{crop}_data_1900-2018_{version}.txt"
# Agrégat historique antérieur à 1968, sans équivalent dans les départements actuels.
IGNORED_NAMES = {"Seine_SeineOise"}


def normalize_name(name: str) -> str:
    """Minuscules, sans accents ni ponctuation : « Côtes-d'Armor » et « Cotes_d_Armor » -> « cotesdarmor »."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def read_crop(zip_path, crop: str, name_to_code: dict[str, str], version: str = "RAW") -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        df = pd.read_csv(io.BytesIO(z.read(INNER.format(crop=crop, version=version))), sep=";", na_values="NA")
    df = df[~df["department"].isin(IGNORED_NAMES)]
    codes = df["department"].map(lambda n: name_to_code.get(normalize_name(n)))
    if codes.isna().any():
        raise ValueError(f"Noms non appariés : {sorted(df.loc[codes.isna(), 'department'].unique())}")
    out = pd.DataFrame({"dep_code": codes, "annee": df["year"],
                        "rendement_q_ha": df["yield"] * 10,  # t/ha -> q/ha
                        "surface_ha": df["area"], "production_t": df["production"]})
    if out.duplicated(["dep_code", "annee"]).any():
        raise ValueError("Clé (dep_code, annee) non unique après appariement")
    return out
