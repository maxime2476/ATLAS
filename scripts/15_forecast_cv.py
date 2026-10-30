"""Étape 15 : évaluation chronologique du module prédictif (spécification de la phase 5).

Usage : uv run python scripts/15_forecast_cv.py              (~10 min)
        uv run python scripts/15_forecast_cv.py --synthese   (synthèses seules, depuis phase5_metriques_annee.csv)
Sorties (reports/tables/) :
  phase5_predictions.parquet      toutes les prévisions (date, variante, année test, département, modèle)
  phase5_metriques_annee.csv      RMSE / MAE / skill par modèle et par année test
  phase5_synthese.csv             moyennes, écart de MSE à B1 : bootstrap des années (prévu en phase 5), intervalle
                                  de Student et test des signes (ajoutés), années gagnées
  phase5_synthese_vs_B0.csv       idem par rapport à B0 (comparaison ajoutée après les résultats)
  phase5_pertes.csv               détection des pertes (rappel, précision)
  phase5_national.csv             erreur sur le rendement national pondéré
  phase5_importance.csv           importance par permutation (RIDGE, GBM, 1er juillet, variante principale)
  phase5_alpha_ridge.csv          fréquence de chaque α de la ridge choisi
"""

import argparse
import time

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from atlas.download import ROOT
from atlas.forecast import SEED, compare_years, features, run_fold

TAB = ROOT / "reports" / "tables"
MODELS = ["B0", "B1", "L1", "RIDGE", "RF", "GBM"]
TEST_YEARS = range(2016, 2026)


def wmse(e, w):
    return np.average(e ** 2, weights=w)


def synthese(M: pd.DataFrame, ref: str) -> pd.DataFrame:
    """Moyennes sur les années test et bootstrap des années test (chaque année tirée comme un tout) de l'écart de MSE à la référence `ref`.

    Le générateur est réinitialisé pour chaque référence : la synthèse par rapport à B1 est celle de la
    spécification (phase 5) ; celle par rapport à B0 a été ajoutée après examen des résultats.
    """
    rng = np.random.default_rng(SEED)
    syn = []
    for (variant, date), g in M.groupby(["variante", "date"]):
        piv = g.pivot(index="annee_test", columns="modele", values="mse_log")
        boot_idx = rng.integers(0, len(piv), size=(9999, len(piv)))
        for m in MODELS:
            if m == ref and ref == "B0":
                continue
            diff = (piv[m] - piv[ref]).to_numpy()  # < 0 : le modèle fait mieux que la référence
            gm = g[g.modele == m]
            row = {"variante": variant, "date": date, "modele": m}
            if ref == "B1":
                row.update({"rmse_log_moyen": np.sqrt(piv[m].mean()), "mae_q_ha_moyenne": gm["mae_q_ha"].mean()})
            row.update({f"skill_moyen_vs_{ref}": 1 - piv[m].mean() / piv[ref].mean(),
                        f"ecart_mse_vs_{ref}": diff.mean(), **compare_years(diff, boot_idx),
                        f"annees_meilleur_que_{ref}": int((diff < 0).sum())})
            if ref == "B1":
                row["n_annees"] = len(diff)
            syn.append(row)
    return pd.DataFrame(syn)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthese", action="store_true", help="recalculer seulement les synthèses")
    if parser.parse_args().synthese:
        M = pd.read_csv(TAB / "phase5_metriques_annee.csv")
        for ref in ["B1", "B0"]:
            synthese(M, ref).to_csv(TAB / ("phase5_synthese.csv" if ref == "B1" else "phase5_synthese_vs_B0.csv"),
                                    index=False)
        print("synthèses écrites : phase5_synthese.csv, phase5_synthese_vs_B0.csv")
        return
    data = pd.read_parquet(ROOT / "data" / "processed" / "forecast_features.parquet")
    data = data[data["echantillon_principal"]].reset_index(drop=True)
    preds, importances = [], []
    for variant, first in [("principale_2010", 2010), ("longue_1990", 1990)]:
        for date in ["juin", "juillet"]:
            for t in TEST_YEARS:
                t0 = time.perf_counter()
                train = data[(data.annee >= first) & (data.annee < t)]
                test = data[data.annee == t]
                out, obj = run_fold(train, test, date)
                preds.append(out.assign(date=date, variante=variant, annee_test=t, alpha_ridge=obj["alpha"]))
                if variant == "principale_2010" and date == "juillet":
                    y_res = test["log_rendement"].to_numpy() - obj["base_te"]
                    for name in ["ridge", "gbm"]:
                        pi = permutation_importance(obj[name], obj["xte"], y_res, n_repeats=10, random_state=SEED,
                                                    sample_weight=test["surface_ref_ha"].to_numpy(),
                                                    scoring="neg_mean_squared_error")
                        importances.append(pd.DataFrame({"modele": name.upper(), "annee_test": t,
                                                         "variable": features(date),
                                                         "importance": pi.importances_mean}))
                print(f"{variant} {date} {t}: entraînement {train.annee.min()}-{train.annee.max()} "
                      f"({len(train)} obs.), α ridge = {obj['alpha']} ({time.perf_counter() - t0:.0f} s)")
    P = pd.concat(preds, ignore_index=True)
    P.to_parquet(TAB / "phase5_predictions.parquet", index=False)
    # Un α à la borne haute de la grille signale une pénalité probablement insuffisante (grille non modifiée).
    alphas = P.drop_duplicates(["variante", "date", "annee_test"]).groupby(["variante", "date"]).alpha_ridge
    alphas.value_counts().rename("n_plis").reset_index().to_csv(TAB / "phase5_alpha_ridge.csv", index=False)

    # --- Métriques par année test -------------------------------------------------------------
    rows = []
    for (variant, date, t), g in P.groupby(["variante", "date", "annee_test"]):
        w = g["poids"].to_numpy()
        mse_b1 = wmse(g["obs"] - g["B1"], w)
        for m in MODELS:
            e = g["obs"] - g[m]
            e_q = np.exp(g["obs"]) - np.exp(g[m])
            rows.append({"variante": variant, "date": date, "annee_test": t, "modele": m,
                         "mse_log": wmse(e, w), "rmse_log": np.sqrt(wmse(e, w)),
                         "mae_q_ha": np.average(np.abs(e_q), weights=w), "rmse_q_ha": np.sqrt(wmse(e_q, w)),
                         "skill_vs_B1": 1 - wmse(e, w) / mse_b1})
    M = pd.DataFrame(rows)
    M.to_csv(TAB / "phase5_metriques_annee.csv", index=False)

    for ref in ["B1", "B0"]:
        synthese(M, ref).to_csv(TAB / ("phase5_synthese.csv" if ref == "B1" else "phase5_synthese_vs_B0.csv"), index=False)
    S = pd.read_csv(TAB / "phase5_synthese.csv")

    # --- Détection des pertes et rendement national -------------------------------------------------
    loss_rows, nat_rows = [], []
    for (variant, date), g in P.groupby(["variante", "date"]):
        lost = (g["obs"] - g["B1"]) < np.log(0.9)
        for m in MODELS[2:]:
            pred_lost = (g[m] - g["B1"]) < np.log(0.95)
            tp = int((lost & pred_lost).sum())
            loss_rows.append({"variante": variant, "date": date, "modele": m, "pertes_observees": int(lost.sum()),
                              "pertes_predites": int(pred_lost.sum()), "vrais_positifs": tp,
                              "rappel": tp / max(int(lost.sum()), 1), "precision": tp / max(int(pred_lost.sum()), 1)})
        for t, gt in g.groupby("annee_test"):
            row = {"variante": variant, "date": date, "annee_test": t,
                   "observe_q_ha": np.average(np.exp(gt["obs"]), weights=gt["poids"])}
            for m in MODELS:
                row[f"{m}_q_ha"] = np.average(np.exp(gt[m]), weights=gt["poids"])
            nat_rows.append(row)
    pd.DataFrame(loss_rows).to_csv(TAB / "phase5_pertes.csv", index=False)
    pd.DataFrame(nat_rows).to_csv(TAB / "phase5_national.csv", index=False)

    imp = pd.concat(importances).groupby(["modele", "variable"], as_index=False)["importance"].mean()
    imp.sort_values(["modele", "importance"], ascending=[True, False]).to_csv(TAB / "phase5_importance.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n== Synthèse (écart de MSE < 0 : meilleur que B1)\n",
          S.round({"rmse_log_moyen": 4, "mae_q_ha_moyenne": 2, "skill_moyen_vs_B1": 3, "ecart_mse_vs_B1": 5,
                   "ic95_bas": 5, "ic95_haut": 5}).to_string(index=False))


if __name__ == "__main__":
    main()
