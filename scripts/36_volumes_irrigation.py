"""Étape 36 : volumes prélevés pour l'irrigation (BNPE) et part du maïs grain dans les surfaces irriguées (volumes et valeur du m³).

Usage : uv run python scripts/36_volumes_irrigation.py   (après scripts/01_download_raw.py --bnpe --ra2020)
Entrées : data/raw/hubeau_bnpe/irr_<dép.>_<période>.csv (Hub'Eau, usage IRR, 2012-2023) ;
          data/raw/agreste_ra2020/FDS_RA2020_0052.zip (surfaces irriguées par culture, 2010 et 2020) ;
          prix du maïs : data/raw/prix/ (raccord IPPAP-Eurostat de scripts/24_valorisation_mais.py)
Sorties : data/processed/bnpe_irr_dep_annee.parquet : dep_code, annee, volume_m3, n_ouvrages, part_volume_mesure
          data/processed/ra_irrigation_dep.parquet : dep_code, annee_ra, sau_irriguee_ha, mais_grain_irrigue_ha,
                                                     part_mais_grain_irrigue
          data/processed/prix_mais.parquet : annee, prix_eur_q

Règles : tous ouvrages,
statuts et modes d'obtention confondus. Un même ouvrage peut porter deux lignes la même année (deux points de mesure) :
elles sont additionnées. Les volumes portent sur toutes les cultures irriguées.
"""

import importlib.util
import io
import zipfile

import pandas as pd

from atlas.download import ROOT

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
YEARS = range(2012, 2024)


def bnpe() -> pd.DataFrame:
    files = sorted((RAW / "hubeau_bnpe").glob("irr_*.csv"))
    d = pd.concat([pd.read_csv(f, sep=";", dtype={"code_departement": str}) for f in files], ignore_index=True)
    if d.duplicated().any() or (d.code_usage != "IRR").any() or d.volume.isna().any() or (d.volume < 0).any():
        raise RuntimeError("lignes BNPE inattendues (doublons exacts, autre usage, volume manquant ou négatif)")
    print(f"{len(files)} fichiers, {len(d):,} lignes ; ouvrage-années en deux lignes : "
          f"{d.duplicated(['code_ouvrage', 'annee']).sum()} ({d[d.duplicated(['code_ouvrage', 'annee'], keep=False)].volume.sum() / 1e6:.1f} Mm³)")
    d["mesure"] = d.code_mode_obtention_volume.isin(["MED", "MES"])   # mesure directe ou volume mesuré
    out = (d.groupby(["code_departement", "annee"])
             .apply(lambda g: pd.Series({"volume_m3": g.volume.sum(), "n_ouvrages": g.code_ouvrage.nunique(),
                                         "part_volume_mesure": g.volume[g.mesure].sum() / g.volume.sum()}),
                    include_groups=False)
             .reset_index().rename(columns={"code_departement": "dep_code"}))
    full = out.groupby("dep_code").annee.apply(lambda a: sorted(a) == list(YEARS))
    if not full.all():
        raise RuntimeError(f"années manquantes : {list(full[~full].index)}")
    out["n_ouvrages"] = out.n_ouvrages.astype(int)
    return out


def ra2020() -> pd.DataFrame:
    rows = []
    with zipfile.ZipFile(RAW / "agreste_ra2020" / "FDS_RA2020_0052.zip") as outer:
        for name in sorted(n for n in outer.namelist() if n.endswith(".zip")):
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                csv_name = name.replace(".zip", ".csv")   # l'archive 2020 contient aussi le fichier 2010
                d = pd.read_csv(inner.open(csv_name), sep=";", dtype=str)
            d = d[(d.N027_LIB == "Superficie irrigée (hectares)") & (d.N110d_LIB == "Toutes exploitations")
                  & d.N307_LIB.isin(["SAU", "mais grain"]) & (d.GEOGRAPHIE.str.len() == 2)
                  & (d.GEOGRAPHIE != "FR")]
            d["valeur"] = pd.to_numeric(d.VALEUR, errors="coerce")       # « s » : secret statistique
            w = d.pivot_table(index="GEOGRAPHIE", columns="N307_LIB", values="valeur", aggfunc="first")
            w = w.rename(columns={"SAU": "sau_irriguee_ha", "mais grain": "mais_grain_irrigue_ha"}).reset_index()
            rows.append(w.rename(columns={"GEOGRAPHIE": "dep_code"}).assign(annee_ra=int(d.ANNREF.iloc[0])))
    out = pd.concat(rows, ignore_index=True)
    out["part_mais_grain_irrigue"] = out.mais_grain_irrigue_ha / out.sau_irriguee_ha
    if out.duplicated(["dep_code", "annee_ra"]).any() or (out.part_mais_grain_irrigue > 1).any():
        raise RuntimeError("table RA2020_0052 inattendue")
    return out[["dep_code", "annee_ra", "sau_irriguee_ha", "mais_grain_irrigue_ha", "part_mais_grain_irrigue"]]


def maize_price() -> pd.DataFrame:
    """Prix du maïs (€/q) : même raccord que la valorisation de la phase 4 bis, importé pour ne pas le dupliquer."""
    spec = importlib.util.spec_from_file_location("valorisation", ROOT / "scripts" / "24_valorisation_mais.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    price = module.maize_price()[0]   # (prix raccordé, prix Eurostat, ratio moyen, écart du ratio)
    return price.rename("prix_eur_q").rename_axis("annee").reset_index()


def main() -> None:
    vol = bnpe()
    vol.to_parquet(PROC / "bnpe_irr_dep_annee.parquet", index=False)
    print(f"bnpe_irr_dep_annee : {vol.dep_code.nunique()} départements × {vol.annee.nunique()} années ; "
          f"part mesurée médiane {vol.part_volume_mesure.median():.1%}")
    ra = ra2020()
    ra.to_parquet(PROC / "ra_irrigation_dep.parquet", index=False)
    price = maize_price()
    price.to_parquet(PROC / "prix_mais.parquet", index=False)
    print(f"prix du maïs 2012-2023 : {price[price.annee.between(2012, 2023)].prix_eur_q.round(1).tolist()} €/q")
    show = ra[ra.dep_code.isin(vol.dep_code)].pivot(index="dep_code", columns="annee_ra", values="part_mais_grain_irrigue")
    print("part du maïs grain dans la surface irriguée (17 départements) :")
    print(show.round(3).sort_values(2020, ascending=False).to_string())


if __name__ == "__main__":
    main()
