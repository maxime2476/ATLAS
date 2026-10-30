"""Étape 1 : téléchargement des données brutes et mise à jour du manifeste.

Usage :
    uv run python scripts/01_download_raw.py                      # SAA, ADMIN EXPRESS, SIM 2009 (échantillon)
    uv run python scripts/01_download_raw.py --sim-years 2009-2025

Les fichiers sont écrits dans data/raw/<source>/ (non versionné). Le manifeste
docs/manifest_raw.csv (versionné) conserve URL, taille et SHA-256.
"""

import argparse
import csv
import json
import urllib.request

from atlas.download import ROOT, USER_AGENT, download, tls_context

RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "docs" / "manifest_raw.csv"

SAA_URL = (
    "https://agreste.agriculture.gouv.fr/agreste-web/download/publication/publie/"
    "SAA-SeriesLongues/SAA-SeriesLongues-2010-2025_DonneesProvisoires-DepartementalesRegionales.zip"
)
ADMIN_EXPRESS_URL = (
    "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG-CARTO/"
    "ADMIN-EXPRESS-COG-CARTO_4-0__GEOPARQUET_WGS84G_FRA_2026-01-01/departement.parquet"
)
SIM_BASE = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/REF_CC/SIM/"
SIM_DOC_URLS = {
    "coordonnees_grille_safran_lambert-2-etendu.csv":
        SIM_BASE + "coordonnees_grille_safran_lambert-2-etendu.csv",
    "sim-quotidienne-parametres-20260331.pdf":
        "https://static.data.gouv.fr/resources/donnees-changement-climatique-sim-quotidienne/"
        "20260331-150448/sim-quotidienne-parametres-20260331.pdf",
    "climatologie-presentation-modele-sim-20260602.pdf":
        "https://static.data.gouv.fr/resources/donnees-changement-climatique-sim-quotidienne/"
        "20260602-150234/climatologie-presentation-modele-sim-20260602.pdf",
}


# RPG version 2.0, France métropolitaine, shapefile Lambert 93, archive 7z (~2,8 Go par millésime).
RPG_DATES = {2015: "2015-01-01", 2016: "2016-01-01", 2017: "2017-01-01"}


def rpg_url(year: int) -> str:
    ident = f"RPG_2-0__SHP_LAMB93_FR-{year}_{RPG_DATES[year]}"
    return f"https://data.geopf.fr/telechargement/download/RPG/{ident}/{ident}.7z"


# RPG version 1.0 (îlots anonymes, groupe de cultures majoritaire), une archive par région (découpage 2016) et
# par an, ~270 Mo. Phase 0 ter : 2008, régions de l'échantillon principal maïs (Q1-R9).
RPG1_REGIONS = ["R24", "R27", "R44", "R84"]  # Centre-Val de Loire, Bourgogne-Franche-Comté, Grand Est, AURA


def rpg1_url(region: str, year: int) -> str:
    ident = f"RPG_1-0__SHP_LAMB93_{region}_{year}-01-01"
    return f"https://data.geopf.fr/telechargement/download/RPG/{ident}/{ident}.7z"


# Schauberger et al. (2022), rendements départementaux 1900-2018, GFZ Data Services, CC-BY 4.0.
SCHAUBERGER_BASE = "https://datapub.gfz.de/download/10.5880.PIK.2021.001najvndf/"
SCHAUBERGER_FILES = ["2021-001_Schauberger-et-al_Data.zip",
                     "2021-001_Schauberger_et-al_Data-Description.pdf"]


# Prix du blé tendre (phase 6, valorisation descriptive).
PRICE_URLS = {
    "insee_ippap_ble_tendre_010776425.xml": "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/010776425",
    "insee_ippap_mais_010776430.xml": "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/010776430",
    "eurostat_apri_ap_crpouta_FR_ble_tendre.json":
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/apri_ap_crpouta"
        "?geo=FR&currency=EUR&prod_veg=01110000&format=JSON&lang=en",
    # Maïs grain (phase 4 bis : valorisation de Q1).
    "eurostat_apri_ap_crpouta_FR_mais.json":
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/apri_ap_crpouta"
        "?geo=FR&currency=EUR&prod_veg=01500000&format=JSON&lang=en",
}


# SAA « anciennes séries » 2000-2020 (avant recalage sur le RA 2020) : cultures développées, par département.
# Seule source trouvée du partage maïs grain irrigué / non irrigué avant 2010 (phase 0 bis).
SAA_OLD_URL = ("https://agreste.agriculture.gouv.fr/agreste-web/download/publication/publie/"
               "SAANR_DEVELOPPE_2/FDS_DEVELOPPE_2.zip")
# VigiEau (MTE), arrêtés de restriction d'eau par année, Licence Ouverte 2.0.
VIGIEAU_BASE = "https://static.data.gouv.fr/resources/donnee-secheresse-vigieau/"
VIGIEAU_FILES = {  # nom publié -> chemin daté sur data.gouv (relevé)
    **{f"arretes-{y}.csv": f"20260915-0400{s}/arretes-{y}.csv" for y, s in [
        (2012, "09"), (2013, "10"), (2014, "12"), (2015, "14"), (2016, "15"), (2017, "16"), (2018, "18"),
        (2019, "20"), (2020, "38"), (2021, "39"), (2022, "47"), (2023, "54"), (2024, "57")]},
    "arretes.csv": "20260915-040006/arretes.csv",
    "arretes-cadre.csv": "20260915-040104/arretes-cadre.csv",
}
# E-OBS v33.0e (ECA&D / Copernicus), Tmin et Tmax journalières, grille 0,1°, moyenne d'ensemble.
# Usage non commercial (recherche, enseignement) ; vérification de la mesure de chaleur de Q1.
EOBS_BASE = "https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/"
EOBS_FILES = [f"{v}_ens_mean_0.1deg_reg_{p}_v33.0e.nc" for v in ["tn", "tx"] for p in ["1995-2010", "2011-2025"]]
# Recensement agricole 2020, surfaces irriguées par culture et département (2010 et 2020).
RA2020_URL = ("https://agreste.agriculture.gouv.fr/agreste-web/download/publication/publie/"
              "RA2020_0052/FDS_RA2020_0052.zip")


# Agreste, conjoncture grandes cultures : estimations précoces 2026 par département, arrêtées au 1er octobre 2026
# (Infos rapides n° 2026-131 ; maïs grain irrigué et non irrigué). Données provisoires (pré-lecture de la récolte 2026).
CONJONCTURE_2026_URL = ("https://agreste.agriculture.gouv.fr/agreste-web/download/publication/publie/"
                        "IraGcu26131/2026_131donnees_grandescultures_departements.xlsx")
# Hub'Eau, prélèvements en eau (BNPE), usage irrigation, 2012-2023, Licence Ouverte Etalab.
# Deux périodes par département : une requête est limitée à 20 000 lignes (le Loiret en compte 31 925).
BNPE_API = "https://hubeau.eaufrance.fr/api/v1/prelevements/chroniques"
BNPE_PERIODS = {"2012-2017": range(2012, 2018), "2018-2023": range(2018, 2024)}
BNPE_DEPS = ["01", "03", "18", "26", "28", "36", "37", "38", "39", "41", "45", "58", "63", "67", "68", "69", "89"]


def bnpe_count(dep: str, years: range) -> int:
    """Nombre de lignes annoncé par l'API, pour vérifier qu'aucune page ne manque."""
    url = f"{BNPE_API}?code_departement={dep}&code_usage=IRR&annee={','.join(map(str, years))}&size=1"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, context=tls_context(), timeout=300) as r:   # comptage lent côté serveur
        return json.load(r)["count"]


def parse_years(text: str) -> list[int]:
    if "-" in text:
        start, end = text.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(y) for y in text.split(",")]


def update_manifest(rows: list[dict], source_of: dict[str, str]) -> None:
    """Ajoute ou remplace les lignes du manifeste (clé = chemin du fichier)."""
    fields = ["source", "file", "url", "size_bytes", "sha256"]
    existing = {}
    if MANIFEST.exists():
        with open(MANIFEST, newline="") as f:
            existing = {r["file"]: r for r in csv.DictReader(f)}
    for row in rows:
        old = existing.get(row["file"])
        if old and old["sha256"] != row["sha256"] and not row["downloaded"]:
            # Fichier local modifié sans nouveau téléchargement : on refuse de
            # réécrire le manifeste, pour ne pas perdre la traçabilité.
            raise RuntimeError(f"{row['file']} ne correspond plus au manifeste ; vérifier avant de continuer")
        existing[row["file"]] = {"source": source_of[row["file"]],
                                 **{k: row[k] for k in ("file", "url", "size_bytes", "sha256")}}
    with open(MANIFEST, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for key in sorted(existing):
            writer.writerow({k: existing[key][k] for k in fields})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-years", default="2009",
                        help="années SIM à télécharger, ex. 2009 ou 2009-2025")
    parser.add_argument("--rpg", default="",
                        help="millésimes RPG à télécharger (masque blé), ex. 2015-2017")
    parser.add_argument("--rpg1", default="",
                        help="millésimes RPG 1.0 (îlots) pour les régions de l'échantillon maïs, ex. 2008")
    parser.add_argument("--prix", action="store_true", help="IPPAP blé tendre et maïs (INSEE), prix Eurostat")
    parser.add_argument("--saa-ancienne", action="store_true", help="SAA 2000-2020 avant recalage (maïs irrigué)")
    parser.add_argument("--vigieau", action="store_true", help="arrêtés de restriction d'eau : fichiers annuels 2012-2024 et fichier global (utilisé, depuis 2010)")
    parser.add_argument("--schauberger", action="store_true",
                        help="rendements départementaux longs (robustesse 1990-2009)")
    parser.add_argument("--eobs", action="store_true", help="E-OBS Tmin/Tmax 0,1° 1995-2025 (environ 4 Go)")
    parser.add_argument("--ra2020", action="store_true", help="recensement agricole : surfaces irriguées par culture")
    parser.add_argument("--conjoncture-2026", action="store_true",
                        help="Agreste, estimations précoces 2026 par département (conjoncture au 1er octobre 2026)")
    parser.add_argument("--bnpe", action="store_true", help="volumes prélevés pour l'irrigation (Hub'Eau), 17 départements")
    args = parser.parse_args()

    rows, source_of = [], {}

    def get(source: str, url: str, dest, context=None):
        row = download(url, dest, context=context)
        rows.append(row)
        source_of[row["file"]] = source

    get("agreste_saa", SAA_URL, RAW / "agreste_saa" / SAA_URL.rsplit("/", 1)[1],
        context=tls_context(extra_intermediate=True))
    get("ign_admin_express", ADMIN_EXPRESS_URL,
        RAW / "ign_admin_express" / "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    for name, url in SIM_DOC_URLS.items():
        get("meteofrance_sim", url, RAW / "meteofrance_sim" / name)
    for year in parse_years(args.sim_years):
        name = f"QUOT_SIM2_{year}.csv.gz"
        get("meteofrance_sim", SIM_BASE + name, RAW / "meteofrance_sim" / name)
    for year in parse_years(args.rpg) if args.rpg else []:
        url = rpg_url(year)
        get("ign_rpg", url, RAW / "ign_rpg" / url.rsplit("/", 1)[1])
    for year in parse_years(args.rpg1) if args.rpg1 else []:
        for region in RPG1_REGIONS:
            url = rpg1_url(region, year)
            get("ign_rpg", url, RAW / "ign_rpg" / url.rsplit("/", 1)[1])
    if args.prix:
        for name, url in PRICE_URLS.items():
            get("prix", url, RAW / "prix" / name)
    if args.saa_ancienne:
        get("agreste_saa_ancienne", SAA_OLD_URL, RAW / "agreste_saa_ancienne" / "FDS_DEVELOPPE_2.zip",
            context=tls_context(extra_intermediate=True))
    if args.vigieau:
        for name, path in VIGIEAU_FILES.items():
            get("vigieau", VIGIEAU_BASE + path, RAW / "vigieau" / name)
    if args.schauberger:
        for name in SCHAUBERGER_FILES:
            get("pik_schauberger", SCHAUBERGER_BASE + name, RAW / "pik_schauberger" / name)
    if args.eobs:
        for name in EOBS_FILES:
            get("eobs", EOBS_BASE + name, RAW / "eobs" / name)
    if args.ra2020:
        get("agreste_ra2020", RA2020_URL, RAW / "agreste_ra2020" / "FDS_RA2020_0052.zip",
            context=tls_context(extra_intermediate=True))
    if args.conjoncture_2026:
        get("agreste_conjoncture", CONJONCTURE_2026_URL,
            RAW / "agreste_conjoncture" / CONJONCTURE_2026_URL.rsplit("/", 1)[1], context=tls_context(extra_intermediate=True))
    if args.bnpe:
        for dep in BNPE_DEPS:
            for period, years in BNPE_PERIODS.items():
                dest = RAW / "hubeau_bnpe" / f"irr_{dep}_{period}.csv"
                get("hubeau_bnpe", f"{BNPE_API}.csv?code_departement={dep}&code_usage=IRR"
                                   f"&annee={','.join(map(str, years))}&size=20000", dest)
                with open(dest, encoding="utf-8", newline="") as f:
                    n = sum(1 for _ in csv.reader(f, delimiter=";")) - 1
                if n != bnpe_count(dep, years):
                    raise RuntimeError(f"{dest.name} : {n} lignes, l'API en annonce davantage")

    update_manifest(rows, source_of)
    print(f"manifeste mis à jour : {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
