"""Étape 40 : récolte 2026, pré-lecture exploratoire.

Usage : uv run python scripts/40_recolte_2026.py
Entrées : data/raw/meteofrance_sim/QUOT_SIM2_2025.csv.gz et QUOT_SIM2_2026.csv.gz ;
          data/raw/agreste_conjoncture/2026_131donnees_grandescultures_departements.xlsx (estimations au 1er octobre 2026) ;
          poids des masques maïs et blé ; forecast_features.parquet (2010-2025).
Sorties : data/processed/panel_mais_2026.parquet (17 + 21 départements, deux modes, rendements provisoires et météo) ;
          reports/tables/phase7_recolte_2026_controle_2025.csv, phase7_p4_prevision_ble_2026.csv.

Aucun fichier existant n'est modifié : la météo 2026 est calculée à part, avec les mêmes fonctions que l'étape 5
(double sinus, agrégation mensuelle, masques fixes). Décembre 2025 est recalculé ici avec le 1er janvier 2026, qui
manquait lors du calcul initial (le mois y est marqué manquant).
La spécification figée (specification_recoltes_futures.md) exige des chiffres définitifs : rien ici n'en est le test.
"""

import hashlib

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

from atlas import forecast as fc
from atlas.download import ROOT
from atlas.spatial import weighted_mean
from atlas.weather import MEAN_VARS, SUM_VARS, daily_indicators, harvest_year_windows, monthly, read_year

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
TAB = ROOT / "reports" / "tables"
SIM = RAW / "meteofrance_sim"
CONJ = RAW / "agreste_conjoncture" / "2026_131donnees_grandescultures_departements.xlsx"
FC_WINDOWS = {"automne": [(-1, 9), (-1, 10), (-1, 11)], "hiver": [(-1, 12), (0, 1), (0, 2)],
              "printemps": [(0, 3), (0, 4)], "remplissage": [(0, 5), (0, 6)], "mai": [(0, 5)]}   # comme l'étape 14


def cell_months_2026() -> pd.DataFrame:
    """Maille × mois : décembre 2025 (recalculé avec le 1er janvier 2026) et janvier-septembre 2026."""
    w = pd.read_parquet(PROC / "weights_cell_dep_area.parquet")[["LAMBX", "LAMBY"]].drop_duplicates()
    dec = monthly(daily_indicators(read_year(SIM / "QUOT_SIM2_2025.csv.gz", SIM / "QUOT_SIM2_2026.csv.gz")
                                   .merge(w, on=["LAMBX", "LAMBY"])))
    dec = dec[dec.month == 12]
    y26 = monthly(daily_indicators(read_year(SIM / "QUOT_SIM2_2026.csv.gz").merge(w, on=["LAMBX", "LAMBY"])))
    y26 = y26[y26.month <= 9]                 # le fichier s'arrête au 1er octobre 2026
    out = pd.concat([dec, y26], ignore_index=True)
    if not (out[SUM_VARS + MEAN_VARS].notna().all().all()):
        raise SystemExit("mois incomplets dans la météo 2026")
    return out


def conjoncture() -> pd.DataFrame:
    """Rendements de maïs grain irrigué et non irrigué par département, 2025 (SAA définitive) et 2026 (estimations)."""
    raw = pd.read_excel(CONJ, sheet_name="grandes_cultures", header=None)
    if not ("arrêtées au 1er octobre 2026" in str(raw.iloc[5, 0])):
        raise SystemExit("le fichier de conjoncture n'est pas celui des estimations au 1er octobre 2026")
    if not (str(raw.iloc[6, 15]).startswith("2025") and str(raw.iloc[6, 18]).startswith("2026")):
        raise SystemExit("colonnes 2025 et 2026 du fichier de conjoncture déplacées")
    d = raw.iloc[8:, :21].copy()
    d.columns = ["region", "dep", "culture"] + [f"{y}_{v}" for y in range(2021, 2027) for v in ["surface", "rdt", "prod"]]
    d["culture"] = d.culture.astype(str).str.strip()
    d = d[d.culture.isin(["Maïs grain irrigué", "Maïs grain non irrigué"]) & d.dep.notna()]
    d["dep_code"] = d.dep.astype(str).str.split(" - ").str[0].str.zfill(2)
    d["modalite"] = np.where(d.culture == "Maïs grain irrigué", "irrigue", "non_irrigue")
    out = d[["dep_code", "modalite", "2025_rdt", "2026_rdt", "2026_surface"]].rename(
        columns={"2025_rdt": "rdt_2025_definitif", "2026_rdt": "rendement_q_ha", "2026_surface": "surface_1000ha"})
    for c in ["rdt_2025_definitif", "rendement_q_ha", "surface_1000ha"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    if not (not out.duplicated(["dep_code", "modalite"]).any()):
        raise SystemExit("doublons département × modalité dans la conjoncture 2026")
    return out


def main() -> None:
    cm = cell_months_2026()
    maize_w = pd.read_parquet(PROC / "weights_cell_dep_maize.parquet")
    dm = weighted_mean(cm, maize_w, SUM_VARS + MEAN_VARS, "w_maize", ["year", "month"])
    ja = harvest_year_windows(dm, [2026], windows={"ja": [(0, 7), (0, 8)]})[["dep_code", "annee", "dd_32_ja", "swi_ja"]]

    # Panel 2026 : mêmes 38 départements et même échantillon principal que le panel 2000-2025.
    old = pd.read_parquet(PROC / "panel_mais_long.parquet")
    ref = old.drop_duplicates("dep_code")[["dep_code", "surface_ref_ha", "statut_irrigue", "echantillon_principal"]]
    conj = conjoncture()
    p26 = conj[conj.dep_code.isin(ref.dep_code)].merge(ref, on="dep_code", validate="many_to_one")
    p26 = p26.merge(ja, on="dep_code", how="left", validate="many_to_one")
    if not (p26.dep_code.nunique() == 38 and p26.dd_32_ja.notna().all()):
        raise SystemExit("département sans météo ou absent")
    p26["log_rendement"] = np.log(p26.rendement_q_ha)
    p26.to_parquet(PROC / "panel_mais_2026.parquet", index=False)
    print(f"panel 2026 : {len(p26)} lignes, {p26.rendement_q_ha.isna().sum()} rendements manquants ; "
          f"dd_32_ja moyen (17 dép.) {np.average(ja[ja.dep_code.isin(ref[ref.echantillon_principal].dep_code)].dd_32_ja):.1f}")

    # (a) Contrôle : 2025 du fichier (SAA définitive) contre 2025 du panel (SAA provisoire), 17 départements.
    p25 = old[(old.annee == 2025) & old.echantillon_principal][["dep_code", "modalite", "rendement_q_ha"]]
    c = p25.merge(conj[["dep_code", "modalite", "rdt_2025_definitif"]], on=["dep_code", "modalite"], how="left",
                  validate="one_to_one")
    c["ecart_q_ha"] = c.rdt_2025_definitif - c.rendement_q_ha
    c.to_csv(TAB / "phase7_recolte_2026_controle_2025.csv", index=False)
    print(f"2025 définitif − provisoire : médiane {c.ecart_q_ha.median():+.1f} q/ha, max |écart| {c.ecart_q_ha.abs().max():.1f}")

    # (d) Prévision figée du blé 2026 au 1er juillet (spécification figée, § 2), avant toute comparaison.
    wheat_w = pd.read_parquet(PROC / "weights_cell_dep_wheat.parquet")
    dw = weighted_mean(cm, wheat_w, SUM_VARS + MEAN_VARS, "w_wheat", ["year", "month"])
    old_w = pd.read_parquet(PROC / "weather_dep_month_wheat.parquet")
    dw_all = pd.concat([old_w[(old_w.year == 2025) & old_w.month.isin([9, 10, 11])], dw], ignore_index=True)
    h = harvest_year_windows(dw_all, [2026], windows=FC_WINDOWS)
    for win in FC_WINDOWS:
        h[f"gdd_0_32_{win}"] = h[f"dd_0_{win}"] - h[f"dd_32_{win}"]
    feat = pd.read_parquet(PROC / "forecast_features.parquet")
    feat = feat[feat.echantillon_principal]
    test = feat[feat.annee == 2025][["dep_code", "surface_ref_ha"]].assign(annee=2026, log_rendement=np.nan)
    test = test.merge(h, on=["dep_code", "annee"], how="left", validate="one_to_one")
    cols = fc.features("juillet")
    if not (test[cols].notna().all().all()):
        raise SystemExit("variables de prévision manquantes en 2026")
    train = feat[(feat.annee >= 2010) & (feat.annee <= 2025)]
    b0_tr = train.groupby("dep_code").log_rendement.transform("mean").to_numpy()
    b0_te = fc.predict_b0(train, test)
    resid, w = train.log_rendement.to_numpy() - b0_tr, train.surface_ref_ha.to_numpy()
    xtr, xte = fc.center_by_dep(train, test, cols)
    xtr, xte = fc.standardize(xtr, xte)
    rf = RandomForestRegressor(n_estimators=500, min_samples_leaf=10, max_features=1 / 3, random_state=fc.SEED, n_jobs=-1)
    gbm = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=20,
                                        early_stopping=False, random_state=fc.SEED)
    pred = test[["dep_code", "annee", "surface_ref_ha"]].assign(
        B0=b0_te, RF_B0=b0_te + rf.fit(xtr, resid, sample_weight=w).predict(xte),
        GBM_B0=b0_te + gbm.fit(xtr, resid, sample_weight=w).predict(xte))
    out = TAB / "phase7_p4_prevision_ble_2026.csv"
    pred.round(6).to_csv(out, index=False)
    print(f"prévision du blé 2026 enregistrée : {len(pred)} départements ; "
          f"SHA-256 {hashlib.sha256(out.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
