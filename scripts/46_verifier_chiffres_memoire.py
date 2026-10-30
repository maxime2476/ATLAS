"""Étape 46 : vérification des chiffres du mémoire, macros générées et chiffres écrits à la main.

Usage : uv run python scripts/46_verifier_chiffres_memoire.py
Entrées : memoire/tables/numbers.tex et relief.tex, memoire/chapters/*.tex, données de data/ et tables de reports/tables/.
Sorties : reports/tables/verification_chiffres_memoire.csv (un chiffre par ligne : valeur exacte, valeur du texte, statut)
          et reports/tables/verification_chiffres_en_dur.csv (inventaire de tous les nombres écrits en dur dans le .tex).

Principe. La partie A recalcule chaque chiffre à partir des données, sans importer scripts/26_tables_memoire.py :
les formules sont réécrites ici (régressions à effets fixes comprises), puis arrondies comme dans le texte et
comparées à la macro de numbers.tex. Quand un chiffre vient d'une simulation en R (tailles, placebos), il n'est pas
resimulé : on contrôle seulement le passage du CSV au texte, et le statut le dit (« CSV → texte »).
La partie B inventorie les nombres écrits en dur dans le .tex et les rattache à un contrôle, une constante de
conception ou une source externe ; tout nombre non rattaché est marqué « à examiner ».
Le script ne modifie aucun fichier du mémoire.
"""

import io
import json
import re
import zipfile

import numpy as np
import pandas as pd

from atlas.download import ROOT
from atlas.saa import read_sheet_wide, to_long

PROC = ROOT / "data" / "processed"
TAB = ROOT / "reports" / "tables"
MEM = ROOT / "memoire"
ROWS = []          # résultats de la partie A


# --- Outils --------------------------------------------------------------------------------------------------------

def read_macros() -> dict:
    text = (MEM / "tables" / "numbers.tex").read_text()
    return dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", text))


MACROS = read_macros()
TEX = {p.name: p.read_text() for p in sorted((MEM / "chapters").glob("*.tex"))}
ALL_TEX = "\n".join(TEX.values())


def check(item: str, exact: float, digits: int, macro: str | None = None, literal: str | None = None,
          scale: float = 1.0, note: str = "") -> None:
    """Compare la valeur recalculée, arrondie à `digits` décimales, à la macro ou au texte littéral.

    `macro` : nom de la macro de numbers.tex ; on vérifie aussi qu'elle est appelée dans un chapitre.
    `literal` : chiffre écrit à la main dans le .tex (contrôle de présence dans le texte).
    """
    value = exact * scale
    rounded = f"{value:,.{digits}f}"
    if macro is not None:
        shown = MACROS.get(macro, "ABSENTE")
        used = re.search(rf"\\{macro}(?![A-Za-z])", ALL_TEX) is not None
        source = f"\\{macro}" + ("" if used else " (non appelée)")
    else:
        shown = literal
        source = "écrit en dur" + ("" if literal in ALL_TEX else " (introuvable)")
    if shown is not None and "," not in shown:          # séparateur de milliers seulement si le texte en met un
        rounded = rounded.replace(",", "")
    # Écart de dernier chiffre seulement si la valeur exacte tombe sur une demi-unité (arrondi à l'affichage).
    status = "OK" if rounded == shown else "ÉCART"
    if status == "ÉCART" and shown not in ("ABSENTE", None):
        try:
            half = abs(abs(value - float(shown.replace(",", ""))) - 0.5 * 10 ** -digits) < 1e-9
            status = "ÉCART (demi-unité)" if half else status
        except ValueError:
            pass
    ROWS.append({"chiffre": item, "valeur_exacte": f"{value:.6g}" if abs(value) < 1e6 else f"{value:.0f}",
                 "arrondi_recalcule": rounded, "texte": shown, "source_texte": source, "statut": status, "note": note})


def demean(df: pd.DataFrame, groups: list[pd.Series], w: pd.Series, tol: float = 1e-12) -> pd.DataFrame:
    """Retire des effets fixes (plusieurs dimensions) par projections alternées pondérées."""
    m = df.astype(float).copy()
    sw = [w.groupby(g).transform("sum") for g in groups]
    for _ in range(10_000):
        old = m.copy()
        for g, s in zip(groups, sw):
            m = m - m.mul(w, axis=0).groupby(g).transform("sum").div(s, axis=0)
        if (m - old).abs().to_numpy().max() < tol:
            return m
    raise RuntimeError("projections alternées non convergées")


def fe_wls(df: pd.DataFrame, y: str, xs: list[str], fes: list[str], w: str | None) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Moindres carrés pondérés à effets fixes (Frisch-Waugh-Lovell) : coefficients, résidus, variables démoyennées."""
    weights = df[w] if w else pd.Series(1.0, index=df.index)
    z = demean(df[[y] + xs], [df[f] for f in fes], weights)
    X, Y, W = z[xs].to_numpy(), z[y].to_numpy(), weights.to_numpy()
    beta = np.linalg.solve(X.T @ (W[:, None] * X), X.T @ (W * Y))
    return pd.Series(beta, index=xs), pd.Series(Y - X @ beta, index=df.index), z


def maize_pairs() -> pd.DataFrame:
    """Paires irrigué / pluvial de l'échantillon principal (435 département-années), comme le modèle A1."""
    m = pd.read_parquet(PROC / "panel_mais_long.parquet")
    m = m[m.echantillon_principal]
    irr = m[m.modalite == "irrigue"]
    non = m[m.modalite == "non_irrigue"][["dep_code", "annee", "rendement_q_ha", "log_rendement", "surface_ha"]]
    d = irr.merge(non, on=["dep_code", "annee"], suffixes=("", "_non"))
    d["ecart_log"] = d.log_rendement - d.log_rendement_non
    return d.sort_values(["dep_code", "annee"]).reset_index(drop=True)


def year_shares(df: pd.DataFrame, resid: pd.Series, w: pd.Series | None = None) -> pd.Series:
    """Part de chaque année dans la somme (pondérée) des carrés de la chaleur résiduelle."""
    w = pd.Series(1.0, index=df.index) if w is None else w
    s = (w * resid ** 2).groupby(df.annee).sum()
    return s / s.sum()


# --- A.1 Introduction et données ---------------------------------------------------------------------------------

def intro_and_data() -> None:
    d = maize_pairs()
    heat = d.groupby("annee").apply(lambda g: np.average(g.dd_32_ja, weights=g.surface_ref_ha), include_groups=False)
    check("Chaleur moyenne de juillet-août 2003 (DD > 32 °C)", heat[2003], 1, "HeatTwoThousandThree")
    check("2003 / été suivant le plus chaud depuis 2000", heat[2003] / heat.drop(2003).max(), 1, "HeatRatio",
          note=f"deuxième été : {heat.drop(2003).idxmax()} ({heat.drop(2003).max():.3f} DD)")

    # Raccord des deux éditions de la SAA sur 2010-2020 (rendements maïs grain irrigué / non irrigué).
    mod = {"Maïs grain irrigué": "irrigue", "Maïs grain non irrigué": "non_irrigue"}
    z = zipfile.ZipFile(ROOT / "data" / "raw" / "agreste_saa_ancienne" / "FDS_DEVELOPPE_2.zip")
    old = []
    for y in range(2010, 2021):
        t = pd.read_csv(io.BytesIO(z.read(f"FDS_DEVELOPPE_{y}.csv")), sep=";", dtype=str)
        t = t[t.N306_LIB.isin(mod) & (t.N027_LIB == "Rendement") & (t.DEP != "...")]
        old.append(pd.DataFrame({"dep_code": t.DEP, "annee": t.ANNREF.astype(int), "modalite": t.N306_LIB.map(mod),
                                 "ancien": pd.to_numeric(t.VALEUR, errors="coerce")}))
    old = pd.concat(old)
    saa = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    new = saa[saa.culture_code.isin(["14", "15"]) & saa.metropole].assign(
        modalite=lambda s: s.culture_code.map({"14": "irrigue", "15": "non_irrigue"}))
    j = old.merge(new[["dep_code", "annee", "modalite", "rendement_q_ha"]], on=["dep_code", "annee", "modalite"])
    j = j.dropna(subset=["ancien", "rendement_q_ha"])
    j = j[(j.ancien > 0) & (j.rendement_q_ha > 0)]
    diff = j.ancien - j.rendement_q_ha
    check("Raccord SAA : paires département-année-mode", len(j), 0, "SpliceN")
    check("Raccord SAA : part d'accord à 0,5 q/ha (%)", (diff.abs() <= 0.5).mean(), 0, "SpliceShare", scale=100)
    check("Raccord SAA : différence médiane (q/ha)", diff.median(), 1, "SpliceMedian")
    for mode, macro in [("irrigue", "SpliceCorrIrr"), ("non_irrigue", "SpliceCorrRain")]:
        s = j[j.modalite == mode]
        check(f"Raccord SAA : corrélation ({mode})", s.ancien.corr(s.rendement_q_ha), 2, macro)

    w = pd.read_parquet(PROC / "panel_ble.parquet")
    integer = (w.rendement_q_ha - w.rendement_q_ha.round()).abs() < 1e-9
    check("Blé 2010-2025 : rendements entiers en q/ha (%)", integer.mean(), 1, "WheatIntegerShare", scale=100,
          note=f"85 départements de la population ; {integer[w.echantillon_principal].mean():.2%} sur les 83 du principal")

    # Code RPG MIS contre la SAA, départements-millésimes avec plus de 2 000 ha de MIS, 2015-2017.
    rpg = pd.read_parquet(PROC / "maize_area_cell_dep_rpg.parquet").groupby(["dep_code", "millesime"]).surf_ha.sum()
    rpg.index.names = ["dep_code", "annee"]
    grain = saa[(saa.culture_code == "18") & saa.metropole & saa.annee.between(2015, 2017)].set_index(["dep_code", "annee"]).surface_ha
    fou = to_long(read_sheet_wide(ROOT / "data" / "raw" / "agreste_saa" /
                                  "SAA-SeriesLongues-2010-2025_DonneesProvisoires-DepartementalesRegionales.zip", "FOU"))
    fodder = fou[(fou.culture_code == "06") & fou.metropole & fou.annee.between(2015, 2017)].set_index(["dep_code", "annee"]).surface_ha
    c = pd.concat([rpg.rename("rpg"), grain.rename("grain"), fodder.rename("fodder")], axis=1).fillna(0)
    c = c[c.rpg > 2000]
    check("Corrélation MIS / maïs grain SAA", c.rpg.corr(c.grain), 3, "MaskCorrGrain", note=f"{len(c)} département-millésimes")
    check("Corrélation MIS / maïs fourrage SAA", c.rpg.corr(c.fodder), 2, "MaskCorrFodder")

    # VigiEau : part des arrêtés sans niveau de gravité, recalculée depuis le fichier brut (sans l'arrondi à 3 décimales).
    a = pd.read_csv(ROOT / "data" / "raw" / "vigieau" / "arretes.csv", dtype=str).drop_duplicates("id")
    a["debut"] = pd.to_datetime(a.date_debut, errors="coerce")
    a = a.dropna(subset=["debut", "departement"])
    miss = a.groupby(a.debut.dt.year)["zones_alerte.niveau_gravite"].apply(lambda s: s.isna().mean()) * 100
    for (first, last), (lo, hi) in [((2012, 2015), ("VigiMissEarlyMin", "VigiMissEarlyMax")),
                                    ((2016, 2022), ("VigiMissMidMin", "VigiMissMidMax"))]:
        p = miss.loc[first:last]
        check(f"VigiEau sans niveau, minimum {first}-{last} (%)", p.min(), 0, lo, note=f"année {p.idxmin()}")
        check(f"VigiEau sans niveau, maximum {first}-{last} (%)", p.max(), 0, hi, note=f"année {p.idxmax()}")


# --- A.2 Mesure de la chaleur et altitudes -------------------------------------------------------------------------

def exposure_and_altitude() -> None:
    def n_eff(shares: pd.Series) -> float:
        return 1 / (shares ** 2).sum()

    deps = pd.read_parquet(PROC / "panel_ble.parquet").dep_code.unique()       # population blé (85 départements)
    for suffix, label, macro in [("", "2010-2025", "NeffWheatExact"), ("_1959", "1959-2025", "NeffWheatLong")]:
        h = pd.read_parquet(PROC / f"weather_dep_harvest_wheat{suffix}.parquet")
        h = h[h.dep_code.isin(deps)].reset_index(drop=True)
        if not (len(h) == h.dep_code.nunique() * h.annee.nunique()):
            raise SystemExit("panel blé non équilibré")
        r = demean(h[["dd_32_remplissage"]], [h.dep_code, h.annee], pd.Series(1.0, index=h.index)).dd_32_remplissage
        check(f"N_eff blé {label}", n_eff(year_shares(h, r)), 2 if suffix == "" else 1, macro,
              note=f"{h.annee.nunique()} années")
        if suffix == "":
            h25 = h[h.annee != 2025].reset_index(drop=True)
            r25 = demean(h25[["dd_32_remplissage"]], [h25.dep_code, h25.annee], pd.Series(1.0, index=h25.index)).dd_32_remplissage
            check("N_eff blé 2010-2024 (sans 2025)", n_eff(year_shares(h25, r25)), 2, "NeffWheatNoTwentyFive")

    # Maïs, sans poids ni SWI : le texte utilise la formule x - moyenne dép. - moyenne année + moyenne générale,
    # exacte pour un panel équilibré ; ici 435 paires sur 17 x 26 = 442. On recalcule les deux versions.
    d = maize_pairs()
    x = d.dd_32_ja
    approx = x - d.groupby("dep_code").dd_32_ja.transform("mean") - d.groupby("annee").dd_32_ja.transform("mean") + x.mean()
    exact = demean(d[["dd_32_ja"]], [d.dep_code, d.annee], pd.Series(1.0, index=d.index)).dd_32_ja
    s_approx, s_exact = year_shares(d, approx), year_shares(d, exact)
    check("N_eff maïs 2000-2025 (sans poids ni SWI)", n_eff(s_approx), 1, "NeffMaize",
          note=f"formule du panel équilibré ; projection exacte : {n_eff(s_exact):.2f}")
    check("Part de 2003 dans la variance résiduelle (sans poids ni SWI, %)", s_approx[2003], 0,
          "NeffMaizeShareTwoThousandThree", scale=100, note=f"projection exacte : {100 * s_exact[2003]:.1f} %")

    # Modèle pondéré avec SWI : chaleur résiduelle après effets fixes et SWI (Frisch-Waugh-Lovell pondéré).
    for period, macro_share, macro_neff in [((2000, 2025), "LevThree", "NeffLevAll"), ((2000, 2009), "LevThreeEarly", "NeffLevEarly")]:
        sub = d[d.annee.between(*period)].reset_index(drop=True)
        _, xt, _ = fe_wls(sub, "dd_32_ja", ["swi_ja"], ["dep_code", "annee"], "surface_ref_ha")
        sh = year_shares(sub, xt, sub.surface_ref_ha)
        check(f"Part de 2003 dans le levier partiel, {period[0]}-{period[1]} (%)", sh[2003], 0, macro_share, scale=100)
        check(f"N_eff du modèle pondéré avec SWI, {period[0]}-{period[1]}", n_eff(sh), 1, macro_neff)
        if period == (2000, 2025):
            check("Levier de 2003 / levier moyen d'une année", sh[2003] * len(sh), 1, "LevTwoThousandThreeRatio")
            check("Levier de la deuxième année (%)", sh.drop(2003).max(), 0, "LevSecond", scale=100)
            check("Deuxième année par le levier", sh.drop(2003).idxmax(), 0, "LevSecondYear")

    # Altitudes (tableau 5) : différences calculées sur les valeurs non arrondies.
    mes = pd.read_csv(TAB / "phase4bis_q1_mesures_departement.csv", dtype={"dep_code": str})
    alt = pd.read_parquet(PROC / "cell_altitude.parquet")
    for wfile, wcol, col in [("weights_cell_dep_maize", "w_maize", "alt_maize"), ("weights_cell_dep_area", "w_area", "alt_area")]:
        w = pd.read_parquet(PROC / f"{wfile}.parquet").merge(alt, on=["LAMBX", "LAMBY"]).dropna(subset=["altitude_moy_m"])
        mes[col] = mes.dep_code.map(w.groupby("dep_code").apply(lambda g: np.average(g.altitude_moy_m, weights=g[wcol]),
                                                               include_groups=False))
    mes["alt_gap"] = mes.alt_area - mes.alt_maize
    mes["alt_gap_rounded_cols"] = mes.alt_area.round() - mes.alt_maize.round()
    big = mes[mes.ecart_surface_moins_masque_2003 < -3]
    lo, hi = big.loc[big.alt_gap.idxmin()], big.loc[big.alt_gap.idxmax()]
    check("Écart d'altitude minimal, 6 départements de relief (m)", lo.alt_gap, 0, "ReliefAltDiffMin",
          note=f"dép. {lo.dep_code} : {lo.alt_area:.2f} - {lo.alt_maize:.2f} ; colonnes arrondies du tableau : {lo.alt_gap_rounded_cols:.0f}")
    check("Écart d'altitude maximal, 6 départements de relief (m)", hi.alt_gap, 0, "ReliefAltDiffMax",
          note=f"dép. {hi.dep_code} : {hi.alt_area:.2f} - {hi.alt_maize:.2f} ; colonnes arrondies du tableau : {hi.alt_gap_rounded_cols:.0f}")
    check("Corrélation écart de chaleur / écart d'altitude (17 départements)",
          mes.ecart_surface_moins_masque_2003.corr(mes.alt_gap), 2, "ReliefAltCorr")
    # Le tableau relief.tex doit afficher les mêmes altitudes arrondies que celles recalculées ici.
    table = (MEM / "tables" / "relief.tex").read_text()
    wrong = []
    for r in mes.itertuples():
        row = re.search(rf"\({r.dep_code}\)(.*)\\\\", table).group(1).split("&")
        if (int(row[-2]), int(row[-1])) != (round(r.alt_maize), round(r.alt_area)):
            wrong.append(r.dep_code)
    ROWS.append({"chiffre": "Tableau 5 : altitudes affichées des 17 départements", "valeur_exacte": "",
                 "arrondi_recalcule": "", "texte": "", "source_texte": "relief.tex",
                 "statut": "OK" if not wrong else "ÉCART", "note": " ".join(wrong)})


# --- A.3 Inférence et résultats maïs ------------------------------------------------------------------------------

def ar1(df: pd.DataFrame, resid: pd.Series) -> float:
    """Autocorrélation d'ordre 1 des résidus, années consécutives d'un même département (comme R/18)."""
    e = pd.DataFrame({"u": df.dep_code, "t": df.annee, "e": resid}).sort_values(["u", "t"])
    lag = e.groupby("u").e.shift()
    ok = lag.notna() & (e.groupby("u").t.diff() == 1)
    return np.corrcoef(e.e[ok], lag[ok])[0, 1]


def inference_and_maize() -> None:
    d = maize_pairs()
    beta, res, _ = fe_wls(d, "ecart_log", ["dd_32_ja", "swi_ja"], ["dep_code", "annee"], "surface_ref_ha")
    b = beta["dd_32_ja"]
    check("β de A1 (contrôle de la régression réécrite)", b, 4, "QoneBeta")
    check("Autocorrélation d'ordre 1 des résidus, maïs A1", ar1(d, res), 2, "ArMaize")

    w = pd.read_parquet(PROC / "panel_ble_1959.parquet")
    w = w[w.echantillon_principal & w.rendement_q_ha.notna()].reset_index(drop=True)
    w["dep_periode"] = w.dep_code + "_" + pd.cut(w.annee, [-np.inf, 1988, 2009, np.inf], labels=["a", "b", "c"]).astype(str)
    rhs = ["gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne"]
    _, res_w, _ = fe_wls(w, "log_rendement", rhs, ["dep_periode", "annee"], "surface_ref_ha")
    check("Autocorrélation d'ordre 1 des résidus, blé 1959-2025 (M3)", ar1(w, res_w), 2, "ArWheat")

    # Simulations en R (non resimulées ici) : contrôle CSV -> texte.
    s3 = pd.read_csv(TAB / "phase7_correlation_serielle.csv").set_index("rho").taille_5pct
    for rho, macro in [(0.0, "SerialSizeZero"), (0.3, "SerialSizeLow"), (0.6, "SerialSizeHigh")]:
        check(f"Simulation AR(1), rejet du WCR pour rho = {rho} (%)", s3[rho], 1, macro, scale=100, note="CSV → texte (R/26)")
    sz = pd.read_csv(TAB / "phase7_tailles.csv").set_index("diagnostic").taux
    check("Matrices de Conley corrigées par fixest (%)", sz[sz.index.str.startswith("matrices de Conley")].iloc[0], 0, "ConleyFixedPct",
          scale=100, note="CSV → texte (R/22)")

    # Rendements et écart médian.
    check("Rendement moyen irrigué (q/ha)", d.rendement_q_ha.mean(), 0, "YieldIrr")
    check("Rendement moyen pluvial (q/ha)", d.rendement_q_ha_non.mean(), 0, "YieldRain")
    ratio = d.rendement_q_ha / d.rendement_q_ha_non
    check("Écart médian irrigué / pluvial (%)", ratio.median() - 1, 0, "GapMedianPct", scale=100)
    check("Paires irrigué > pluvial", (ratio > 1).sum(), 0, "GapAboveCount")
    check("Paires irrigué = pluvial", (d.rendement_q_ha == d.rendement_q_ha_non).sum(), 0, "GapEqualCount")
    check("Paires irrigué < pluvial", (ratio < 1).sum(), 0, "GapBelowCount")
    check("Nombre de paires de l'échantillon principal", len(d), 0, "MaizeMainPairs")

    # Rapports répétés d'une année sur l'autre (rapport arrondi au centième), et référence par permutation.
    def repeat_flags(df: pd.DataFrame) -> pd.Series:
        r = (df.rendement_q_ha / df.rendement_q_ha_non).round(2)
        return (r == r.groupby(df.dep_code).shift()) & (df.groupby("dep_code").annee.diff() == 1)
    rep = repeat_flags(d)
    denom = len(d) - d.dep_code.nunique()
    check("Rapports répétés (%)", rep.sum() / denom, 1, "SaaRepPct", scale=100, note=f"{rep.sum()} sur {denom} paires successives")
    check("Rapports répétés : nombre", rep.sum(), 0, "SaaRepTot")
    check("Rapports répétés : dont 2000-2009", rep[d.annee <= 2009].sum(), 0, "SaaRepOld")
    check("Rapports répétés : dont 2003", rep[d.annee == 2003].sum(), 0, "SaaRepTwoThousandThree")
    rng = np.random.default_rng(123)
    ref = []
    for _ in range(1000):
        sim = d.copy()
        sim["rendement_q_ha_non"] = sim.groupby("dep_code").rendement_q_ha_non.transform(lambda v: rng.permutation(v.to_numpy()))
        ref.append(repeat_flags(sim).sum() / denom)
    ref = np.array(ref) * 100
    # Tirages différents de ceux de R (numpy contre R) : on accepte un écart de Monte-Carlo de 0,3 point.
    for label, val, macro in [("médiane", np.median(ref), "SaaRepRefPct"), ("95e centile", np.quantile(ref, 0.95), "SaaRepPnf")]:
        csv = pd.read_csv(TAB / "phase7_signatures_saa.csv").iloc[0]
        csv_val = 100 * (csv.s2_ref_mediane if label == "médiane" else csv.s2_ref_p95)
        check(f"Rapports répétés, permutation : {label} (%)", csv_val, 1, macro,
              note=f"CSV (R, 1 000 permutations) ; recalcul numpy : {val:.2f} %, écart {'≤' if abs(val - csv_val) <= 0.3 else '>'} 0,3 point")

    # Valorisation de 2003 : surface irriguée x rendement pluvial x (exp(beta x excès de chaleur) - 1) x prix.
    price = pd.read_parquet(PROC / "prix_mais.parquet").set_index("annee").prix_eur_q
    dev = d.dd_32_ja - d.groupby("dep_code").dd_32_ja.transform("mean")
    y3 = d.annee == 2003
    ci = pd.read_csv(TAB / "phase4bis_q1_verif_intervalles.csv")
    ci = ci[ci.modele.str.startswith("A1") & (ci.niveau == 0.90)].iloc[0]
    def value(beta_):
        return (d.surface_ha[y3] * d.rendement_q_ha_non[y3] * (np.exp(beta_ * dev[y3]) - 1)).sum()
    check("Valeur 2003 (M EUR)", value(b) * price[2003] / 1e6, 0, "QoneValTwoThousandThree")
    check("Valeur 2003, borne basse (M EUR)", value(ci.borne_inf) * price[2003] / 1e6, 0, "QoneValLow",
          note="borne de l'intervalle à 90 % de β (inversion du bootstrap, CSV R)")
    check("Valeur 2003, borne haute (M EUR)", value(ci.borne_sup) * price[2003] / 1e6, 0, "QoneValHigh")
    m = pd.read_parquet(PROC / "panel_mais_long.parquet")
    m3 = m[m.echantillon_principal & (m.annee == 2003)]
    prod = (m3.surface_ha * m3.rendement_q_ha).sum()
    check("Valeur de toute la récolte 2003 des 17 départements (M EUR)", prod * price[2003] / 1e6, 0, "ProdValTwoThousandThree")
    check("Part de la récolte 2003 (%)", value(b) / prod, 0, "ValShareTwoThousandThree", scale=100)
    gap_dev = d.ecart_log - d.groupby("dep_code").ecart_log.transform("mean")
    obs = np.average(gap_dev[y3], weights=d.surface_ref_ha[y3])
    pred = b * np.average(dev[y3], weights=d.surface_ref_ha[y3])
    # Fourchette de mesure de 2003 : écart observé à la place de beta x excès de chaleur,
    # hors paires reconduites (deux rendements identiques à l'année précédente), et prix Eurostat observé.
    def value_obs(mask):
        return (d.surface_ha[mask] * d.rendement_q_ha_non[mask] * (np.exp(gap_dev[mask]) - 1)).sum()
    def value_f(mask):
        return (d.surface_ha[mask] * d.rendement_q_ha_non[mask] * (np.exp(b * dev[mask]) - 1)).sum()
    g = d.groupby("dep_code")
    rep = ((d.rendement_q_ha == g.rendement_q_ha.shift()) & (d.rendement_q_ha_non == g.rendement_q_ha_non.shift())
           & (g.annee.diff() == 1))
    keep = y3 & ~rep
    check("Paires reconduites en 2003", (y3 & rep).sum(), 0, "ValRepPairs")
    check("Surestimation de 2003 par la formule, poids de la valorisation (%)", value(b) / value_obs(y3) - 1, 0,
          "ValOverPct", scale=100)
    check("Surestimation de 2003 hors paires reconduites (%)", value_f(keep) / value_obs(keep) - 1, 0,
          "ValOverNoRepPct", scale=100)
    with open(ROOT / "data" / "raw" / "prix" / "eurostat_apri_ap_crpouta_FR_mais.json") as f:
        js = json.load(f)
    years = {v: int(k) for k, v in js["dimension"]["time"]["category"]["index"].items()}
    eurostat = {years[int(k)]: v for k, v in js["value"].items()}
    q_f, q_o = value(b), value_obs(y3)
    q_o2 = q_f * value_obs(keep) / value_f(keep)
    vals = [q * pr / 1e6 for q in (q_f, q_o, q_o2) for pr in (price[2003], eurostat[2003])]
    check("Prix Eurostat observé 2003 (EUR/q)", eurostat[2003], 1, "PriceEurostatThree")
    check("Prix raccordé 2003 (EUR/q)", price[2003], 1, "PriceRaccordThree")
    check("Valeur 2003 au prix Eurostat (M EUR)", vals[1], 0, "QoneValEurostat")
    check("Valeur 2003, écart observé (M EUR)", vals[2], 0, "QoneValObs")
    check("Valeur 2003, écart observé hors reconduites (M EUR)", vals[4], 0, "QoneValObsNoRep")
    check("Fourchette 2003, borne basse (M EUR)", min(vals), 0, "QoneValRangeLow")
    check("Fourchette 2003, borne haute (M EUR)", max(vals), 0, "QoneValRangeHigh")
    check("Valeur de toute la récolte 2003 au prix Eurostat (M EUR)", prod * eurostat[2003] / 1e6, 0,
          "ProdValTwoThousandThreeEurostat")
    for yr, macro in [(2019, "QoneValObsNineteen"), (2022, "QoneValObsTwentyTwo")]:
        check(f"Valeur {yr}, écart observé (M EUR)", value_obs(d.annee == yr) * price[yr] / 1e6, 0, macro)
    q = d.assign(dd_32_ja_carre=d.dd_32_ja ** 2)
    bq, _, _ = fe_wls(q, "ecart_log", ["dd_32_ja", "dd_32_ja_carre", "swi_ja"], ["dep_code", "annee"], "surface_ref_ha")
    dev2 = q.dd_32_ja_carre - q.groupby("dep_code").dd_32_ja_carre.transform("mean")
    pred_q = np.average((bq["dd_32_ja"] * dev + bq["dd_32_ja_carre"] * dev2)[y3], weights=d.surface_ref_ha[y3])
    check("Écart prédit en 2003 avec terme quadratique (log)", pred_q, 3, "QuadPredThree")
    check("Écart prédit en 2003, modèle linéaire (macro du § 7.10)", pred, 3, "LinPredThree")
    check("Écart observé en 2003 (macro du § 7.10)", obs, 3, "ObsThree")


# --- B. Chiffres écrits en dur --------------------------------------------------------------------------------------

def hardcoded() -> list[dict]:
    """Contrôles des chiffres saisis à la main : (fichier, extrait du .tex, valeur recalculée, statut)."""
    out = []

    def add(file, snippet, exact, status, note=""):
        found = snippet in TEX[file]
        out.append({"fichier": file, "extrait": snippet, "valeur_code": exact,
                    "statut": status if found else "EXTRAIT INTROUVABLE", "note": note})

    n = MACROS
    d = maize_pairs()
    w = pd.read_parquet(PROC / "panel_ble.parquet")
    w59 = pd.read_parquet(PROC / "panel_ble_1959.parquet")
    ok = lambda cond: "OK" if cond else "ÉCART"                                         # noqa: E731

    # Plan d'échantillonnage (annexe A : « counts that define the design »).
    add("01_introduction.tex", "so 83 departments are not 83", f"{n['WheatMainDeps']} départements (blé, principal)", ok(n["WheatMainDeps"] == "83"))
    add("07_maize.tex", "435 department-years, 17 departments", f"{len(d)} paires, {d.dep_code.nunique()} départements",
        ok(len(d) == 435 and d.dep_code.nunique() == 17))
    add("07_maize.tex", "(435 department-years, 26 years)", f"{len(d)} paires, {d.annee.nunique()} années", ok(d.annee.nunique() == 26))
    add("08_wheat.tex", "the 85 departments of the population", f"{w.dep_code.nunique()} départements", ok(w.dep_code.nunique() == 85))
    add("08_wheat.tex", "83 departments, 16 harvests", f"{n['WheatMainDeps']} dép., {w.annee.nunique()} récoltes", ok(w.annee.nunique() == 16))
    add("09_forecasting.tex", "the 83 departments of the main sample", n["WheatMainDeps"], ok(n["WheatMainDeps"] == "83"))
    add("10_discussion.tex", "across the 38 departments", n["MaizeDeps"], ok(n["MaizeDeps"] == "38"))
    add("10_discussion.tex", "the 21 departments with a lower status", f"{int(n['MaizeDeps']) - int(n['MaizeMainDeps'])}",
        ok(int(n["MaizeDeps"]) - int(n["MaizeMainDeps"]) == 21))
    add("11_conclusion.tex", "In 17 French departments over 26 summers", f"{d.dep_code.nunique()} dép., {d.annee.nunique()} étés",
        ok(d.dep_code.nunique() == 17 and d.annee.nunique() == 26))
    add("06_inference.tex", "16 for wheat over 2010--2025, 26 for maize", f"{w.annee.nunique()} et {d.annee.nunique()} années",
        ok(w.annee.nunique() == 16 and d.annee.nunique() == 26))
    thirds = [len(c) for c in np.array_split(np.sort(w59.annee.unique()), 3)]
    add("05_strategy.tex", "three sub-periods of 22 to 23 years", f"tiers des années 1959-2025 : {thirds}",
        ok(sorted(thirds) == [22, 22, 23]))
    add("08_wheat.tex", "Multiplying the number of harvests by four", f"{w59.annee.nunique()} / {w.annee.nunique()} = "
        f"{w59.annee.nunique() / w.annee.nunique():.2f}", ok(round(w59.annee.nunique() / w.annee.nunique()) == 4), "ordre de grandeur")
    test_years = pd.read_parquet(TAB / "phase5_predictions.parquet").annee_test
    add("09_forecasting.tex", "between 6 and 15 years", f"années test {test_years.min()}-{test_years.max()}, entraînement depuis 2010",
        ok(test_years.min() - 2010 == 6 and test_years.max() - 2010 == 15))
    add("07_maize.tex", "$t$ with 25 d.f.", f"{d.annee.nunique()} années - 1", ok(d.annee.nunique() - 1 == 25))
    add("A_reproduction.tex", "that of 26 explicit re-estimations", f"{d.annee.nunique()} années", ok(d.annee.nunique() == 26))
    add("G_maize_checks.tex", "a test on 16 restrictions", f"{d.dep_code.nunique()} pentes - 1", ok(d.dep_code.nunique() - 1 == 16))

    # Paramètres de simulation, vérifiés dans le code R et les CSV.
    r_code = "\n".join(p.read_text() for p in (ROOT / "R").rglob("*.R"))
    taille = pd.read_csv(TAB / "phase4bis_q1_taille.csv")
    add("06_inference.tex", "repeat 300 times (200 for the two exploratory", f"R = {int(taille.R.iloc[0])} ; phase 6 R = "
        f"{int(pd.read_csv(TAB / 'phase6_mais_taille.csv').R.iloc[0])}", ok(int(taille.R.iloc[0]) == 300))
    add("06_inference.tex", "uses 399 draws within each repetition", f"B = {int(taille.B.iloc[0])}", ok(int(taille.B.iloc[0]) == 399))
    add("06_inference.tex", "distribution of 9,999 simulated", "B = 9999 (R/common.R)", ok("B = 9999" in r_code))
    add("06_inference.tex", "about 1.3 points with 300 repetitions and 1.5 points with 200",
        f"{100 * np.sqrt(.05 * .95 / 300):.2f} et {100 * np.sqrt(.05 * .95 / 200):.2f} points",
        ok(round(100 * np.sqrt(.05 * .95 / 300), 1) == 1.3 and round(100 * np.sqrt(.05 * .95 / 200), 1) == 1.5))
    add("06_inference.tex", "(about 0.04 with 26 years)", f"1/{d.annee.nunique() - 1} = {1 / (d.annee.nunique() - 1):.3f}",
        ok(round(1 / (d.annee.nunique() - 1), 2) == 0.04))
    add("06_inference.tex", "simulates 40 regions over 25 years", "N_REG <- 40, N_YEAR <- 25 (R/wcr/exemple.R)",
        ok("N_REG <- 40" in r_code and "N_YEAR <- 25" in r_code))
    add("07_maize.tex", "5,000 derangements of years", "seq_len(5000) (R/22)", ok("seq_len(5000)" in r_code))
    dml = pd.read_csv(TAB / "phase7_dml_repetitions.csv")
    add("07_maize.tex", "over 50 random splits", f"{len(dml)} découpages", ok(len(dml) == 50))
    add("07_maize.tex", "a true effect of the estimated size (0.016)", f"β = {float(n['QoneBeta']):.4f}",
        ok(round(float(n["QoneBeta"]), 3) == 0.016))
    add("07_maize.tex", "(500 to 3\\,000~m$^3$/ha)", "500 <= dose <= 3000 (R/27)", ok("dose_m3_ha >= 500 & v$dose_m3_ha <= 3000" in r_code))
    add("01_introduction.tex", "200~km cut-off", "CONLEY_KM <- 200", ok("CONLEY_KM <- 200" in r_code))
    sim = pd.read_csv(TAB / "phase4_simulation_inference.csv")
    add("08_wheat.tex", "a true effect of $-1.5$", f"beta_vrai = {sorted(sim.beta_vrai.unique())}", ok(-0.015 in sim.beta_vrai.round(3).values))
    py_code = "\n".join(p.read_text() for p in (ROOT / "scripts").glob("*.py") if not p.name.startswith("46_"))
    add("03_data.tex", "below 0.002 euro per quintal per index point", "le script 24 s'arrête si l'écart ≥ 0,002",
        ok("if spread >= 0.002" in py_code))
    add("F_degree_days.tex", "over 100,000 points of the sine cycle", "np.linspace(0, 2π, 100_000) (script 26)", ok("100_000" in py_code))
    add("03_data.tex", "simplified to 800~m", "simplify(800) (script 39)", ok("simplify(800)" in py_code))

    # Rapports et comptes déduits de macros.
    add("07_maize.tex", "known only to within a factor of eight", f"{n['CiNinetyHigh']} / {n['CiNinetyLow']} = "
        f"{float(n['CiNinetyHigh']) / float(n['CiNinetyLow']):.1f}",
        ok(round(float(n["CiNinetyHigh"]) / float(n["CiNinetyLow"])) == 8))
    add("07_maize.tex", "The eight that are not", f"{int(n['MultiN']) - int(n['MultiSig'])}", ok(int(n["MultiN"]) - int(n["MultiSig"]) == 8))
    t1 = pd.read_csv(TAB / "phase7_fourrage.csv")
    add("07_maize.tex", "only five of them with quality status~1", f"{int(t1.n_departements.iloc[1])} départements", ok(int(t1.n_departements.iloc[1]) == 5))
    ra = pd.read_parquet(PROC / "ra_irrigation_dep.parquet")
    ra = ra[(ra.annee_ra == 2020) & ra.dep_code.isin(d.dep_code) & (ra.part_mais_grain_irrigue > 0.5)]
    add("07_maize.tex", "(01, 03, 18, 63, 67, 68)", " ".join(sorted(ra.dep_code)),
        ok(sorted(ra.dep_code) == ["01", "03", "18", "63", "67", "68"]))
    val = pd.read_csv(TAB / "phase4bis_q1_valorisation.csv").set_index("annee")
    add("07_maize.tex", "price of maize was about twice as high", f"{val.prix_eur_q[2022]:.2f} / {val.prix_eur_q[2019]:.2f} = "
        f"{val.prix_eur_q[2022] / val.prix_eur_q[2019]:.2f}", ok(1.75 <= val.prix_eur_q[2022] / val.prix_eur_q[2019] <= 2.25))
    add("10_discussion.tex", "between a quarter and two fifths", f"{n['NeffMaizeShareTwoThousandThree']} % et {n['LevThree']} %",
        ok(sorted([float(n["NeffMaizeShareTwoThousandThree"]), float(n["LevThree"])]) [0] >= 22.5
           and sorted([float(n["NeffMaizeShareTwoThousandThree"]), float(n["LevThree"])])[1] <= 42.5))
    add("10_discussion.tex", "raises the estimate by about a third", f"rapport IV / MCO = {n['IvEobsRatio']}", ok(1.25 <= float(n["IvEobsRatio"]) <= 1.42))
    heat26 = float(n["TwentySixHeat"])
    add("07_maize.tex", "second only to 2003", f"2026 : {heat26} DD ; 2003 : {n['HeatTwoThousandThree']} ; suivant : {n['HeatSecondYear']}",
        ok(float(n["HeatSecondYear"]) < heat26 < float(n["HeatTwoThousandThree"])))
    add("08_wheat.tex", "only one summer, 1976", f"1976 : {n['HeatSeventySix']} DD ; autres < 2000 : ≤ {n['HeatPreTwoThousandOtherMax']}",
        ok(float(n["HeatSeventySix"]) > 2 * float(n["HeatPreTwoThousandOtherMax"])), "1976 au moins deux fois l'été suivant d'avant 2000")
    from atlas.forecast import DATES, VARS, features
    n_feat = {date: len(features(date)) for date in DATES}
    add("09_forecasting.tex", "Nine variables per window give 36 variables",
        f"{len(VARS)} variables x fenêtres ; par date : {n_feat}", ok(len(VARS) == 9 and 36 in n_feat.values()))
    vb = pd.read_csv(TAB / "phase7_prevision_vs_B0.csv").set_index(["date", "modele"])
    add("09_forecasting.tex", "better than B0 in 9 of the 10 years", f"{int(vb.loc[('juillet', 'RF_B0'), 'annees_meilleur_que_B0'])} années",
        ok(int(vb.loc[("juillet", "RF_B0"), "annees_meilleur_que_B0"]) == 9))
    f = pd.read_csv(TAB / "phase5_synthese_vs_B0.csv")
    b1 = f[(f.variante == "principale_2010") & (f.modele == "B1")]
    add("09_forecasting.tex", "its 0 years out of 10 better than B0", f"{b1.annees_meilleur_que_B0.tolist()}", ok((b1.annees_meilleur_que_B0 == 0).all()))
    width = ((f.ic95_haut - f.ic95_bas) / (f.ic95_t_haut - f.ic95_t_bas))
    add("09_forecasting.tex", "about 18\\,\\% narrower than a Student interval", f"rétrécissement moyen {1 - width.mean():.1%} "
        f"(de {1 - width.max():.1%} à {1 - width.min():.1%})", "OK" if abs(1 - width.mean() - 0.18) < 0.03 else "ÉCART",
        "moyenne sur les 20 comparaisons à B0")
    ndvi = pd.read_parquet(PROC / "ndvi_features.parquet")
    ndvi = ndvi[ndvi.dep_code.isin(w.loc[w.echantillon_principal, "dep_code"]) & ndvi.annee.between(2010, 2025)]
    add("C_deviations.tex", "at most 1.13\\,\\% per variable", f"{100 * ndvi.drop(columns=['dep_code', 'annee']).isna().mean().max():.2f} %",
        ok(f"{100 * ndvi.drop(columns=['dep_code', 'annee']).isna().mean().max():.2f}" == "1.13"), "83 départements, 2010-2025")
    add("C_deviations.tex", "18 missing wheat yields in the main sample, not 27",
        f"{int(w59[w59.echantillon_principal].rendement_q_ha.isna().sum())} (principal) ; {int(w59.rendement_q_ha.isna().sum())} (population)",
        ok(int(w59[w59.echantillon_principal].rendement_q_ha.isna().sum()) == 18 and int(w59.rendement_q_ha.isna().sum()) == 27))
    # Valeurs d'une version antérieure de l'analyse (graines ou code d'origine), citées comme telles dans le texte :
    # le dépôt ne garde pas cette version, elles ne sont donc pas recalculables.
    for file, snippet in [("06_inference.tex", "gave 8.7\\,\\% false rejections"),
                          ("C_deviations.tex", "(size 8.7\\,\\% $\\to$ 6.6\\,\\%)"),
                          ("06_inference.tex", "(it was 6.0\\,\\% with other random seeds)"),
                          ("07_maize.tex", "it was 12\\,\\% below, with a combined $p$ of 0.044"),
                          ("09_forecasting.tex", "the best sign test gave $p = 0.109$")]:
        add(file, snippet, "version antérieure de l'analyse", "SOURCE EXTERNE", "valeur historique, citée comme telle")
    for file, snippet in [("07_maize.tex", "the 15\\,\\% set for calling"), ("C_deviations.tex", "double machine learning within 15\\,\\%")]:
        add(file, snippet, "règle de lecture du DML : « à moins de 15 % de β̂(A1) »", "SOURCE EXTERNE", "seuil de la règle de lecture")

    # Sources externes : non vérifiables par le code du projet.
    for file, snippet in [("07_maize.tex", "1\\,410~m$^3$/ha"), ("07_maize.tex", "0.20 to 0.28 euros per cubic metre"),
                          ("07_maize.tex", "for 1.4~kg of maize per cubic metre"), ("03_data.tex", "10\\,000~m$^3$ a year"),
                          ("10_discussion.tex", "falls above 35\\,$^{\\circ}$C, less so for maize"), ("10_discussion.tex", "about a third of the benefit"),
                          ("07_maize.tex", "taken around 10:30"), ("09_forecasting.tex", "until 18:00 UTC"),
                          ("01_introduction.tex", "about a quarter of the heat sensitivity")]:
        add(file, snippet, "source citée", "SOURCE EXTERNE", "à vérifier dans la référence, pas dans le code")
    return out


# --- C. Inventaire automatique des nombres écrits en dur ----------------------------------------------------------

STRIP = [r"%.*$", r"\\(?:c|C)ref\{[^}]*\}", r"\\label(?:\[[^\]]*\])?\{[^}]*\}", r"\\eqref\{[^}]*\}",
         r"\\(?:paren|text)?cite[a-z]*(?:\[[^\]]*\])?\{[^}]*\}", r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}",
         r"\\input\{[^}]*\}", r"\\url\{[^}]*\}", r"\\href\{[^}]*\}", r"\\texttt\{[^}]*\}", r"p\{\d+(?:\.\d+)?cm\}",
         r"\\(?:setlength|tabcolsep|arraystretch)[^ ]*", r"\\[A-Za-z]+", r"\[\d+pt\]", r"\d+(?:\.\d+)?\\textwidth"]
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
# Seuils, niveaux de test, résolutions, ordinaux : choix de conception, pas des résultats.
DESIGN = {"32", "30", "34", "33", "35", "0", "1", "2", "3", "4", "5", "10", "90", "95", "0.05", "0.5", "1,000", "2,000", "8",
          "250", "500", "0.1", "200", "800", "70", "6", "16", "12", "9", "7", "20", "40", "100", "2.0", "2.7", "4.0", "24", "365"}
# Comptes du plan d'échantillonnage et des simulations, contrôlés en partie B.
COUNTS = {"17", "38", "83", "85", "26", "67", "300", "9,999", "435", "50", "25", "123"}
IDENT = re.compile(r"Licence|Version|version|CC BY|RCP|collection|Python|SHA-|doi|Lambert|Infos rapides|\(\d\d\)")
NOT_CHECKABLE = re.compile(r"minutes|10\^\{-15\}|March to 6 April")


def scan_literals() -> pd.DataFrame:
    rows = []
    for name, text in TEX.items():
        for i, line in enumerate(text.splitlines(), 1):
            clean = re.sub(r"(\d)\\,(\d)", r"\1\2", line)          # « 3\,000 » -> « 3000 »
            for pat in STRIP:
                clean = re.sub(pat, " ", clean)
            for mt in NUMBER.finditer(clean):
                tok = mt.group().rstrip(",")
                v = float(tok.replace(",", "")) if tok.replace(",", "").replace(".", "").isdigit() else None
                ctx = clean[max(0, mt.start() - 45): mt.end() + 30].replace("\n", " ")
                if v is not None and 1900 <= v <= 2100 and "." not in tok:
                    kind = "année ou période"
                elif name == "02_literature.tex":
                    kind = "source externe (littérature)"
                elif IDENT.search(clean[max(0, mt.start() - 25): mt.end() + 5]):
                    kind = "identifiant, version, licence ou code"
                elif tok in DESIGN:
                    kind = "constante de conception, unité ou ordinal"
                elif tok in COUNTS:
                    kind = "compte du plan (contrôlé en partie B)"
                elif NOT_CHECKABLE.search(line):
                    kind = "non vérifiable par le code (durée, historique, calendrier MODIS)"
                else:
                    kind = "à examiner"
                rows.append({"fichier": name, "ligne": i, "nombre": tok, "classe": kind, "contexte": ctx.strip()})
    return pd.DataFrame(rows)


def saa_split() -> None:
    """Partage irrigué / non irrigué : rendements dérivés de la production et fourrage."""
    d = maize_pairs()
    # Production, surface et rendement non irrigués relus dans les deux éditions de la SAA.
    z = zipfile.ZipFile(ROOT / "data" / "raw" / "agreste_saa_ancienne" / "FDS_DEVELOPPE_2.zip")
    old = []
    for y in range(2000, 2010):
        t = pd.read_csv(io.BytesIO(z.read(f"FDS_DEVELOPPE_{y}.csv")), sep=";", dtype=str)
        t = t[(t.N306_LIB == "Maïs grain non irrigué") & (t.DEP != "...")]
        w = t.pivot_table(index="DEP", columns="N027_LIB", values="VALEUR", aggfunc="first").apply(pd.to_numeric)
        old.append(pd.DataFrame({"dep_code": w.index, "annee": y, "p": w["Production (volume)"].values,
                                 "r": w["Rendement"].values, "s": w["Superficie développée"].values}))
    saa = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    new = saa[(saa.culture_code == "15") & (saa.annee >= 2010)]
    new = pd.DataFrame({"dep_code": new.dep_code, "annee": new.annee, "p": new.production_q, "r": new.rendement_q_ha,
                        "s": new.surface_ha})
    ps = pd.concat(old + [new]).merge(d[["dep_code", "annee"]], on=["dep_code", "annee"], validate="one_to_one")
    ps["derive"] = (ps.p - ps.r * ps.s).abs() >= 0.5
    check("Non irrigué dérivé de la production, 2000-2009 (%)", ps.derive[ps.annee <= 2009].mean(), 0, "SplitDerivOld", scale=100)
    check("Non irrigué dérivé de la production, 2010-2025 (%)", ps.derive[ps.annee >= 2010].mean(), 0, "SplitDerivNew", scale=100)
    keep = d.merge(ps[["dep_code", "annee", "derive"]], on=["dep_code", "annee"])
    k = keep[~keep.derive]
    k = k[k.groupby("annee").annee.transform("size") > 1]   # une année à une seule paire est absorbée par son effet fixe
    check("Paires sans non irrigué dérivé, dans l'estimation", len(k), 0, "SplitNoDerivN",
          note=f"{(~keep.derive).sum()} paires, dont les années à une seule paire retirées par fixest")
    # Fourrage : rapport irrigué / non irrigué arrondi au centième identique à celui du grain (population de 38).
    m = pd.read_parquet(PROC / "panel_mais_long.parquet")
    g = m.pivot_table(index=["dep_code", "annee"], columns="modalite", values="rendement_q_ha").dropna()
    g = (g.irrigue / g.non_irrigue).round(2).rename("r_grain").reset_index()
    fo = pd.read_parquet(PROC / "panel_fourrage.parquet")
    fg = fo.merge(g, on=["dep_code", "annee"])
    check("Couples fourrage / grain communs", len(fg), 0, "FodderPairsN")
    check("Couples au rapport identique au grain", ((fg.irrigue / fg.non_irrigue).round(2) == fg.r_grain).sum(), 0, "FodderSameN")


def main() -> None:
    intro_and_data()
    exposure_and_altitude()
    inference_and_maize()
    saa_split()
    a = pd.DataFrame(ROWS)
    b = pd.DataFrame(hardcoded())
    c = scan_literals()
    # Un nombre de l'inventaire est « contrôlé » s'il figure dans un extrait de la partie B du même fichier.
    covered = {(r.fichier, tok.rstrip(",")) for r in b.itertuples() for tok in NUMBER.findall(r.extrait.replace("\\,", ""))}
    in_b = pd.Series([(f, t) in covered for f, t in zip(c.fichier, c.nombre)], index=c.index)
    c.loc[(c.classe == "à examiner") & in_b, "classe"] = "contrôlé (partie B)"
    a.to_csv(TAB / "verification_chiffres_memoire.csv", index=False)
    pd.concat([b.assign(partie="B"), c.assign(partie="C")]).to_csv(TAB / "verification_chiffres_en_dur.csv", index=False)

    pd.set_option("display.width", 250, "display.max_colwidth", 90, "display.max_rows", 500)
    print("=== A. Chiffres recalculés depuis les données ===")
    print(a[["chiffre", "valeur_exacte", "arrondi_recalcule", "texte", "statut", "note"]].to_string(index=False))
    print("\n=== B. Chiffres écrits en dur, contrôlés un par un ===")
    print(b[["fichier", "extrait", "valeur_code", "statut"]].to_string(index=False))
    print("\n=== C. Inventaire des nombres en dur : répartition ===")
    print(c.classe.value_counts().to_string())
    todo = c[c.classe == "à examiner"]
    print(f"\n{len(todo)} nombres « à examiner » :")
    print(todo[["fichier", "ligne", "nombre", "contexte"]].to_string(index=False))
    # Macros définies mais appelées dans aucun chapitre : signalées pour information (code mort ou contrôle interne).
    unused = [k for k in MACROS if re.search(rf"\\{k}(?![A-Za-z])", ALL_TEX) is None]
    print(f"\n{len(unused)} macros de numbers.tex non appelées dans le mémoire : {' '.join(unused)}")
    bad = (a.statut != "OK").sum() + (~b.statut.isin(["OK", "SOURCE EXTERNE"])).sum()
    print(f"\nRésumé : {len(a)} chiffres recalculés, {len(b)} chiffres en dur contrôlés, {bad} à regarder.")


if __name__ == "__main__":
    main()
