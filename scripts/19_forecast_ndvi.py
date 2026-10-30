"""Étape 19 : le NDVI améliore-t-il la prévision ?

Usage : uv run python scripts/19_forecast_ndvi.py              (durée : voir data/README.md)
        uv run python scripts/19_forecast_ndvi.py --synthese  (synthèse seule, depuis phase6_ndvi_metriques_annee.csv)
Entrées : data/processed/ndvi_dep_composite.parquet, data/processed/forecast_features.parquet
Sorties : data/processed/ndvi_features.parquet, reports/tables/phase6_ndvi_*.csv

Variables NDVI disponibles à la date D (1er juin ou 1er juillet de l'année t) : seuls les composites
dont la période de 16 jours est TERMINÉE avant D (fin = début + 15 jours < D).
  ndvi_avril, ndvi_mai, ndvi_juin : moyenne des composites utilisables commençant ce mois-là
  ndvi_max                        : maximum des composites utilisables
Valeurs manquantes (nuages, mois sans composite utilisable) : remplacées, dans chaque pli, par la
moyenne du département sur les années d'ENTRAÎNEMENT (sans fuite).
"""

import argparse

import numpy as np
import pandas as pd

from atlas.download import ROOT
from atlas.forecast import SEED, compare_years, run_fold

PROC = ROOT / "data" / "processed"
TAB = ROOT / "reports" / "tables"
DATES = {"juin": (6, 1), "juillet": (7, 1)}
MODELS = ["B0", "B1", "RIDGE", "RF", "GBM"]


def ndvi_features() -> pd.DataFrame:
    comp = pd.read_parquet(PROC / "ndvi_dep_composite.parquet")
    parts = []
    for name, (m, d) in DATES.items():
        cut = pd.to_datetime(dict(year=comp["annee"], month=m, day=d))
        ok = comp[comp["fin"] < cut].copy()           # composite entièrement terminé avant la date de prévision
        ok["mois"] = ok["debut"].dt.month
        piv = ok[ok["mois"].between(4, 6)].pivot_table(index=["dep_code", "annee"], columns="mois", values="ndvi")
        piv.columns = [f"ndvi_{ {4: 'avril', 5: 'mai', 6: 'juin'}[c] }" for c in piv.columns]
        piv["ndvi_max"] = ok.groupby(["dep_code", "annee"])["ndvi"].max()
        piv.columns = [f"{c}_{name}" for c in piv.columns]
        parts.append(piv)
    return pd.concat(parts, axis=1).reset_index()


def impute_by_train_dep_mean(train: pd.DataFrame, test: pd.DataFrame, cols):
    mu = train.groupby("dep_code")[cols].mean()
    glob = train[cols].mean()
    fill = lambda df: df[cols].fillna(mu.reindex(df["dep_code"]).set_index(df.index)).fillna(glob)
    return train.assign(**fill(train)), test.assign(**fill(test))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthese", action="store_true", help="recalculer seulement la synthèse")
    if parser.parse_args().synthese:
        synthese(pd.read_csv(TAB / "phase6_ndvi_metriques_annee.csv"))
        return
    nd = ndvi_features()
    nd.to_parquet(PROC / "ndvi_features.parquet", index=False)
    data = pd.read_parquet(PROC / "forecast_features.parquet")
    data = data[data["echantillon_principal"] & (data["annee"] >= 2010)].merge(nd, on=["dep_code", "annee"], how="left")
    preds = []
    for date in DATES:
        cols = [c for c in nd.columns if c.endswith("_" + date) and nd[c].notna().any()]
        print(f"{date} : variables NDVI {cols} ; part manquante : {data[cols].isna().mean().round(3).to_dict()}")
        for t in range(2016, 2026):
            train, test = data[data.annee < t], data[data.annee == t]
            train, test = impute_by_train_dep_mean(train, test, cols)
            base, _ = run_fold(train, test, date)
            with_ndvi, _ = run_fold(train, test, date, extra=cols)
            for label, out in [("meteo", base), ("meteo_ndvi", with_ndvi)]:
                preds.append(out.assign(date=date, version=label, annee_test=t))
            print(f"  {date} {t} terminé")
    P = pd.concat(preds, ignore_index=True)
    P.to_parquet(TAB / "phase6_ndvi_predictions.parquet", index=False)

    rows = []
    for (date, version, t), g in P.groupby(["date", "version", "annee_test"]):
        for m in MODELS:
            rows.append({"date": date, "version": version, "annee_test": t, "modele": m,
                         "mse_log": np.average((g["obs"] - g[m]) ** 2, weights=g["poids"])})
    M = pd.DataFrame(rows)
    M.to_csv(TAB / "phase6_ndvi_metriques_annee.csv", index=False)
    synthese(M)


def synthese(M: pd.DataFrame) -> None:
    """Écarts de MSE sur les 10 années test : bootstrap, intervalle de Student et test des signes."""
    rng = np.random.default_rng(SEED)
    syn = []
    for date in DATES:
        a = M[(M.date == date)].pivot_table(index="annee_test", columns=["version", "modele"], values="mse_log")
        idx = rng.integers(0, len(a), size=(9999, len(a)))
        b0 = a[("meteo", "B0")].to_numpy()
        for m in ["RIDGE", "RF", "GBM"]:
            with_n, without = a[("meteo_ndvi", m)].to_numpy(), a[("meteo", m)].to_numpy()
            for ref_name, ref in [("vs_B0", b0), ("vs_meme_modele_sans_ndvi", without)]:
                diff = with_n - ref
                syn.append({"date": date, "modele": m, "comparaison": ref_name, "ecart_mse": diff.mean(),
                            **compare_years(diff, idx),
                            "skill": 1 - with_n.mean() / ref.mean(), "annees_meilleur": int((diff < 0).sum())})
    S = pd.DataFrame(syn)
    S.to_csv(TAB / "phase6_ndvi_synthese.csv", index=False)
    print(S.round(5).to_string(index=False))


if __name__ == "__main__":
    main()
