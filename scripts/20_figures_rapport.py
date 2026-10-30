"""Étape 20 : figures du README (docs/figures/, PNG, en français) et du mémoire (memoire/figures/, PDF, en anglais).

Usage : uv run python scripts/20_figures_rapport.py
Les figures du mémoire n'ont pas de titre : la légende LaTeX en tient lieu.
Entrées : tableaux de reports/tables/ (aucun recalcul d'estimation).
Palette de référence validée (skill dataviz) : bleu #2a78d6, orange #eb6834, encres #0b0b0b / #52514e.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from atlas.download import ROOT  # noqa: E402

TAB = ROOT / "reports" / "tables"
FIG = ROOT / "docs" / "figures"
MEMOIRE_FIG = ROOT / "memoire" / "figures"   # versions vectorielles (PDF) pour le mémoire LaTeX
PDF_META = {"CreationDate": None}   # PDF sans date de création : la figure ne dépend que des données


def save(fig, name, lang="fr"):
    if lang == "fr":
        fig.savefig(FIG / f"{name}.png", dpi=130)
    else:
        fig.savefig(MEMOIRE_FIG / f"{name}.pdf", metadata=PDF_META)

# Les effectifs des libellés (« 17 dép. », « 83 dép. », années) décrivent le plan de chaque échantillon et sont
# écrits à la main, comme dans les tableaux du mémoire (annexe A) ; les valeurs tracées viennent des CSV.
INK, INK2, SURFACE, BLUE, ORANGE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#2a78d6", "#eb6834", "#e6e5e1"


def style(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_facecolor(SURFACE)


def fig_rendement(lang="fr"):
    nat = pd.read_csv(TAB / "rendement_national.csv", index_col=0)["rendement_national_q_ha"]
    fig, ax = plt.subplots(figsize=(8, 3.4), facecolor=SURFACE)
    ax.axvspan(1989.5, 2009.5, color="#f0efec", zorder=0)
    ax.plot(nat.index, nat.values, color=BLUE, linewidth=2)
    for yr in [2003, 2016, 2024]:
        ax.plot(yr, nat[yr], "o", color=BLUE, markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.annotate(str(yr), (yr, nat[yr]), xytext=(7, -3), textcoords="offset points", fontsize=8, color=INK)
    # x en années, y en fraction de la hauteur : les sources sont écrites juste au-dessus du cadre, sans
    # chevaucher la courbe quelle que soit l'échelle.
    top = ax.get_xaxis_transform()
    ax.text(1999.5, 1.01, "Schauberger et al. (RAW)", ha="center", va="bottom", fontsize=8, color=INK2, transform=top)
    ax.text(2017.5, 1.01, "SAA, Agreste (2025 provisoire)" if lang == "fr" else "SAA, Agreste (2025 provisional)",
            ha="center", va="bottom", fontsize=8, color=INK2, transform=top)
    ax.set_ylabel("q/ha", color=INK2)
    if lang == "fr":
        ax.set_title("Rendement du blé tendre d'hiver, 85 départements (moyenne pondérée)", loc="left", fontsize=10, color=INK, pad=16)
    style(ax)
    fig.tight_layout()
    save(fig, "fig1_rendement_national", lang)
    plt.close(fig)


def fig_taille_inference():
    ble = pd.read_csv(TAB / "phase4_simulation_inference.csv")
    ble = ble[ble.beta_vrai == 0].assign(culture="Blé, mai-juin (83 dép.)")
    mais = pd.read_csv(TAB / "phase6_mais_taille.csv")
    mais = mais[mais.variable_expliquee == "log_non_irrigue"].rename(columns={"taille_5pct": "taux_rejet_5pct"})
    mais = mais.assign(culture="Maïs non irrigué, juillet-août (17 dép.)")
    labels = {"cluster_dep": "Cluster\ndépartement", "conley_200": "Conley\n200 km", "wcr_annee": "Bootstrap WCR\npar année"}
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.4), facecolor=SURFACE, sharey=True)
    for ax, d in zip(axes, [ble, mais]):
        x = np.arange(3)
        vals = [100 * d.set_index("inference").loc[k, "taux_rejet_5pct"] for k in labels]
        bars = ax.bar(x, vals, color=BLUE, width=0.55)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.0f} %", ha="center", fontsize=9, color=INK)
        ax.axhline(5, color=ORANGE, linewidth=1.5, label="Taux nominal : 5 %")
        ax.set_xticks(x, list(labels.values()))
        ax.set_title(d["culture"].iloc[0], loc="left", fontsize=9.5, color=INK)
        style(ax)
    axes[0].set_ylabel("Faux positifs sous H0 (%)", color=INK2)
    axes[1].legend(frameon=False, fontsize=8.5, loc="upper right", labelcolor=INK)
    fig.suptitle("Taille réelle des tests (placebo = exposition réelle, années permutées)", x=0.01, ha="left",
                 fontsize=10, color=INK)
    fig.tight_layout()
    save(fig, "fig2_taille_inference")
    plt.close(fig)


def fig_prevision(lang="fr"):
    m = pd.read_csv(TAB / "phase6_ndvi_metriques_annee.csv")
    m = m[m.date == "juillet"].pivot_table(index="annee_test", columns=["version", "modele"], values="mse_log") ** 0.5
    fig, ax = plt.subplots(figsize=(8, 3.4), facecolor=SURFACE)
    years = m.index.to_numpy()
    fr = lang == "fr"
    ax.plot(years, m[("meteo", "B0")], color=ORANGE, linewidth=2, marker="o", markersize=5,
            label="B0 : moyenne du département" if fr else "B0: department mean")
    ax.plot(years, m[("meteo_ndvi", "GBM")], color=BLUE, linewidth=2, marker="o", markersize=5,
            label="GBM : météo + NDVI au 1er juillet" if fr else "GBM: weather + NDVI on 1 July")
    ax.set_xticks(years)
    ax.set_ylabel("RMSE du log-rendement" if fr else "RMSE of log yield", color=INK2)
    if fr:
        ax.set_title("Prévision hors échantillon, année par année (entraînement sur les années antérieures)",
                     loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right", labelcolor=INK)
    style(ax)
    fig.tight_layout()
    save(fig, "fig3_prevision_par_annee", lang)
    plt.close(fig)


def fig_mais_robustesse(lang="fr"):
    """Phase 4 bis : coefficient de A1 (écart irrigué - non irrigué) selon la spécification. Points seuls :
    les intervalles CR1 n'ont pas une taille vérifiée ; la p WCR unilatérale est écrite à côté."""
    r = pd.read_csv(TAB / "phase4bis_q1_robustesse.csv")
    r9 = TAB / "phase4bis_q1_r9_masque2008.csv"
    if r9.exists():   # robustesse ajoutée ensuite
        r = pd.concat([r, pd.read_csv(r9)], ignore_index=True)
    ex = pd.read_csv(TAB / "phase4bis_q1_exploratoire.csv")
    ex = ex[(ex.analyse.str.startswith("beta")) & (ex.mesure == "pondération surfacique") & (ex.periode != "2000-2025")]
    fr = lang == "fr"
    labels = [s.split(" ", 1)[-1] if s.startswith("Q1-") else "Principal (17 dép., 2000-2025)" for s in r.specification]
    labels = [s[0].upper() + s[1:] for s in labels]
    if not fr:
        en = {"Q1-R1": "38 departments (all quality statuses)", "Q1-R2": "2010-2025 only",
              "Q1-R3": "Weather weighted by department area", "Q1-R4": "Threshold 30 °C", "Q1-R5": "July only",
              "Q1-R6": "Unweighted", "Q1-R7": "Without 2025", "Q1-R8": "Without 2003", "Q1-R9": "2008 maize mask (RPG v1.0)"}
        labels = [en.get(s.split(" ", 1)[0], "Main (17 departments, 2000-2025)") for s in r.specification]
    fig, ax = plt.subplots(figsize=(8.4, 5.2), facecolor=SURFACE)
    y = np.arange(len(r))[::-1]
    sig = r.p_wcb_annee_unilateral_droite < 0.05
    ax.scatter(100 * r.estimation[sig], y[sig], s=48, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
               label="p WCR < 0,05 (unilatéral)" if fr else "one-sided bootstrap p < 0.05")
    ax.scatter(100 * r.estimation[~sig], y[~sig], s=48, facecolor=SURFACE, edgecolor=BLUE, linewidth=1.8, zorder=3,
               label="p WCR ≥ 0,05" if fr else "one-sided bootstrap p ≥ 0.05")
    for yi, b, pv in zip(y, r.estimation, r.p_wcb_annee_unilateral_droite):
        ax.annotate(f"p = {pv:.3f}", (100 * b, yi), xytext=(8, -3), textcoords="offset points", fontsize=8, color=INK2)
    y2 = np.arange(-len(ex), 0)[::-1] - 0.6
    ax.scatter(100 * ex.estimation, y2, s=40, marker="D", color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
               label="Exploratoire, météo pondérée par la surface (sans inférence)" if fr
               else "Exploratory, department-area weather (point estimate only)")
    ax.axvline(0, color=INK2, linewidth=1)
    per_en = {"2000-2009": "2000-2009", "2010-2025": "2010-2025", "sans 2003": "without 2003",
              "2000-2009 sans 2003": "2000-2009 without 2003"}
    ax.set_yticks(list(y) + list(y2), labels + [f"Surface : {s}" if fr else f"Area weights: {per_en[s]}" for s in ex.periode])
    ax.set_xlabel("100 × β : écart log irrigué − non irrigué (≈ % par °C·jour > 32 °C, juillet-août)" if fr else
                  "100 × β: irrigated − rainfed log yield gap (≈ % per degree-day > 32 °C, July-August)", color=INK2)
    if fr:
        ax.set_title("Maïs : écart irrigué − non irrigué selon la spécification (dépend de la mesure de la chaleur)",
                     loc="left", fontsize=9.5, color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.4, -0.13), ncol=2, labelcolor=INK)
    style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    fig.tight_layout()
    save(fig, "fig4_mais_robustesse", lang)
    plt.close(fig)


def fig_taille_4bis():
    q1 = pd.read_csv(TAB / "phase4bis_q1_taille.csv").assign(titre="Maïs, écart irrigué − non irrigué (17 dép., 2000-2025)")
    q2 = pd.read_csv(TAB / "phase4bis_q2_taille.csv").assign(titre="Blé, remplissage (83 dép., 1959-2025)")
    labels = {"cluster_dep": "Cluster\ndépartement", "conley_200": "Conley\n200 km", "wcr_annee": "Bootstrap WCR\npar année"}
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.4), facecolor=SURFACE, sharey=True)
    for ax, d in zip(axes, [q1, q2]):
        x = np.arange(3)
        vals = [100 * d.set_index("inference").loc[k, "taille_5pct"] for k in labels]
        bars = ax.bar(x, vals, color=BLUE, width=0.55)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, max(v, 5) + 0.8, f"{v:.1f} %".replace(".", ","), ha="center",
                    fontsize=9, color=INK)
        ax.axhline(5, color=ORANGE, linewidth=1.5, label="Taux nominal : 5 %")
        ax.set_xticks(x, list(labels.values()))
        ax.set_title(d["titre"].iloc[0], loc="left", fontsize=9, color=INK)
        ax.set_ylim(0, 1.15 * max(31, q1.taille_5pct.max() * 100, q2.taille_5pct.max() * 100))  # marge pour les étiquettes
        style(ax)
    axes[0].set_ylabel("Faux positifs sous H0 (%)", color=INK2)
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left", labelcolor=INK)
    fig.suptitle("Phase 4 bis : taille réelle des tests unilatéraux principaux (placebo, R = 300)", x=0.01, ha="left",
                 fontsize=10, color=INK)
    fig.tight_layout()
    save(fig, "fig5_taille_phase4bis")
    plt.close(fig)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    MEMOIRE_FIG.mkdir(parents=True, exist_ok=True)
    fig_rendement()
    fig_taille_inference()
    fig_prevision()
    fig_mais_robustesse()
    fig_taille_4bis()
    for f in (fig_rendement, fig_prevision, fig_mais_robustesse):   # versions anglaises du mémoire
        f(lang="en")
    print(sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
