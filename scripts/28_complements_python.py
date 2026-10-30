"""Étape 28 : analyses complémentaires côté Python (préparation des variables, ensilage, DML, prévision corrigeant B0).

Usage : uv run python scripts/28_complements_python.py preparer     (avant R/22_q1_complements.R)
        uv run python scripts/28_complements_python.py prevision    (indépendant)
Exploratoire.

Sorties :
  data/processed/phase7_covariables_dep.parquet   un département par ligne (38 départements de la population maïs) :
      part_irriguee (maïs grain irrigué / total, surfaces 2010-2012), alt_masque_m, alt_surface_m, ecart_alt_m
      (surface − masque), relief (6 départements du tableau 5), lat_centroide
  data/processed/phase7_fourrage.parquet          département × année 2010-2025 : surfaces de maïs fourrage et de maïs
      grain non irrigués, part_fourrage_non_irr = fourrage / (fourrage + grain)
  data/processed/phase7_dml_residus.parquet       résidus du DML (Y et dd_32_ja) pour chacun des 50 découpages
      en plis (colonne repetition), pour l'inférence WCR en R
  data/processed/phase7_dml_mundlak_residus.parquet  idem, variante Mundlak
  reports/tables/phase7_prevision_vs_B0.csv (+ _annees : MSE par année test)
"""

import argparse

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge

from atlas import forecast as fc
from atlas.download import ROOT
from atlas.saa import read_sheet_wide, to_long

PROC = ROOT / "data" / "processed"
TAB = ROOT / "reports" / "tables"
SAA_ZIP = ROOT / "data" / "raw" / "agreste_saa" / "SAA-SeriesLongues-2010-2025_DonneesProvisoires-DepartementalesRegionales.zip"
RELIEF = ["01", "26", "38", "39", "63", "69"]
SEED = 123


def maize_pairs() -> pd.DataFrame:
    """Paires irrigué / non irrigué de l'échantillon principal (même construction que R/14)."""
    m = pd.read_parquet(PROC / "panel_mais_long.parquet")
    m = m[m.echantillon_principal]
    irr = m[m.modalite == "irrigue"]
    non = m[m.modalite == "non_irrigue"][["dep_code", "annee", "log_rendement"]].rename(
        columns={"log_rendement": "log_non_irrigue"})
    d = irr.merge(non, on=["dep_code", "annee"], how="inner", validate="one_to_one")
    d["ecart_log"] = d.log_rendement - d.log_non_irrigue
    if len(d) != 435:
        raise RuntimeError(f"{len(d)} paires au lieu de 435")
    return d


def covariates() -> pd.DataFrame:
    m = pd.read_parquet(PROC / "panel_mais_long.parquet")
    ref = (m[m.annee.between(2010, 2012)].groupby(["dep_code", "modalite"]).surface_ha.mean().unstack())
    out = pd.DataFrame({"part_irriguee": ref.irrigue / (ref.irrigue + ref.non_irrigue)})
    alt = pd.read_parquet(PROC / "cell_altitude.parquet")
    for wfile, wcol, col in [("weights_cell_dep_maize", "w_maize", "alt_masque_m"),
                             ("weights_cell_dep_area", "w_area", "alt_surface_m")]:
        w = pd.read_parquet(PROC / f"{wfile}.parquet").merge(alt, on=["LAMBX", "LAMBY"]).dropna(subset=["altitude_moy_m"])
        out[col] = w.groupby("dep_code").apply(lambda d: (d[wcol] * d.altitude_moy_m).sum() / d[wcol].sum())
    out["ecart_alt_m"] = out.alt_surface_m - out.alt_masque_m
    out = out.reset_index()
    out["relief"] = out.dep_code.isin(RELIEF)
    out = out.merge(m[["dep_code", "lat_centroide"]].drop_duplicates(), on="dep_code", how="left", validate="one_to_one")
    if out.isna().any().any() or len(out) != 38:
        raise RuntimeError("covariables départementales incomplètes")
    return out


def fodder() -> pd.DataFrame:
    fou = to_long(read_sheet_wide(SAA_ZIP, "FOU"))
    cop = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    f = fou[fou.culture_code == "05"][["dep_code", "annee", "surface_ha"]].rename(columns={"surface_ha": "fourrage_non_irr_ha"})
    g = cop[cop.culture_code == "15"][["dep_code", "annee", "surface_ha"]].rename(columns={"surface_ha": "grain_non_irr_ha"})
    out = f.merge(g, on=["dep_code", "annee"], how="inner", validate="one_to_one")
    out["part_fourrage_non_irr"] = out.fourrage_non_irr_ha / (out.fourrage_non_irr_ha + out.grain_non_irr_ha)
    return out


def two_way_residuals(df: pd.DataFrame, cols: list[str], w: np.ndarray) -> pd.DataFrame:
    """Résidus de MCO pondérés de chaque colonne sur les indicatrices département et année."""
    X = pd.get_dummies(df[["dep_code", "annee"]].astype(str), drop_first=True, dtype=float)
    X.insert(0, "const", 1.0)
    sw = np.sqrt(w)[:, None]
    Y = df[cols].to_numpy(float)
    coef = np.linalg.lstsq(X.to_numpy() * sw, Y * sw, rcond=None)[0]
    return pd.DataFrame(Y - X.to_numpy() @ coef, columns=cols, index=df.index)


DML_REPETITIONS = 50


def dml(d: pd.DataFrame) -> None:
    """DML : modèle partiellement linéaire, nuisances par forêt aléatoire, plis formés d'années entières.

    Les effets fixes département et année sont retirés une fois, sur tout l'échantillon, avant le découpage
    (transformation linéaire, sans apprentissage). Le découpage des années en 5 plis est répété 50 fois
    (graine SEED + r, aussi pour les forêts) : une seule répartition rend β̂ dépendant de la graine
    (Chernozhukov et al. 2018, § 3.4).
    """
    controls = ["swi_ja", "prec_ja", "etp_ja", "gdd_0_32_ja"]
    w = d.surface_ref_ha.to_numpy(float)
    r = two_way_residuals(d, ["ecart_log", "dd_32_ja"] + controls, w)
    years = np.sort(d.annee.unique())
    outs, betas = [], []
    for rep in range(DML_REPETITIONS):
        seed = SEED + rep
        folds = {y: k % 5 for k, y in enumerate(np.random.default_rng(seed).permutation(years))}
        fold = d.annee.map(folds).to_numpy()
        res = pd.DataFrame(index=d.index, columns=["y_res", "d_res"], dtype=float)
        for k in range(5):
            tr, te = fold != k, fold == k
            for target, name in [("ecart_log", "y_res"), ("dd_32_ja", "d_res")]:
                rf = RandomForestRegressor(n_estimators=500, min_samples_leaf=5, random_state=seed, n_jobs=-1)
                rf.fit(r.loc[tr, controls], r.loc[tr, target], sample_weight=w[tr])
                res.loc[te, name] = r.loc[te, target] - rf.predict(r.loc[te, controls])
        betas.append(np.sum(w * res.d_res * res.y_res) / np.sum(w * res.d_res ** 2))
        outs.append(d[["dep_code", "annee", "surface_ref_ha"]].assign(repetition=rep, y_res=res.y_res, d_res=res.d_res))
    pd.concat(outs, ignore_index=True).to_parquet(PROC / "phase7_dml_residus.parquet", index=False)
    print(f"DML, {DML_REPETITIONS} découpages : beta médian = {np.median(betas):.4f} "
          f"(min {np.min(betas):.4f}, max {np.max(betas):.4f} ; A1 : 0,0158) ; inférence WCR dans R/22")


def dml_mundlak(d: pd.DataFrame) -> None:
    """Variante Mundlak du DML, sans retrait préalable des effets fixes département.

    Seules les moyennes annuelles sont retirées : elles ne mélangent pas les plis, formés d'années entières.
    Les effets départementaux sont traités à la Mundlak : les forêts reçoivent aussi les moyennes
    départementales des contrôles et de la chaleur (jamais de la variable expliquée). Mêmes 50 découpages.
    """
    controls = ["swi_ja", "prec_ja", "etp_ja", "gdd_0_32_ja"]
    w = d.surface_ref_ha.to_numpy(float)
    cols = ["ecart_log", "dd_32_ja"] + controls
    r = d[cols] - d.groupby("annee")[cols].transform(lambda v: np.average(v, weights=w[v.index]))
    feats = r[controls].copy()
    for c in controls + ["dd_32_ja"]:
        feats[f"moy_dep_{c}"] = d.groupby("dep_code")[c].transform("mean")
    years = np.sort(d.annee.unique())
    outs, betas = [], []
    for rep in range(DML_REPETITIONS):
        seed = SEED + rep
        folds = {y: k % 5 for k, y in enumerate(np.random.default_rng(seed).permutation(years))}
        fold = d.annee.map(folds).to_numpy()
        res = pd.DataFrame(index=d.index, columns=["y_res", "d_res"], dtype=float)
        for k in range(5):
            tr, te = fold != k, fold == k
            for target, name in [("ecart_log", "y_res"), ("dd_32_ja", "d_res")]:
                rf = RandomForestRegressor(n_estimators=500, min_samples_leaf=5, random_state=seed, n_jobs=-1)
                rf.fit(feats.loc[tr], r.loc[tr, target], sample_weight=w[tr])
                res.loc[te, name] = r.loc[te, target] - rf.predict(feats.loc[te])
        betas.append(np.sum(w * res.d_res * res.y_res) / np.sum(w * res.d_res ** 2))
        outs.append(d[["dep_code", "annee", "surface_ref_ha"]].assign(repetition=rep, y_res=res.y_res, d_res=res.d_res))
    pd.concat(outs, ignore_index=True).to_parquet(PROC / "phase7_dml_mundlak_residus.parquet", index=False)
    print(f"DML Mundlak, {DML_REPETITIONS} découpages : beta médian = {np.median(betas):.4f} "
          f"(min {np.min(betas):.4f}, max {np.max(betas):.4f})")


def prepare() -> None:
    cov = covariates()
    cov.to_parquet(PROC / "phase7_covariables_dep.parquet", index=False)
    print(cov[cov.dep_code.isin(maize_pairs().dep_code)].round(3).to_string(index=False))
    fod = fodder()
    fod.to_parquet(PROC / "phase7_fourrage.parquet", index=False)
    print(f"fourrage : {len(fod)} département-années ; part médiane du fourrage dans le maïs non irrigué : "
          f"{fod.part_fourrage_non_irr.median():.2f}")
    dml(maize_pairs())
    dml_mundlak(maize_pairs())


# --- Prévision : modèles corrigeant B0 ---------------------------------------------------------------
def b0_corrected() -> pd.DataFrame:
    """Modèles prédisant le résidu de B0 (moyenne du département) au lieu de B1 ; mêmes réglages que fc.run_fold.

    Variante principale (entraînement depuis 2010), années test 2016-2025, déjà vues : exploratoire.
    """
    feat = pd.read_parquet(PROC / "forecast_features.parquet")
    feat = feat[feat.echantillon_principal].reset_index(drop=True)
    rows = []
    for date in ["juin", "juillet"]:
        cols = fc.features(date)
        for t in range(2016, 2026):
            train, test = feat[(feat.annee >= 2010) & (feat.annee < t)], feat[feat.annee == t]
            b0_tr = train.groupby("dep_code").log_rendement.transform("mean").to_numpy()
            b0_te = fc.predict_b0(train, test)
            resid, w = train.log_rendement.to_numpy() - b0_tr, train.surface_ref_ha.to_numpy()
            xtr, xte = fc.center_by_dep(train, test, cols)
            xtr, xte = fc.standardize(xtr, xte)
            alpha = fc.choose_ridge_alpha(xtr, resid, w, train.annee.to_numpy())
            preds = {
                "B0": b0_te,
                "RIDGE_B0": b0_te + Ridge(alpha=alpha).fit(xtr, resid, sample_weight=w).predict(xte),
                "RF_B0": b0_te + RandomForestRegressor(n_estimators=500, min_samples_leaf=10, max_features=1 / 3,
                                                       random_state=fc.SEED, n_jobs=-1)
                .fit(xtr, resid, sample_weight=w).predict(xte),
                "GBM_B0": b0_te + HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200,
                                                                min_samples_leaf=20, early_stopping=False,
                                                                random_state=fc.SEED)
                .fit(xtr, resid, sample_weight=w).predict(xte),
            }
            y, wt = test.log_rendement.to_numpy(), test.surface_ref_ha.to_numpy()
            for model, pr in preds.items():
                rows.append({"date": date, "annee": t, "modele": model, "mse": np.average((y - pr) ** 2, weights=wt)})
    m = pd.DataFrame(rows)
    m.to_csv(TAB / "phase7_prevision_vs_B0_annees.csv", index=False)
    rng = np.random.default_rng(SEED)
    out = []
    for date, g in m.groupby("date"):
        piv = g.pivot(index="annee", columns="modele", values="mse")
        boot_idx = rng.integers(0, len(piv), size=(9999, len(piv)))   # années test tirées comme un tout, comme en phase 5
        for model in ["RIDGE_B0", "RF_B0", "GBM_B0"]:
            diff = (piv[model] - piv["B0"]).to_numpy()
            out.append({"date": date, "modele": model, "skill_vs_B0": 1 - piv[model].mean() / piv["B0"].mean(),
                        "ecart_mse_vs_B0": diff.mean(), **fc.compare_years(diff, boot_idx),
                        "annees_meilleur_que_B0": int((diff < 0).sum())})
    return pd.DataFrame(out)


def forecasting() -> None:
    vs = b0_corrected()
    vs.to_csv(TAB / "phase7_prevision_vs_B0.csv", index=False)
    print(vs.round(4).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("etape", choices=["preparer", "prevision"])
    {"preparer": prepare, "prevision": forecasting}[ap.parse_args().etape]()
