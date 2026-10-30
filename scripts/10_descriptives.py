"""Étape 10 : statistiques descriptives du panel blé (aucune estimation d'effet).

Usage : uv run python scripts/10_descriptives.py
Sorties : reports/tables/*.csv, reports/figures/*.png (non versionnées), résumé imprimé.

Contenu :
  1. rendement national pondéré (surface fixe) 1990-2025, années extrêmes ;
  2. décomposition de la variance du log-rendement (effets fixes département / année) ;
  3. statistiques des variables météo clés et de leurs résidus après effets fixes ;
  4. corrélations des résidus entre variables météo (colinéarité chaleur / eau, hypothèse H2) ;
  5. cartes : rendement moyen, anomalie 2016, exposition > 32 °C en 2019.
"""

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

from atlas.download import ROOT  # noqa: E402

PROC = ROOT / "data" / "processed"
TAB = ROOT / "reports" / "tables"
FIG = ROOT / "reports" / "figures"

# Palette de référence validée (skill dataviz) : série unique, rampe séquentielle bleue,
# paire divergente bleu <-> rouge autour d'un gris neutre.
INK, INK2, SURFACE, BLUE = "#0b0b0b", "#52514e", "#fcfcfb", "#2a78d6"
SEQ = LinearSegmentedColormap.from_list("seq_blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
DIV = LinearSegmentedColormap.from_list("div", ["#d03b3b", "#ec835a", "#f0efec", "#86b6ef", "#1c5cab"])

KEY = ["dd_32_remplissage", "gdd_0_32_remplissage", "swi_remplissage", "swi_dry_remplissage",
       "prec_remplissage", "prec_printemps", "etp_remplissage", "dd_0_automne", "prec_automne", "tmin_hiver"]


def twoway_resid(df, col):
    x = df[col]
    return x - df.groupby("dep_code")[col].transform("mean") - df.groupby("annee")[col].transform("mean") + x.mean()


def style(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    ax.set_axisbelow(True)


def main() -> None:
    TAB.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(PROC / "panel_ble.parquet")
    long = pd.read_parquet(PROC / "panel_ble_long.parquet")

    # 1. Rendement national pondéré par la surface fixe 2010-2012 --------------------
    nat = long.groupby("annee").apply(lambda d: np.average(d["rendement_q_ha"], weights=d["surface_ref_ha"]),
                                      include_groups=False).rename("rendement_national_q_ha")
    nat.to_csv(TAB / "rendement_national.csv")
    dev = panel["rendement_q_ha"] / panel.groupby("dep_code")["rendement_q_ha"].transform("mean") - 1
    worst = panel.assign(dev=dev).groupby("annee")["dev"].median().sort_values()
    print("== 1. Rendement national pondéré (q/ha) :", nat.round(1).to_dict())
    print("   écart médian au rendement moyen du département, 3 pires années 2010-2025 :",
          worst.head(3).round(3).to_dict(), "| 3 meilleures :", worst.tail(3).round(3).to_dict())

    fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.plot(nat.index, nat.values, color=BLUE, linewidth=2)
    ax.axvspan(1989.5, 2009.5, color="#f0efec", zorder=0)
    ax.text(1999.5, nat.max() + 1, "Schauberger et al. (RAW)", ha="center", color=INK2, fontsize=8)
    ax.text(2017.5, nat.max() + 1, "SAA (Agreste)", ha="center", color=INK2, fontsize=8)
    for yr in [2003, 2016, 2025]:
        lab = f"{yr} (provisoire)" if yr == 2025 else str(yr)
        ax.annotate(lab, (yr, nat[yr]), xytext=(8, -3), textcoords="offset points", ha="left", fontsize=8, color=INK)
        ax.plot(yr, nat[yr], "o", color=BLUE, markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax.set_ylabel("q/ha", color=INK2)
    ax.set_title("Rendement du blé tendre d'hiver, 85 départements (pondéré par la surface 2010-2012)",
                 loc="left", fontsize=10, color=INK)
    style(ax)
    fig.tight_layout()
    fig.savefig(FIG / "rendement_national.png", dpi=150)
    plt.close(fig)

    # 2. Décomposition de la variance du log-rendement ------------------------------
    rows = []
    for name, df in [("2010-2025 (SAA)", panel), ("1990-2025 (panel long)", long)]:
        x = df["log_rendement"]
        tot = ((x - x.mean()) ** 2).sum()
        dep = ((df.groupby("dep_code")["log_rendement"].transform("mean") - x.mean()) ** 2).sum()
        yr = ((df.groupby("annee")["log_rendement"].transform("mean") - x.mean()) ** 2).sum()
        res = twoway_resid(df, "log_rendement")  # résidu centré (panel équilibré)
        rows.append({"panel": name, "part_dep": dep / tot, "part_annee": yr / tot,
                     "part_residuelle": (res ** 2).sum() / tot, "ecart_type_residuel": float(np.sqrt((res ** 2).mean()))})
    var = pd.DataFrame(rows)
    var.to_csv(TAB / "decomposition_variance_log_rendement.csv", index=False)
    print("\n== 2. Variance du log-rendement\n", var.round(3).to_string(index=False))

    # 3. Variables météo clés : niveaux et résidus -----------------------------------
    stats = []
    for c in KEY:
        r = twoway_resid(panel, c)
        stats.append({"variable": c, "moyenne": panel[c].mean(), "ecart_type": panel[c].std(),
                      "min": panel[c].min(), "max": panel[c].max(), "ecart_type_residuel": r.std(),
                      "part_residuelle_variance": (r ** 2).sum() / ((panel[c] - panel[c].mean()) ** 2).sum()})
    stats = pd.DataFrame(stats)
    stats.to_csv(TAB / "meteo_cles_2010_2025.csv", index=False)
    print("\n== 3. Variables météo clés (masque blé, 2010-2025)\n", stats.round(3).to_string(index=False))

    # 4. Corrélations des résidus (après effets fixes département et année) ---------
    resid = pd.DataFrame({c: twoway_resid(panel, c) for c in KEY})
    corr = resid.corr()
    corr.to_csv(TAB / "correlations_residus_meteo.csv")
    print("\n== 4. Corrélations des résidus (sélection)")
    for a, b in [("dd_32_remplissage", "swi_remplissage"), ("dd_32_remplissage", "swi_dry_remplissage"),
                 ("dd_32_remplissage", "prec_remplissage"), ("dd_32_remplissage", "etp_remplissage"),
                 ("dd_32_remplissage", "gdd_0_32_remplissage"), ("swi_remplissage", "prec_printemps"),
                 ("swi_remplissage", "prec_remplissage")]:
        print(f"   {a} × {b} : {corr.loc[a, b]:+.3f}")
    # Part de la variation résiduelle de la chaleur extrême NON expliquée par les variables d'eau.
    X = resid[["swi_remplissage", "prec_remplissage", "etp_remplissage"]].to_numpy()
    yv = resid["dd_32_remplissage"].to_numpy()
    beta, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(X)), X]), yv, rcond=None)
    r2 = 1 - ((yv - np.column_stack([np.ones(len(X)), X]) @ beta) ** 2).sum() / ((yv - yv.mean()) ** 2).sum()
    print(f"   R² de dd_32_remplissage (résidu) sur SWI, pluie, ETP (résidus) : {r2:.3f} "
          f"-> part propre à la chaleur : {1 - r2:.3f}")

    fig, ax = plt.subplots(figsize=(5.2, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.scatter(resid["swi_remplissage"], resid["dd_32_remplissage"], s=14, color=BLUE, alpha=0.55,
               edgecolors=SURFACE, linewidths=0.4)
    ax.set_xlabel("SWI mai-juin, résidu après effets fixes", color=INK2, fontsize=9)
    ax.set_ylabel("Degrés-jours > 32 °C mai-juin, résidu", color=INK2, fontsize=9)
    ax.set_title(f"Chaleur extrême et humidité du sol (r = {corr.loc['dd_32_remplissage', 'swi_remplissage']:+.2f})",
                 loc="left", fontsize=10, color=INK)
    style(ax)
    fig.tight_layout()
    fig.savefig(FIG / "residus_chaleur_swi.png", dpi=150)
    plt.close(fig)

    # 5. Cartes -------------------------------------------------------------------
    dep = gpd.read_parquet(ROOT / "data" / "raw" / "ign_admin_express" /
                           "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    dep = dep[dep["code_insee"].str.len() == 2].rename(columns={"code_insee": "dep_code"}).to_crs(2154)
    mean_y = panel.groupby("dep_code")["rendement_q_ha"].mean().rename("rendement_moyen")
    an16 = (panel[panel.annee == 2016].set_index("dep_code")["rendement_q_ha"] / mean_y - 1).rename("anomalie_2016") * 100
    edd19 = panel[panel.annee == 2019].set_index("dep_code")["dd_32_remplissage"].rename("dd32_2019")
    m = dep.merge(pd.concat([mean_y, an16, edd19], axis=1).reset_index(), on="dep_code", how="left")
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), facecolor=SURFACE)
    specs = [("rendement_moyen", "Rendement moyen 2010-2025 (q/ha)", SEQ, None),
             # Bornes symétriques : un même écart absolu a la même intensité des deux côtés.
             ("anomalie_2016", "Écart 2016 au rendement moyen (%)", DIV,
              TwoSlopeNorm(vcenter=0, vmin=-m.anomalie_2016.abs().max(), vmax=m.anomalie_2016.abs().max())),
             ("dd32_2019", "Degrés-jours > 32 °C, mai-juin 2019", SEQ, None)]
    for ax, (col, title, cmap, norm) in zip(axes, specs):
        ax.set_facecolor(SURFACE)
        dep.plot(ax=ax, color="#f0efec", edgecolor=SURFACE, linewidth=0.4)  # hors population
        m.dropna(subset=[col]).plot(ax=ax, column=col, cmap=cmap, norm=norm, edgecolor=SURFACE, linewidth=0.4,
                                    legend=True, legend_kwds={"shrink": 0.6})
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_axis_off()
    fig.text(0.01, 0.02, "Gris clair : départements hors population (< 1000 ha de blé en 2010-2012).",
             fontsize=8, color=INK2)
    fig.tight_layout()
    fig.savefig(FIG / "cartes_rendement_exposition.png", dpi=150)
    plt.close(fig)
    print(f"\nfigures : {sorted(p.name for p in FIG.glob('*.png'))}")


if __name__ == "__main__":
    main()
