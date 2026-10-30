"""Étape 42 : humidité du sol projetée (SWI de juillet-août) et projection de l'écart avec δ̂ · ΔSWI.

Usage : uv run python scripts/42_drias_eau_swi.py   (après scripts/41_drias_eau.py telecharger et l'étape 38)
Entrées : data/raw/drias_eau/indices*.txt (68 fichiers : 17 simulations × référence et trois niveaux TRACC) ;
          grille SAFRAN (latitude, longitude des mailles) ; poids du masque maïs ; reports/tables/phase7_drias_horizons.csv ;
          reports/tables/phase4bis_q1_hypotheses.csv (β̂ et δ̂ de A1) et phase4bis_q1_verif_intervalles.csv (intervalle de β).
Sorties : reports/tables/phase7_drias_eau_horizons.csv (simulation × niveau), phase7_drias_eau_synthese.csv (médianes et étendues).
"""

import numpy as np
import pandas as pd

from atlas.download import ROOT
from atlas.spatial import weighted_mean

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
TAB = ROOT / "reports" / "tables"
DEP17 = ["01", "03", "18", "26", "28", "36", "37", "38", "39", "41", "45", "58", "63", "67", "68", "69", "89"]
LEVELS = {"REF": "reference", "RWL20": "France +2.0", "RWL27": "France +2.7", "RWL40": "France +4.0"}


def read_indices(path) -> pd.DataFrame:
    head = [l for l in path.read_text(encoding="latin-1").splitlines() if l.startswith("#")]
    model = [l.split(":", 1)[1].strip() for l in head if l.startswith("# Modele")][0].removesuffix("_SIM2")
    d = pd.read_csv(path, sep=";", comment="#", header=None, encoding="latin-1",
                    names=["point", "lat", "lon", "contexte", "periode", "mois", "swi", "vide"]).drop(columns="vide")
    if not (set(d.mois) == {7, 8} and d.periode.nunique() == 1):
        raise SystemExit(path.name)
    return d.assign(modele=model)


def main() -> None:
    files = sorted((RAW / "drias_eau").glob("indices*.txt"))
    if not (len(files) == 68):
        raise SystemExit("68 fichiers DRIAS-Eau attendus")
    d = pd.concat([read_indices(f) for f in files], ignore_index=True)
    if not (d.groupby(["modele", "periode"]).size().eq(1582 * 2).all() and d.modele.nunique() == 17):
        raise SystemExit("17 simulations × 1 582 points × 2 mois attendus par période")

    # Points DRIAS-Eau -> mailles SAFRAN par les coordonnées (arrondies à 10⁻⁴ °, comme les fichiers).
    grid = pd.read_csv(RAW / "meteofrance_sim" / "coordonnees_grille_safran_lambert-2-etendu.csv", sep=";", decimal=",")
    grid.columns = ["LAMBX", "LAMBY", "lat", "lon"]
    pts = d[["point", "lat", "lon"]].drop_duplicates()
    m = pts.merge(grid.round({"lat": 4, "lon": 4}), on=["lat", "lon"], how="left", validate="one_to_one")
    if m.LAMBX.isna().any():                                   # repli : maille la plus proche, contrôlée à 1 km
        miss = m.LAMBX.isna()
        for i in m.index[miss]:
            dist = np.hypot(grid.lat - m.at[i, "lat"], (grid.lon - m.at[i, "lon"]) * np.cos(np.radians(m.at[i, "lat"])))
            if not (dist.min() < 0.01):
                raise SystemExit("point DRIAS-Eau sans maille SAFRAN proche")
            m.loc[i, ["LAMBX", "LAMBY"]] = grid.loc[dist.idxmin(), ["LAMBX", "LAMBY"]].to_numpy()
    weights = pd.read_parquet(PROC / "weights_cell_dep_maize.parquet")
    weights = weights[weights.dep_code.isin(DEP17)]
    cells = m[["point", "LAMBX", "LAMBY"]]
    if not (len(cells) == 1582 and set(map(tuple, cells[["LAMBX", "LAMBY"]].to_numpy())) == set(map(tuple, weights[["LAMBX", "LAMBY"]].drop_duplicates().to_numpy()))):
        raise SystemExit("mailles différentes du masque")

    # SWI de juillet-août par maille (moyenne des deux mois), puis par département (masque maïs), puis 17 départements.
    ja = d.groupby(["modele", "periode", "point"]).swi.mean().reset_index().merge(cells, on="point")
    dep = weighted_mean(ja, weights, ["swi"], "w_maize", ["modele", "periode"])
    ref_w = (pd.read_parquet(PROC / "panel_mais_long.parquet").query("echantillon_principal")
             .groupby("dep_code").surface_ref_ha.first())
    nat = dep.groupby(["modele", "periode"]).apply(
        lambda g: np.average(g.swi, weights=ref_w.reindex(g.dep_code)), include_groups=False).rename("swi_ja").reset_index()
    ref = nat[nat.periode == "REF"].set_index("modele").swi_ja
    nat["delta_swi_ja"] = nat.swi_ja - nat.modele.map(ref)
    nat["horizon"] = nat.periode.map(LEVELS)

    # Contrôle : SWI de référence des simulations contre SWI observé (SIM2) sur 1976-2005, mêmes poids.
    obs = pd.read_parquet(PROC / "weather_dep_month_maize.parquet")
    obs = obs[obs.month.isin([7, 8]) & obs.dep_code.isin(DEP17) & obs.year.between(1976, 2005)]
    obs_ja = obs.groupby(["year", "dep_code"]).swi.mean().reset_index()
    obs_ja["w"] = ref_w.reindex(obs_ja.dep_code).to_numpy()
    swi_obs = obs_ja.groupby("year").apply(lambda g: np.average(g.swi, weights=g.w), include_groups=False).mean()

    # Projection : β̂ ΔDD + δ̂ ΔSWI par simulation (ΔDD des projections de chaleur, mêmes simulations et niveaux).
    h = pd.read_csv(TAB / "phase4bis_q1_hypotheses.csv").set_index("hypothese")
    beta, delta = h.loc["H1", "estimation"], h.loc["H2a", "estimation"]
    ci = pd.read_csv(TAB / "phase4bis_q1_verif_intervalles.csv").query("modele == 'A1 maïs 2000-2025' and niveau == 0.9").iloc[0]
    d1 = pd.read_csv(TAB / "phase7_drias_horizons.csv")
    # Noms DRIAS-Climat (GCM_RCM, GCM abrégé) -> noms DRIAS-Eau (RCM_GCM, GCM complet) ; mêmes 17 couples.
    gcm = {"HadGEM2": "HadGEM2-ES", "MPI-ESM": "MPI-ESM-LR", "IPSL-CM5A": "IPSL-CM5A-MR", "NorESM1": "NorESM1-M"}
    d1["modele"] = d1.modele.str.split("_").map(lambda p: f"{p[1]}_{gcm.get(p[0], p[0])}")
    out = nat[nat.periode != "REF"].merge(d1[["modele", "horizon", "delta_dd_32_ja"]], on=["modele", "horizon"],
                                          how="left", validate="one_to_one")
    if not (out.delta_dd_32_ja.notna().all() and len(out) == 51):
        raise SystemExit("simulations différentes entre chaleur et humidité du sol projetées")
    out["terme_chaleur"] = beta * out.delta_dd_32_ja
    out["terme_sol"] = delta * out.delta_swi_ja
    out["ecart_pct_chaleur"] = 100 * (np.exp(out.terme_chaleur) - 1)
    out["ecart_pct_total"] = 100 * (np.exp(out.terme_chaleur + out.terme_sol) - 1)
    out["ecart_pct_total_beta_bas"] = 100 * (np.exp(ci.borne_inf * out.delta_dd_32_ja + out.terme_sol) - 1)
    out["ecart_pct_total_beta_haut"] = 100 * (np.exp(ci.borne_sup * out.delta_dd_32_ja + out.terme_sol) - 1)
    out.to_csv(TAB / "phase7_drias_eau_horizons.csv", index=False)

    rows = []
    for hz, g in out.groupby("horizon"):
        rows.append({"horizon": hz, "simulations": len(g), "swi_ref_mediane": ref.median(), "swi_obs_1976_2005": swi_obs,
                     "delta_swi_mediane": g.delta_swi_ja.median(), "delta_swi_min": g.delta_swi_ja.min(),
                     "delta_swi_max": g.delta_swi_ja.max(),
                     "ecart_pct_chaleur_mediane": g.ecart_pct_chaleur.median(),
                     "ecart_pct_total_mediane": g.ecart_pct_total.median(),
                     "ecart_pct_total_min": g.ecart_pct_total.min(), "ecart_pct_total_max": g.ecart_pct_total.max(),
                     "ecart_pct_total_beta_bas": g.ecart_pct_total_beta_bas.median(),
                     "ecart_pct_total_beta_haut": g.ecart_pct_total_beta_haut.median(),
                     "terme_sol_mediane": g.terme_sol.median(), "terme_chaleur_mediane": g.terme_chaleur.median(),
                     "beta": beta, "delta": delta})
    syn = pd.DataFrame(rows)
    # Règle déclarée : l'humidité du sol change l'ordre de grandeur si |δ ΔSWI| médian > moitié de |β ΔDD| médian.
    syn["sol_change_ordre_de_grandeur"] = syn.terme_sol_mediane.abs() > 0.5 * syn.terme_chaleur_mediane.abs()
    syn.to_csv(TAB / "phase7_drias_eau_synthese.csv", index=False)
    print(syn.round(3).T.to_string())


if __name__ == "__main__":
    main()
