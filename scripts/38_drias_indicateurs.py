"""Étape 38 : degrés-jours > 32 °C et VPD de juillet-août projetés par DRIAS, par département et horizon TRACC.

Usage : uv run python scripts/38_drias_indicateurs.py   (après scripts/37_drias_telechargement.py)
Entrées : data/raw/drias/*.zip (NetCDF tasminAdjust, tasmaxAdjust, hussAdjust) ; data/raw/drias/commandes.csv ;
          data/raw/drias/fenetres_tracc.csv ; data/raw/meteofrance_sim/QUOT_SIM2_1976-2005 (contrôle) ;
          masque maïs, altitudes des mailles ; β de H1 et son intervalle à 90 % (R/21)
Sorties : data/processed/drias_dep_annee.parquet : modele, periode, dep_code, annee, dd_32_ja, vpd_ja
          reports/tables/phase7_drias_controle.csv     historique des modèles contre SIM2, 1976-2005
          reports/tables/phase7_drias_horizons.csv     par modèle et horizon : moyennes sur les 17 départements
          reports/tables/phase7_drias_synthese.csv     médiane et étendue entre modèles ; β × Δ
          reports/tables/phase7_drias_fenetres_tracc.csv  fenêtres TRACC de chaque modèle (copie)

Définitions :
  dd_32_ja : somme des degrés-jours > 32 °C de juillet-août par double sinus (tmin du jour, tmax, tmin du lendemain),
             comme pour SIM2 (atlas.degree_days), puis moyenne pondérée par le masque maïs ;
  vpd_ja   : moyenne de juillet-août de es(tmax) − e, e = q p / (0,622 + 0,378 q), p = pression standard à
             l'altitude de la maille (FAO-56) ; le même calcul est refait sur SIM2 (Q) pour le contrôle.
"""

import io
import zipfile

import duckdb
import h5py
import numpy as np
import pandas as pd

from atlas.degree_days import double_sine
from atlas.download import ROOT
from atlas.spatial import weighted_mean

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
TABLES = ROOT / "reports" / "tables"
DEP17 = ["01", "03", "18", "26", "28", "36", "37", "38", "39", "41", "45", "58", "63", "67", "68", "69", "89"]
HIST = (1976, 2005)


def es(t):
    """Pression de vapeur saturante (kPa), Tetens, t en °C (même formule que scripts/34_vpd.py)."""
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def pressure_kpa(z):
    """Pression atmosphérique standard (kPa) à l'altitude z (m), FAO-56 éq. 7."""
    return 101.3 * ((293 - 0.0065 * z) / 293) ** 5.26


def vapour_pressure(q, p):
    """Pression de vapeur réelle (kPa) à partir de l'humidité spécifique q (kg/kg) et de la pression p (kPa)."""
    return q * p / (0.622 + 0.378 * q)


def read_zip(path) -> dict:
    """Variables d'une archive DRIAS : tableaux (jours, mailles), dates, coordonnées SIM2 (hm).

    Les NetCDF livrés sont au format NetCDF-4 (HDF5) : lus avec h5py, déjà utilisé pour E-OBS.
    """
    out = {}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            var = name.split("_", 1)[0]
            with h5py.File(io.BytesIO(z.read(name)), "r") as f:
                units = f["time"].attrs["units"].decode()
                calendar = f["time"].attrs["calendar"].decode()
                if units != "days since 1950-01-01 00:00:00" or calendar not in ("standard", "gregorian"):
                    raise RuntimeError(f"{name} : temps {units} / {calendar} inattendu")
                dates = pd.Timestamp("1950-01-01") + pd.to_timedelta(f["time"][:], unit="D")
                x, y = np.meshgrid(f["x"][:], f["y"][:])
                values = f[var][:].astype(float).reshape(len(dates), -1)
            out[var] = values
            out["dates"] = pd.DatetimeIndex(dates).normalize()
            out["LAMBX"], out["LAMBY"] = np.rint(x.ravel() / 100).astype(int), np.rint(y.ravel() / 100).astype(int)
    return out


def cell_year(d: dict, altitude: pd.DataFrame, mask_cells: pd.DataFrame) -> pd.DataFrame:
    # L'archive couvre toutes les mailles terrestres du rectangle englobant la sélection : on ne garde que le masque.
    pos = pd.DataFrame({"LAMBX": d["LAMBX"], "LAMBY": d["LAMBY"]}).reset_index()
    pos = pos.merge(mask_cells, on=["LAMBX", "LAMBY"], how="inner", validate="one_to_one")
    if len(pos) != len(mask_cells):
        raise RuntimeError("mailles du masque absentes de l'archive")
    keep = np.zeros(len(d["LAMBX"]), dtype=bool)
    keep[pos["index"]] = True
    if np.isnan(d["tasmaxAdjust"][:, keep]).any():
        raise RuntimeError("valeurs manquantes sur une maille du masque")
    tmin = d["tasminAdjust"][:, keep] - 273.15
    tmax = d["tasmaxAdjust"][:, keep] - 273.15
    q = d["hussAdjust"][:, keep]
    if np.nanmax(q) > 0.1:
        raise RuntimeError("huss attendu en kg/kg")
    cells = pd.DataFrame({"LAMBX": d["LAMBX"][keep], "LAMBY": d["LAMBY"][keep]})
    z = cells.merge(altitude, on=["LAMBX", "LAMBY"], how="left").altitude_moy_m.to_numpy()
    if np.isnan(z).any():
        raise RuntimeError("altitude manquante pour une maille DRIAS")
    dates = d["dates"]
    ja = np.flatnonzero(dates.month.isin([7, 8]))
    if ja.max() + 1 >= len(dates):
        raise RuntimeError("le 1er septembre manque pour le double sinus du 31 août")
    dd = double_sine(tmin[ja], tmax[ja], tmin[ja + 1], 32)
    vpd = es(tmax[ja]) - vapour_pressure(q[ja], pressure_kpa(z)[None, :])
    years = dates.year[ja]
    rows = []
    for yr in np.unique(years):
        sel = years == yr
        if sel.sum() != 62:
            raise RuntimeError(f"{yr} : {sel.sum()} jours de juillet-août")
        rows.append(cells.assign(annee=yr, dd_32_ja=dd[sel].sum(axis=0), vpd_ja=vpd[sel].mean(axis=0)))
    return pd.concat(rows, ignore_index=True)


def sim2_control(altitude: pd.Series, weights: pd.DataFrame) -> pd.DataFrame:
    """VPD observé 1976-2005 recalculé comme pour DRIAS (Q de SIM2, en g/kg) ; degrés-jours de la chaîne."""
    con = duckdb.connect()
    parts = []
    for year in range(HIST[0], HIST[1] + 1):
        f = RAW / "meteofrance_sim" / f"QUOT_SIM2_{year}.csv.gz"
        d = con.execute(f"""SELECT LAMBX, LAMBY, TSUP_H, Q FROM read_csv('{f}', delim=';', header=true)
                            WHERE DATE BETWEEN {year}0701 AND {year}0831""").df()
        d = d.merge(altitude, on=["LAMBX", "LAMBY"], how="inner")
        d["vpd"] = es(d.TSUP_H) - vapour_pressure(d.Q / 1000, pressure_kpa(d.altitude_moy_m))
        parts.append(d.groupby(["LAMBX", "LAMBY"], as_index=False).vpd.mean().rename(columns={"vpd": "vpd_ja"})
                     .assign(annee=year))
    vpd = weighted_mean(pd.concat(parts), weights, ["vpd_ja"], "w_maize", ["annee"])
    m = pd.read_parquet(PROC / "weather_dep_month_maize.parquet")
    dd = (m[m.month.isin([7, 8]) & m.year.between(*HIST)].groupby(["dep_code", "year"], as_index=False).dd_32.sum()
            .rename(columns={"year": "annee", "dd_32": "dd_32_ja"}))
    return dd.merge(vpd, on=["dep_code", "annee"], validate="one_to_one")


def main() -> None:
    orders = pd.read_csv(RAW / "drias" / "commandes.csv", dtype={"reference": str})
    windows = pd.read_csv(RAW / "drias" / "fenetres_tracc.csv")
    altitude = pd.read_parquet(PROC / "cell_altitude.parquet")[["LAMBX", "LAMBY", "altitude_moy_m"]]
    weights = pd.read_parquet(PROC / "weights_cell_dep_maize.parquet")
    weights = weights[weights.dep_code.isin(DEP17)]
    mask_cells = weights[["LAMBX", "LAMBY"]].drop_duplicates()

    parts = []
    for o in orders.itertuples():
        zips = [p for p in (RAW / "drias").glob("*.zip") if p.name.endswith(f"_{o.reference}.zip")]
        if len(zips) != 1:
            raise SystemExit(f"archive de la commande {o.reference} absente : lancer scripts/37 telecharger")
        cy = cell_year(read_zip(zips[0]), altitude, mask_cells)
        if len(cy[["LAMBX", "LAMBY"]].drop_duplicates()) != o.points:
            raise RuntimeError(f"{o.reference} : nombre de mailles inattendu")
        dep = weighted_mean(cy, weights, ["dd_32_ja", "vpd_ja"], "w_maize", ["annee"])
        parts.append(dep.assign(modele=o.modele, periode="historique" if o.scenario == "Historique" else "rcp85"))
        print(f"{o.reference} {o.modele} {o.scenario} : dd_32_ja moyen {dep.dd_32_ja.mean():.2f}")
    panel = pd.concat(parts, ignore_index=True)
    if panel[["dd_32_ja", "vpd_ja"]].isna().any().any():
        raise RuntimeError("valeur départementale manquante")
    panel.to_parquet(PROC / "drias_dep_annee.parquet", index=False)

    # Poids des départements : surface de référence de maïs grain de A1.
    ref = (pd.read_parquet(PROC / "panel_mais_long.parquet").query("echantillon_principal")
             .groupby("dep_code").surface_ref_ha.first())

    def national(df):
        w = ref.reindex(df.dep_code).to_numpy()
        return pd.Series({"dd_32_ja": np.average(df.dd_32_ja, weights=w), "vpd_ja": np.average(df.vpd_ja, weights=w)})

    # Contrôle : historique des modèles contre SIM2 sur 1976-2005.
    obs = sim2_control(altitude, weights)
    obs_nat = obs.groupby("annee").apply(national, include_groups=False).mean()
    hist = panel[(panel.periode == "historique") & panel.annee.between(*HIST)]
    ctrl = hist.groupby(["modele", "annee"]).apply(national, include_groups=False).groupby("modele").mean()
    ctrl = ctrl.assign(dd_32_ja_sim2=obs_nat.dd_32_ja, vpd_ja_sim2=obs_nat.vpd_ja).reset_index()
    ctrl.to_csv(TABLES / "phase7_drias_controle.csv", index=False)
    print(f"SIM2 1976-2005 : dd_32_ja {obs_nat.dd_32_ja:.2f}, VPD {obs_nat.vpd_ja:.2f} kPa ; modèles : "
          f"{ctrl.dd_32_ja.min():.2f} à {ctrl.dd_32_ja.max():.2f}, {ctrl.vpd_ja.min():.2f} à {ctrl.vpd_ja.max():.2f}")

    # Horizons : historique 1976-2005 et les trois fenêtres TRACC de chaque modèle (années ≥ 2021).
    rows = []
    for model, g in panel.groupby("modele"):
        nat = g.groupby(["periode", "annee"]).apply(national, include_groups=False).reset_index()
        base = nat[(nat.periode == "historique") & nat.annee.between(*HIST)]
        rows.append({"modele": model, "horizon": "1976-2005", "debut": HIST[0], "fin": HIST[1],
                     "dd_32_ja": base.dd_32_ja.mean(), "vpd_ja": base.vpd_ja.mean()})
        for w in windows[windows.modele == model].itertuples():
            start = max(2021, w.debut)
            fut = nat[(nat.periode == "rcp85") & nat.annee.between(start, w.fin)]
            if len(fut) != w.fin - start + 1:
                raise RuntimeError(f"{model} {w.niveau} : années manquantes")
            rows.append({"modele": model, "horizon": w.niveau, "debut": start, "fin": w.fin,
                         "dd_32_ja": fut.dd_32_ja.mean(), "vpd_ja": fut.vpd_ja.mean()})
    hz = pd.DataFrame(rows)
    hz = hz.merge(hz[hz.horizon == "1976-2005"][["modele", "dd_32_ja", "vpd_ja"]], on="modele", suffixes=("", "_ref"))
    hz["delta_dd_32_ja"] = hz.dd_32_ja - hz.dd_32_ja_ref
    hz["delta_vpd_ja"] = hz.vpd_ja - hz.vpd_ja_ref
    hz.to_csv(TABLES / "phase7_drias_horizons.csv", index=False)
    windows.to_csv(TABLES / "phase7_drias_fenetres_tracc.csv", index=False)   # fenêtres du portail, versionnées ici

    # β de H1 et intervalle à 90 % par inversion du WCR (R/21), comme scripts/24_valorisation_mais.py.
    h1 = pd.read_csv(TABLES / "phase4bis_q1_hypotheses.csv").query("hypothese == 'H1'").iloc[0]
    ci = pd.read_csv(TABLES / "phase4bis_q1_verif_intervalles.csv")
    ci = ci[(ci.modele == "A1 maïs 2000-2025") & (ci.niveau == 0.90)].iloc[0]
    betas = {"": h1.estimation, "_ic90_bas": ci.borne_inf, "_ic90_haut": ci.borne_sup}
    syn = []
    for horizon, g in hz.groupby("horizon", sort=False):
        row = {"horizon": horizon, "modeles": len(g)}
        for c in ["dd_32_ja", "vpd_ja", "delta_dd_32_ja", "delta_vpd_ja"]:
            row[f"{c}_mediane"], row[f"{c}_min"], row[f"{c}_max"] = g[c].median(), g[c].min(), g[c].max()
        for suffix, b in betas.items():
            row[f"ecart_pct_beta{suffix}"] = 100 * (np.exp(b * row["delta_dd_32_ja_mediane"]) - 1)
        syn.append(row)
    syn = pd.DataFrame(syn)
    obs = (pd.read_parquet(PROC / "panel_mais_long.parquet").query("echantillon_principal and modalite == 'irrigue'")
             [["dep_code", "annee", "dd_32_ja"]])
    obs["w"] = ref.reindex(obs.dep_code).to_numpy()
    syn["dd_32_ja_sim2_2000_2025"] = obs.groupby("annee").apply(
        lambda g: np.average(g.dd_32_ja, weights=g.w), include_groups=False).mean()   # repère : support de β
    syn.to_csv(TABLES / "phase7_drias_synthese.csv", index=False)
    print(syn[["horizon", "modeles", "dd_32_ja_mediane", "dd_32_ja_min", "dd_32_ja_max", "vpd_ja_mediane",
               "ecart_pct_beta"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
