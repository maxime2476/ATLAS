"""Étape 23 : restrictions d'eau (VigiEau) par département et par été, juillet-août 2012-2025.

Usage : uv run python scripts/23_vigieau_indicators.py
Entrée : data/raw/vigieau/arretes.csv (fichier global : tous les arrêtés depuis 2010 ; les fichiers annuels
         en sont des sous-ensembles)
Sortie : data/processed/vigieau_dep_ete.parquet (dep_code, annee, jours_ar_plus_ja, jours_crise_ja, jours_vigilance_plus_ja)

Règles :
- un arrêté s'applique du jour de date_debut au jour de date_fin inclus ; sans date_fin (arrêté encore en
  vigueur), il est borné à la date de publication du fichier (2026-09-15) ;
- niveau d'un arrêté : le plus sévère de ses zones d'alerte (vigilance < alerte < alerte renforcée < crise) ;
- niveau d'un département un jour donné : le plus sévère des arrêtés en vigueur, toutes zones et tous types de
  ressource confondus. C'est un indicateur grossier : « au moins une zone du département », sans pondération
  par la surface agricole concernée ;
- années : 2012-2025. 2010-2011 sont exclues, car le niveau de gravité manque pour 99,6-100 % des arrêtés.
  Le niveau manque encore pour 13-21 % des arrêtés en 2012-2015, 5-11 % en 2016-2022 et ≤ 1 % depuis 2023.
  Un arrêté sans niveau n'est pas compté, d'où une sous-estimation des jours de restriction, surtout avant
  2016. La colonne `part_arretes_sans_niveau` (par année) est conservée, et `periode_principale` vaut vrai
  pour 2016-2025 (analyse principale de H3).
"""

import json

import numpy as np
import pandas as pd

from atlas.download import ROOT

RAW = ROOT / "data" / "raw" / "vigieau" / "arretes.csv"
OUT = ROOT / "data" / "processed" / "vigieau_dep_ete.parquet"
LEVELS = {"vigilance": 1, "alerte": 2, "alerte_renforcee": 3, "crise": 4}
FILE_DATE = pd.Timestamp("2026-09-15")
YEARS = range(2012, 2026)


def decree_level(s) -> int:
    if not isinstance(s, str):
        return 0
    vals = json.loads(s) if s.startswith("[") else [s]
    return max((LEVELS.get(v, 0) for v in vals), default=0)


def main() -> None:
    a = pd.read_csv(RAW, dtype=str).drop_duplicates("id")
    a["debut"] = pd.to_datetime(a["date_debut"], errors="coerce")
    a["fin"] = pd.to_datetime(a["date_fin"], errors="coerce").fillna(FILE_DATE)
    a["niveau"] = a["zones_alerte.niveau_gravite"].map(decree_level)
    a = a.dropna(subset=["debut", "departement"])
    # Liste des départements prise AVANT le filtre sur le niveau : un département dont aucun arrêté n'a de
    # niveau reçoit 0 jour, et non une ligne absente (donc NaN dans les jointures de l'étape 22).
    deps = sorted(a["departement"].str.strip().unique())
    missing = (a.assign(annee=a["debut"].dt.year).groupby("annee")["zones_alerte.niveau_gravite"]
               .apply(lambda s: s.isna().mean()))
    a = a[(a["niveau"] > 0) & (a["fin"] >= a["debut"])]
    a["dep_code"] = a["departement"].str.strip()

    rows = []
    for year in YEARS:
        days = pd.date_range(f"{year}-07-01", f"{year}-08-31")
        sub = a[(a["debut"] <= days[-1]) & (a["fin"] >= days[0])]
        for dep, g in sub.groupby("dep_code"):
            lvl = np.zeros(len(days), dtype=int)
            for _, r in g.iterrows():
                on = (days >= r["debut"]) & (days <= r["fin"])
                lvl[on] = np.maximum(lvl[on], r["niveau"])
            rows.append({"dep_code": dep, "annee": year, "jours_vigilance_plus_ja": int((lvl >= 1).sum()),
                         "jours_ar_plus_ja": int((lvl >= 3).sum()), "jours_crise_ja": int((lvl >= 4).sum())})
    out = pd.DataFrame(rows)
    # Département-année sans aucun arrêté en juillet-août : 0 jour (et non une valeur manquante).
    full = pd.MultiIndex.from_product([deps, list(YEARS)], names=["dep_code", "annee"]).to_frame(index=False)
    out = full.merge(out, on=["dep_code", "annee"], how="left").fillna(0)
    for c in ["jours_vigilance_plus_ja", "jours_ar_plus_ja", "jours_crise_ja"]:
        out[c] = out[c].astype(int)
    out["part_arretes_sans_niveau"] = out["annee"].map(missing).fillna(0).round(3)
    out["periode_principale"] = out["annee"] >= 2016
    if not (out["jours_vigilance_plus_ja"].le(62).all() and (out["jours_crise_ja"] <= out["jours_ar_plus_ja"]).all()):
        raise RuntimeError("plus de 62 jours en juillet-août, ou jours de crise > jours d'alerte renforcée")
    out.to_parquet(OUT, index=False)
    nat = out.groupby("annee")[["jours_ar_plus_ja", "jours_crise_ja"]].mean().round(1)
    print(f"{len(out)} lignes ({out.dep_code.nunique()} départements × {len(YEARS)} étés)")
    print("moyenne nationale des jours (≥ alerte renforcée / crise) en juillet-août :\n", nat.T.to_string())


if __name__ == "__main__":
    main()
