"""Module prédictif (phase 5) : références naïves et modèles météo, un pli d'origine glissante à la fois.

Règle centrale : tout ce qui est estimé (moyennes départementales, tendance, standardisation,
hyperparamètres) n'utilise QUE les lignes d'entraînement passées à chaque fonction.
Spécification de la phase 5.
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge

SEED = 123
# Graine de la forêt aléatoire pour les prévisions figées des récoltes futures (specification_recoltes_futures.md) :
# celle de la prévision du blé 2026 enregistrée la première, gardée pour que ces prévisions restent comparables.
SEED_FIGEE = 20261010
VARS = ["gdd_0_32", "dd_32", "hot_30", "prec", "etp", "swi", "swi_dry", "tmin", "tmax"]
DATES = {"juin": ["automne", "hiver", "printemps", "mai"],
         "juillet": ["automne", "hiver", "printemps", "remplissage"]}
L1_VARS = {"juin": ["gdd_0_32_mai", "dd_32_mai", "prec_printemps", "dd_0_automne", "prec_automne"],
           "juillet": ["gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne",
                       "prec_automne"]}
RIDGE_ALPHAS = [0.1, 1, 10, 100, 1000]


def features(date: str) -> list[str]:
    return [f"{v}_{w}" for w in DATES[date] for v in VARS]


def l1_features(date: str) -> list[str]:
    # dd_0_automne n'est pas dans les 36 variables (gdd_0_32 l'est) : elle vient de la même table.
    return L1_VARS[date]


def fit_b1(train: pd.DataFrame):
    """Effet fixe département + tendance linéaire commune (MCO pondérés), estimés sur `train`."""
    t0 = train["annee"].mean()
    dummies = pd.get_dummies(train["dep_code"], dtype=float)
    X = np.column_stack([dummies.to_numpy(), train["annee"] - t0])
    m = LinearRegression(fit_intercept=False).fit(X, train["log_rendement"], sample_weight=train["surface_ref_ha"])
    dep_effect = dict(zip(dummies.columns, m.coef_[:-1]))
    slope = m.coef_[-1]

    def predict(df: pd.DataFrame) -> np.ndarray:
        return df["dep_code"].map(dep_effect).to_numpy() + slope * (df["annee"] - t0).to_numpy()
    return predict


def predict_b0(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    means = train.groupby("dep_code").apply(
        lambda d: np.average(d["log_rendement"], weights=d["surface_ref_ha"]), include_groups=False)
    return test["dep_code"].map(means).to_numpy()


def center_by_dep(train: pd.DataFrame, test: pd.DataFrame, cols: list[str]):
    """Centre les variables par département avec les moyennes d'ENTRAÎNEMENT (le test n'intervient pas)."""
    mu = train.groupby("dep_code")[cols].mean()
    return (train[cols] - mu.loc[train["dep_code"]].to_numpy()).to_numpy(), \
           (test[cols] - mu.loc[test["dep_code"]].to_numpy()).to_numpy()


def standardize(xtr: np.ndarray, xte: np.ndarray):
    sd = xtr.std(axis=0)
    sd[sd == 0] = 1.0
    return xtr / sd, xte / sd


def compare_years(diff: np.ndarray, boot_idx: np.ndarray) -> dict:
    """Incertitude de l'écart moyen de MSE sur les années test (un écart par année, < 0 : meilleur).

    - bootstrap percentile des années (prévu en phase 5) : avec 10 années, environ ± 1,86 σ/√n ;
    - intervalle de Student à n − 1 degrés de liberté (± 2,26 σ/√n pour n = 10), critère retenu
      pour dire qu'un écart est significatif ;
    - test des signes bilatéral sur le nombre d'années où le modèle fait mieux.
    `boot_idx` (tirages × années) est partagé entre les modèles comparés, pour des tirages appariés.
    """
    n = len(diff)
    boot = diff[boot_idx].mean(axis=1)
    half = stats.t.ppf(0.975, n - 1) * diff.std(ddof=1) / np.sqrt(n)
    better = int((diff < 0).sum())
    return {"ic95_bas": np.quantile(boot, 0.025), "ic95_haut": np.quantile(boot, 0.975),
            "ic95_t_bas": diff.mean() - half, "ic95_t_haut": diff.mean() + half,
            "p_signes": stats.binomtest(better, n, 0.5).pvalue}


def choose_ridge_alpha(x: np.ndarray, y: np.ndarray, w: np.ndarray, years: np.ndarray) -> float:
    """α par validation croisée interne : une année d'entraînement retirée à la fois (MSE pondérée).

    Cette validation interne n'est pas chronologique (elle utilise des années postérieures à l'année retirée),
    mais elle ne voit jamais l'année test : aucune fuite vers le pli évalué. Les entrées `x` et `y` (centrage,
    écart-type, résidu de B1) sont calculées sur tout l'entraînement, année interne retirée comprise : le choix
    de α est donc légèrement optimiste, sans effet sur l'année test.
    """
    scores = {}
    for a in RIDGE_ALPHAS:
        err = []
        for yr in np.unique(years):
            tr, va = years != yr, years == yr
            m = Ridge(alpha=a).fit(x[tr], y[tr], sample_weight=w[tr])
            err.append(np.average((y[va] - m.predict(x[va])) ** 2, weights=w[va]))
        scores[a] = np.mean(err)
    return min(scores, key=scores.get)


def run_fold(train: pd.DataFrame, test: pd.DataFrame, date: str,
             extra: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Prévisions (log-rendement) de tous les modèles pour un pli. Renvoie aussi les objets utiles.

    `extra` : variables supplémentaires (ex. NDVI) ajoutées aux 36 variables météo de RIDGE, RF et GBM.
    """
    b1 = fit_b1(train)
    base_tr, base_te = b1(train), b1(test)
    resid = train["log_rendement"].to_numpy() - base_tr
    w = train["surface_ref_ha"].to_numpy()
    out = pd.DataFrame({"dep_code": test["dep_code"].to_numpy(), "annee": test["annee"].to_numpy(),
                        "obs": test["log_rendement"].to_numpy(), "poids": test["surface_ref_ha"].to_numpy(),
                        "B0": predict_b0(train, test), "B1": base_te})

    # L1 : MCO sur les variables de la spécification M1 (centrées par département).
    xtr, xte = center_by_dep(train, test, l1_features(date))
    l1 = LinearRegression().fit(xtr, resid, sample_weight=w)
    out["L1"] = base_te + l1.predict(xte)

    # Modèles sur les 36 variables, centrées par département puis standardisées.
    cols = features(date) + (extra or [])
    xtr, xte = center_by_dep(train, test, cols)
    xtr, xte = standardize(xtr, xte)
    alpha = choose_ridge_alpha(xtr, resid, w, train["annee"].to_numpy())
    ridge = Ridge(alpha=alpha).fit(xtr, resid, sample_weight=w)
    out["RIDGE"] = base_te + ridge.predict(xte)
    rf = RandomForestRegressor(n_estimators=500, min_samples_leaf=10, max_features=1 / 3,
                               random_state=SEED, n_jobs=-1).fit(xtr, resid, sample_weight=w)
    out["RF"] = base_te + rf.predict(xte)
    gbm = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=20,
                                        early_stopping=False, random_state=SEED).fit(xtr, resid, sample_weight=w)
    out["GBM"] = base_te + gbm.predict(xte)
    return out, {"alpha": alpha, "ridge": ridge, "gbm": gbm, "xte": xte, "base_te": base_te}
