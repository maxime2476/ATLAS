"""Étape 39 : quatre figures ajoutées ensuite au mémoire (descriptives, aucune nouvelle estimation).

Usage : uv run python scripts/39_figures_complements.py
Sorties (memoire/figures/, PDF, en anglais, sans titre : la légende LaTeX en tient lieu) :
  fig7_residus_ecart_chaleur.pdf   le résultat principal vu dans les données : écart et chaleur après les effets fixes
  fig8_chaleur_projections.pdf     chaleur de juillet-août observée 1976-2025 et projetée (DRIAS, niveaux TRACC)
  fig9_carte_echantillon.pdf       les 38 départements de la population, l'échantillon principal et les reliefs
  fig10_multivers_choix.pdf        courbe des spécifications avec le panneau des choix
Même palette que scripts/20_figures_rapport.py.
"""

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from atlas.download import ROOT  # noqa: E402

TAB = ROOT / "reports" / "tables"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "memoire" / "figures"
PDF_META = {"CreationDate": None}   # PDF sans date de création : la figure ne dépend que des données
INK, INK2, SURFACE, BLUE, ORANGE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#2a78d6", "#eb6834", "#e6e5e1"
LIGHT_BLUE, GREY = "#a9c9ef", "#e6e5e1"
UPLANDS = ["01", "26", "38", "39", "63", "69"]   # les six départements à relief (chapitre 4, tableau 5)


def style(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_facecolor(SURFACE)


def main_pairs() -> pd.DataFrame:
    long = pd.read_parquet(PROC / "panel_mais_long.parquet").query("echantillon_principal")
    irr = long[long.modalite == "irrigue"]
    non = long[long.modalite == "non_irrigue"][["dep_code", "annee", "log_rendement"]]
    d = irr.merge(non, on=["dep_code", "annee"], suffixes=("", "_non"), validate="one_to_one")
    d["ecart_log"] = d.log_rendement - d.log_rendement_non
    if not (len(d) == 435):
        raise SystemExit("435 paires attendues dans l'échantillon principal")
    return d


def residualise(d: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """Résidus pondérés de `cols` sur les effets fixes département et année et sur le SWI (Frisch-Waugh-Lovell)."""
    X = pd.get_dummies(d[["dep_code", "annee"]].astype(str), drop_first=True).astype(float)
    X = np.column_stack([np.ones(len(d)), X.to_numpy(), d.swi_ja.to_numpy()])
    w = np.sqrt(d.surface_ref_ha.to_numpy())
    Y = d[cols].to_numpy()
    coef, *_ = np.linalg.lstsq(X * w[:, None], Y * w[:, None], rcond=None)
    return Y - X @ coef


def fig_residus():
    d = main_pairs()
    r = residualise(d, ["ecart_log", "dd_32_ja"])
    y, x, w = r[:, 0], r[:, 1], d.surface_ref_ha.to_numpy()
    beta = np.sum(w * x * y) / np.sum(w * x * x)
    h1 = pd.read_csv(TAB / "phase4bis_q1_hypotheses.csv").query("hypothese == 'H1'").estimation.iloc[0]
    if not (abs(beta - h1) < 1e-10):
        raise SystemExit("la pente des résidus doit être le beta de H1")
    fig, ax = plt.subplots(figsize=(7.5, 3.8), facecolor=SURFACE)
    is03 = (d.annee == 2003).to_numpy()
    size = 8 + 40 * w / w.max()
    ax.scatter(x[~is03], 100 * y[~is03], s=size[~is03], color=BLUE, alpha=0.55, edgecolor=SURFACE, linewidth=0.5,
               label="other summers, 2000-2025")
    ax.scatter(x[is03], 100 * y[is03], s=size[is03], color=ORANGE, alpha=0.9, edgecolor=SURFACE, linewidth=0.5,
               label="2003")
    grid = np.linspace(x.min(), x.max(), 50)
    ax.plot(grid, 100 * beta * grid, color=INK, linewidth=1.5, label=f"slope of A1 ({100 * beta:.2f} log points per degree-day)")
    ax.axhline(0, color=INK2, linewidth=0.6)
    ax.axvline(0, color=INK2, linewidth=0.6)
    ax.set_xlabel("Degree-days > 32 °C in July-August, net of department and year effects and soil wetness",
                  color=INK2, fontsize=9)
    ax.set_ylabel("Irrigated − rainfed log yield gap\n(× 100, same adjustment)", color=INK2, fontsize=9)
    style(ax)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig7_residus_ecart_chaleur.pdf", metadata=PDF_META)
    plt.close(fig)
    print(f"fig7 : pente {beta:.4f} (H1 {h1:.4f}) ; part de 2003 dans la variance résiduelle pondérée de la chaleur "
          f"{np.sum((w * x * x)[is03]) / np.sum(w * x * x):.0%}")


def fig_projections():
    ref = main_pairs().groupby("dep_code").surface_ref_ha.first()
    m = pd.read_parquet(PROC / "weather_dep_month_maize.parquet")
    m = m[m.month.isin([7, 8]) & m.dep_code.isin(ref.index) & m.year.between(1976, 2025)]
    ja = m.groupby(["year", "dep_code"]).dd_32.sum().reset_index()
    ja["w"] = ref.reindex(ja.dep_code).to_numpy()
    obs = ja.groupby("year").apply(lambda g: np.average(g.dd_32, weights=g.w), include_groups=False)
    if not (abs(obs.loc[2003] - 14.74) < 0.01):
        raise SystemExit("2003 doit valoir 14,7 comme dans le texte")
    syn = pd.read_csv(TAB / "phase7_drias_synthese.csv").set_index("horizon")
    fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=SURFACE)
    ax.bar(obs.index, obs.values, color=BLUE, width=0.8, label="observed (SIM2), 1976-2025")
    ax.bar([2003], [obs.loc[2003]], color=ORANGE, width=0.8)
    ax.annotate("2003", (2003, obs.loc[2003]), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8,
                color=INK)
    xs = {"France +2.0": 2031, "France +2.7": 2035, "France +4.0": 2039}
    for h, xpos in xs.items():
        r = syn.loc[h]
        ax.errorbar(xpos, r.dd_32_ja_mediane, yerr=[[r.dd_32_ja_mediane - r.dd_32_ja_min], [r.dd_32_ja_max - r.dd_32_ja_mediane]],
                    fmt="o", color=INK, ecolor=INK2, elinewidth=1.2, capsize=3, markersize=6)
        ax.annotate(h.replace("France ", "") + " °C", (xpos, r.dd_32_ja_max), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=8, color=INK)
    ax.axvline(2027.5, color=INK2, linewidth=0.6, linestyle=":")
    top = ax.get_xaxis_transform()
    ax.text(2000.5, 1.0, "observed", ha="center", va="bottom", fontsize=8, color=INK2, transform=top)
    ax.text(2035, 1.0, "projected, warming levels for France", ha="center", va="bottom", fontsize=8, color=INK2,
            transform=top)
    ax.set_xticks([1980, 1990, 2000, 2010, 2020] + list(xs.values()))
    ax.set_xticklabels(["1980", "1990", "2000", "2010", "2020", "+2.0", "+2.7", "+4.0"])
    ax.set_ylabel("Degree-days > 32 °C, July-August", color=INK2, fontsize=9)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / "fig8_chaleur_projections.pdf", metadata=PDF_META)
    plt.close(fig)
    print(f"fig8 : 1976-2025 observé, 2003 = {obs.loc[2003]:.1f} ; médianes DRIAS "
          f"{[round(syn.loc[h].dd_32_ja_mediane, 1) for h in xs]}")


def fig_carte():
    dep = gpd.read_parquet(ROOT / "data" / "raw" / "ign_admin_express" /
                           "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    dep = dep[dep.code_insee.str.len() == 2].set_geometry("geometrie").to_crs(2154)
    dep["geometrie"] = dep.geometry.simplify(800)   # contours allégés (800 m) : la carte est un repère, pas une mesure
    long = pd.read_parquet(PROC / "panel_mais_long.parquet")
    pop = set(long.dep_code)
    main = set(long[long.echantillon_principal].dep_code)
    if not (len(pop) == 38 and len(main) == 17):
        raise SystemExit("38 départements dans la population et 17 dans l'échantillon principal attendus")
    colour = np.where(dep.code_insee.isin(main), BLUE, np.where(dep.code_insee.isin(pop), LIGHT_BLUE, GREY))
    fig, ax = plt.subplots(figsize=(5.6, 5.6), facecolor=SURFACE)
    dep.plot(ax=ax, color=colour, edgecolor=SURFACE, linewidth=0.5)
    dep[dep.code_insee.isin(UPLANDS)].plot(ax=ax, facecolor="none", edgecolor=ORANGE, linewidth=1.6)
    for _, row in dep[dep.code_insee.isin(main)].iterrows():
        p = row.geometrie.representative_point()
        ax.annotate(row.code_insee, (p.x, p.y), ha="center", va="center", fontsize=6.5, color="white")
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=LIGHT_BLUE),
               plt.Rectangle((0, 0), 1, 1, facecolor="none", edgecolor=ORANGE, linewidth=1.6)]
    ax.legend(handles, ["main sample (17 departments, quality status 1)", "rest of the population (21)",
                        "departments with uplands (6)"], frameon=False, fontsize=8, loc="lower left")
    # Barre d'échelle de 100 km (Lambert 93, coordonnées en mètres).
    x0, y0 = dep.total_bounds[2] - 260_000, dep.total_bounds[1] + 60_000
    ax.plot([x0, x0 + 100_000], [y0, y0], color=INK, linewidth=2)
    ax.annotate("100 km", (x0 + 50_000, y0), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8,
                color=INK)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(OUT / "fig9_carte_echantillon.pdf", metadata=PDF_META)
    plt.close(fig)
    print("fig9 : carte enregistrée")


def fig_multivers():
    """Courbe des spécifications du multivers, avec sous la courbe les choix de chaque estimation (Simonsohn et al. 2020)."""
    m = pd.read_csv(TAB / "phase7_multivers.csv").sort_values("effet_pct_par_unite").reset_index(drop=True)
    if not (len(m) == 76 and m.principale.sum() == 1):
        raise SystemExit("76 spécifications du multivers, dont une principale, attendues")
    rows = [("Heat: maize mask 2015-17", m.mesure == "masque 2015-2017"), ("Heat: maize mask 2008", m.mesure == "masque 2008"),
            ("Heat: department-wide", m.mesure == "surface"), ("Heat: E-OBS", m.mesure == "E-OBS"),
            ("Threshold 30 °C", m.seuil == 30), ("July only", m.fenetre == "juillet"), ("Unweighted", ~m.poids),
            ("38 departments", m.echantillon == 38), ("Without 2003", m.sans_2003)]
    fig, (top, bot) = plt.subplots(2, 1, figsize=(7.5, 5.2), sharex=True, gridspec_kw={"height_ratios": [1.3, 1]},
                                   facecolor=SURFACE)
    x = np.arange(len(m))
    sig = (m.p_wcb_annee_unilateral_droite < 0.05).to_numpy()
    col = np.where(m.principale, ORANGE, BLUE)
    top.scatter(x[sig], m.effet_pct_par_unite[sig], color=col[sig], s=22, edgecolor=SURFACE, linewidth=0.5,
                label="one-sided bootstrap p < 0.05")
    top.scatter(x[~sig], m.effet_pct_par_unite[~sig], facecolor="none", edgecolor=col[~sig], s=22, linewidth=1,
                label="p ≥ 0.05")
    main = m.index[m.principale][0]
    top.annotate("main specification (A1)", (main, m.effet_pct_par_unite[main]), xytext=(-10, 18), textcoords="offset points",
                 ha="right", fontsize=8, color=ORANGE, arrowprops=dict(arrowstyle="-", color=ORANGE, lw=0.8))
    top.axhline(0, color=INK2, linewidth=0.6)
    top.set_ylabel("% per degree-day", color=INK2, fontsize=9)
    style(top)
    top.legend(frameon=False, fontsize=8, loc="upper left")
    for k, (label, on) in enumerate(rows):
        yk = len(rows) - 1 - k
        bot.scatter(x[on.to_numpy()], np.full(on.sum(), yk), marker="s", s=9, color=INK)
        bot.scatter(x[~on.to_numpy()], np.full((~on).sum(), yk), marker="s", s=9, color=GREY)
    bot.set_yticks(range(len(rows)))
    bot.set_yticklabels([r[0] for r in rows][::-1], fontsize=8, color=INK2)
    bot.set_xticks([])
    bot.set_xlabel("Specifications, sorted by estimate", color=INK2, fontsize=9)
    for sp in bot.spines.values():
        sp.set_visible(False)
    bot.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(OUT / "fig10_multivers_choix.pdf", metadata=PDF_META)
    plt.close(fig)
    print(f"fig10 : {len(m)} spécifications, {sig.sum()} significatives")


if __name__ == "__main__":
    fig_residus()
    fig_projections()
    fig_carte()
    fig_multivers()
