"""Indicateurs météo quotidiens par maille SIM, puis agrégation mensuelle.

Toutes les variables non linéaires (degrés-jours, jours au-dessus d'un seuil, jours secs)
sont calculées au niveau maille-jour AVANT toute agrégation spatiale ou temporelle.

Variables mensuelles produites (par maille) :
  dd_<b>      somme des degrés-jours au-dessus de b °C (double sinus), °C·jour
  hot_<b>     nombre de jours avec TSUP_H > b °C
  prec        somme des précipitations liquides + solides, mm
  etp         somme de l'ETP Penman-Monteith, mm
  swi         moyenne du Soil Wetness Index (sans dimension, ~0 flétrissement, ~1 capacité au champ)
  swi_dry     nombre de jours avec SWI < 0,4
  swi_deficit somme de max(0, 0,4 - SWI), indice·jour
  wg_racine   moyenne du contenu en eau de la couche racinaire, m3/m3
  tmin, tmax, tmean  moyennes mensuelles, °C
  n_days      nombre de jours du mois présents (contrôle)
"""

import duckdb
import numpy as np
import pandas as pd

from atlas.degree_days import double_sine

DD_THRESHOLDS = [0, 28, 29, 30, 31, 32, 33, 34]
HOT_THRESHOLDS = [30, 32]
SWI_DRY = 0.4  # seuil proche des 40 % d'eau extractible (Laurent et al. 2025)
COLUMNS = "LAMBX, LAMBY, DATE, TINF_H, TSUP_H, T, PRELIQ, PRENEI, ETP, SWI, WG_RACINE"


def read_year(path, next_path=None) -> pd.DataFrame:
    """Lit une année SIM et ajoute Tmin du lendemain (1er janvier de l'année suivante si disponible)."""
    con = duckdb.connect()
    df = con.execute(f"""SELECT {COLUMNS} FROM read_csv('{path}', delim=';', header=true)""").df()
    if next_path is not None:
        first = con.execute(f"""SELECT LAMBX, LAMBY, DATE, TINF_H FROM read_csv('{next_path}', delim=';', header=true)
                                WHERE DATE = (SELECT min(DATE) FROM read_csv('{next_path}', delim=';', header=true))""").df()
    else:
        first = pd.DataFrame(columns=["LAMBX", "LAMBY", "DATE", "TINF_H"])
    df["date"] = pd.to_datetime(df["DATE"].astype(str), format="%Y%m%d")
    df = df.sort_values(["LAMBX", "LAMBY", "date"]).reset_index(drop=True)
    df["tmin_next"] = df.groupby(["LAMBX", "LAMBY"])["TINF_H"].shift(-1)
    # Dernier jour de l'année : Tmin du 1er janvier suivant (NaN si le fichier suivant manque).
    jan1 = first[["LAMBX", "LAMBY", "TINF_H"]].rename(columns={"TINF_H": "tmin_jan1"})
    df = df.merge(jan1, on=["LAMBX", "LAMBY"], how="left", validate="many_to_one")
    df["tmin_next"] = df["tmin_next"].fillna(df["tmin_jan1"])
    return df.drop(columns="tmin_jan1")


def daily_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["LAMBX", "LAMBY", "date"]].copy()
    tmin = df["TINF_H"].to_numpy(float)
    tmax = df["TSUP_H"].to_numpy(float)
    tmin_next = df["tmin_next"].to_numpy(float)
    for b in DD_THRESHOLDS:
        out[f"dd_{b}"] = double_sine(tmin, tmax, tmin_next, b)
    for b in HOT_THRESHOLDS:
        out[f"hot_{b}"] = (tmax > b).astype(float)
    out["prec"] = df["PRELIQ"] + df["PRENEI"]
    out["etp"] = df["ETP"]
    out["swi"] = df["SWI"]
    out["swi_dry"] = (df["SWI"] < SWI_DRY).astype(float)
    out["swi_deficit"] = np.maximum(0.0, SWI_DRY - df["SWI"])
    out["wg_racine"] = df["WG_RACINE"]
    out["tmin"], out["tmax"], out["tmean"] = tmin, tmax, df["T"]
    return out


SUM_VARS = [f"dd_{b}" for b in DD_THRESHOLDS] + [f"hot_{b}" for b in HOT_THRESHOLDS] + \
           ["prec", "etp", "swi_dry", "swi_deficit"]
MEAN_VARS = ["swi", "wg_racine", "tmin", "tmax", "tmean"]


def monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Agrégation maille × mois.

    Masquage PAR VARIABLE : une valeur quotidienne manquante rend la variable du mois
    manquante (pas de somme partielle), sans affecter les autres variables. Exemple :
    décembre 2025, dont les degrés-jours du 31 exigent Tmin du 1er janvier 2026 (absent).
    """
    daily = daily.assign(year=daily["date"].dt.year, month=daily["date"].dt.month)
    g = daily.groupby(["LAMBX", "LAMBY", "year", "month"])
    sums = g[SUM_VARS].sum()
    means = g[MEAN_VARS].mean()
    size = g.size()
    complete = g[SUM_VARS + MEAN_VARS].count().eq(size, axis=0)  # aucune valeur manquante dans le mois
    res = pd.concat([sums, means], axis=1).where(complete)
    res["n_days"] = size
    return res.reset_index()


# Fenêtres fixées en phase 0 (§ 5) pour le blé tendre d'hiver, récolte de l'année t.
# Mois de l'année t-1 codés par un décalage -1.
WINDOWS = {
    "automne": [(-1, 9), (-1, 10), (-1, 11)],
    "hiver": [(-1, 12), (0, 1), (0, 2)],
    "printemps": [(0, 3), (0, 4)],
    "remplissage": [(0, 5), (0, 6)],
}


def harvest_year_windows(dep_month: pd.DataFrame, harvest_years, windows: dict | None = None) -> pd.DataFrame:
    """Département × année de récolte : sommes (SUM_VARS) et moyennes pondérées par les jours (MEAN_VARS) par fenêtre.

    Format large : colonnes `<variable>_<fenêtre>` (ex. dd_32_remplissage).
    Une fenêtre dont un mois manque est manquante. `windows` : par défaut WINDOWS (phase 0).
    """
    days = pd.to_datetime(dict(year=dep_month["year"], month=dep_month["month"], day=1)).dt.days_in_month
    dm = dep_month.assign(n_month_days=days.to_numpy())
    pieces = []
    for name, months in (windows or WINDOWS).items():
        rows = []
        for t in harvest_years:
            for offset, month in months:
                rows.append({"annee": t, "year": t + offset, "month": month})
        sel = dm.merge(pd.DataFrame(rows), on=["year", "month"], how="inner")
        expected = len(months)
        g = sel.groupby(["dep_code", "annee"])
        sums = g[SUM_VARS].sum(min_count=expected)
        weighted = sel[MEAN_VARS].mul(sel["n_month_days"], axis=0).assign(
            dep_code=sel["dep_code"], annee=sel["annee"], n=sel["n_month_days"])
        wg = weighted.groupby(["dep_code", "annee"])
        means = wg[MEAN_VARS].sum(min_count=expected).div(wg["n"].sum(), axis=0)
        block = pd.concat([sums, means], axis=1)
        block = block.where(g.size().eq(expected), axis=0)  # fenêtre incomplète -> manquante
        block.columns = [f"{c}_{name}" for c in block.columns]
        pieces.append(block)
    return pd.concat(pieces, axis=1).reset_index()
