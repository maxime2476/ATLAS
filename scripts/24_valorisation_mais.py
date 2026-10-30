"""Étape 24 : valorisation descriptive de Q1 (phase 4 bis) : quintaux et euros associés à l'irrigation lors des étés chauds.

Usage : uv run python scripts/24_valorisation_mais.py   (après Rscript R/14_q1_maize.R et R/21_q1_verifications.R)
Entrées : data/processed/panel_mais_long.parquet ; reports/tables/phase4bis_q1_hypotheses.csv (beta de H1) ;
          reports/tables/phase4bis_q1_verif_intervalles.csv (IC 90 % par inversion du WCR, R/21_q1_verifications.R) ;
          data/raw/prix/insee_ippap_mais_010776430.xml ; data/raw/prix/eurostat_apri_ap_crpouta_FR_mais.json
Sortie : reports/tables/phase4bis_q1_valorisation.csv

Formule (spécification de la phase 4 bis) : pour le département d l'année t,
  q_dt = surface irriguée_dt × Y_non irrigué,dt × [exp(beta × (dd_32_ja_dt − moyenne_d)) − 1]
C'est un ordre de grandeur DESCRIPTIF conditionnel à beta : « quintaux associés à l'irrigation lors d'un été plus
chaud que la moyenne du département », pas un gain causé par l'irrigation.

Fourchette de mesure (ajoutée ensuite) : la même formule avec l'écart observé
du log-écart à sa moyenne départementale à la place de beta × écart de chaleur (« observe »), la même chose hors paires
reconduites de l'année précédente (« observe_sans_reconduites »), et le prix Eurostat observé à côté du prix raccordé.
"""

import json
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from atlas.download import ROOT

RAW = ROOT / "data" / "raw" / "prix"
TABLES = ROOT / "reports" / "tables"
YEARS = [2003, 2019, 2022]


def maize_price() -> tuple[pd.Series, pd.Series, float, float]:
    root = ET.parse(RAW / "insee_ippap_mais_010776430.xml").getroot()
    ippap = pd.Series({int(o.attrib["TIME_PERIOD"]): float(o.attrib["OBS_VALUE"])
                       for o in root.iter() if o.tag.endswith("Obs")}).sort_index()
    with open(RAW / "eurostat_apri_ap_crpouta_FR_mais.json") as f:
        d = json.load(f)
    idx = {v: int(k) for k, v in d["dimension"]["time"]["category"]["index"].items()}
    eur = pd.Series({idx[int(k)]: v for k, v in d["value"].items()}).sort_index()
    ratio = (eur / ippap).loc[2012:2016]
    spread = ratio.max() - ratio.min()
    # Règle : valorisation abandonnée si le rapport n'est pas stable.
    if spread >= 0.002:
        raise SystemExit(f"raccord instable (écart {spread:.4f} €/q par point) : valorisation abandonnée")
    return ratio.mean() * ippap, eur, ratio.mean(), spread


def main() -> None:
    hyp = pd.read_csv(TABLES / "phase4bis_q1_hypotheses.csv")
    h1 = hyp[hyp["hypothese"] == "H1"].iloc[0]
    # Fourchette : bornes de l'intervalle à 90 % obtenu par inversion du WCR (R/21),
    # à la place de l'intervalle CR1 groupé par année, dont la taille n'était pas vérifiée.
    ci = pd.read_csv(TABLES / "phase4bis_q1_verif_intervalles.csv")
    ci = ci[(ci["modele"] == "A1 maïs 2000-2025") & (ci["niveau"] == 0.90)].iloc[0]
    if abs(ci["estimation"] - h1["estimation"]) > 1e-12:
        raise SystemExit("l'intervalle de R/21 ne porte pas sur le beta de H1")
    betas = {"estimation": h1["estimation"], "ic90_bas": ci["borne_inf"], "ic90_haut": ci["borne_sup"]}

    m = pd.read_parquet(ROOT / "data" / "processed" / "panel_mais_long.parquet")
    m = m[m["echantillon_principal"]]
    cols = ["dep_code", "annee", "rendement_q_ha", "log_rendement"]
    irr = m[m.modalite == "irrigue"][cols + ["surface_ha", "dd_32_ja"]]
    non = m[m.modalite == "non_irrigue"][cols]
    p = irr.merge(non, on=["dep_code", "annee"], how="inner", validate="one_to_one",
                  suffixes=("_irr", ""))                                              # paires, comme en R
    p["ecart_dd32"] = p["dd_32_ja"] - p.groupby("dep_code")["dd_32_ja"].transform("mean")
    # Écart observé du log-écart irrigué / non irrigué à sa moyenne départementale (mesure « observe »).
    p["log_ecart"] = p["log_rendement_irr"] - p["log_rendement"]
    p["ecart_obs"] = p["log_ecart"] - p.groupby("dep_code")["log_ecart"].transform("mean")
    # Paire reconduite : les deux rendements identiques à ceux de l'année précédente (valeurs reprises, pas observées).
    p = p.sort_values(["dep_code", "annee"])
    prev = p.groupby("dep_code")[["rendement_q_ha_irr", "rendement_q_ha"]].shift(1)
    p["reconduite"] = (p["rendement_q_ha_irr"] == prev["rendement_q_ha_irr"]) & (p["rendement_q_ha"] == prev["rendement_q_ha"])
    price, price_eurostat, k, spread = maize_price()
    print(f"prix du maïs : {k:.4f} €/q par point d'IPPAP (raccord 2012-2016, écart max {spread:.4f})")

    rows = []
    for year in YEARS:
        y = p[p.annee == year]
        row = {"annee": year, "departements": len(y), "surface_irriguee_ha": y.surface_ha.sum(),
               "ecart_dd32_moyen_pondere": np.average(y.ecart_dd32, weights=y.surface_ha),
               "prix_eur_q": price.loc[year], "prix_eurostat_eur_q": price_eurostat.get(year, np.nan),
               "paires_reconduites": int(y.reconduite.sum())}
        for name, b in betas.items():
            q = (y.surface_ha * y.rendement_q_ha * (np.exp(b * y.ecart_dd32) - 1)).sum()
            row[f"quintaux_{name}"] = q
            row[f"millions_eur_{name}"] = q * price.loc[year] / 1e6
        # Mesure O : beta × écart de chaleur remplacé par l'écart observé.
        q_obs = (y.surface_ha * y.rendement_q_ha * (np.exp(y.ecart_obs) - 1)).sum()
        # Mesure O' : rapport formule / observé sur les paires non reconduites, appliqué à la formule sur toutes les paires.
        z = y[~y.reconduite]
        q_f_z = (z.surface_ha * z.rendement_q_ha * (np.exp(betas["estimation"] * z.ecart_dd32) - 1)).sum()
        q_o_z = (z.surface_ha * z.rendement_q_ha * (np.exp(z.ecart_obs) - 1)).sum()
        row["surestimation_formule"] = row["quintaux_estimation"] / q_obs - 1
        row["surestimation_formule_sans_reconduites"] = q_f_z / q_o_z - 1
        row["quintaux_observe"] = q_obs
        row["quintaux_observe_sans_reconduites"] = row["quintaux_estimation"] * q_o_z / q_f_z
        for name in ["estimation", "observe", "observe_sans_reconduites"]:
            row[f"millions_eur_{name}"] = row[f"quintaux_{name}"] * price.loc[year] / 1e6
            row[f"millions_eur_{name}_prix_eurostat"] = row[f"quintaux_{name}"] * row["prix_eurostat_eur_q"] / 1e6
        rows.append(row)
    out = pd.DataFrame(rows)
    out["beta"] = betas["estimation"]
    out.to_csv(TABLES / "phase4bis_q1_valorisation.csv", index=False)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
