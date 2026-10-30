"""Étape 33 : panel maïs fourrage irrigué / non irrigué 2010-2025 (réplication de Q1 sur une autre culture).

Usage : uv run python scripts/07_build_wheat_mask.py --culture MIE   # masque maïs ensilage RPG 2015-2017
        uv run python scripts/33_mais_fourrage.py
Entrées : SAA séries longues, feuille FOU (lignes 04 irrigué et 05 non irrigué) ;
          data/processed/weather_dep_month_fodder.parquet (météo pondérée par le masque MIE)
Sortie : data/processed/panel_fourrage.parquet (une ligne par département × année où les deux modes sont observés)

Règles :
- population : irrigué ET non irrigué ≥ 1 000 ha chacun en moyenne 2010-2012 (règle du maïs grain) ;
- échantillon principal : toute la population (5 départements seulement en statut qualité 1) ;
- poids : surface totale de maïs fourrage 2010-2012 ; chaleur et SWI de juillet-août sur le masque MIE.
"""

import importlib.util

import numpy as np
import pandas as pd

from atlas.download import ROOT
from atlas.saa import read_sheet_wide, to_long
from atlas.weather import harvest_year_windows

PROC = ROOT / "data" / "processed"
SAA_ZIP = ROOT / "data" / "raw" / "agreste_saa" / "SAA-SeriesLongues-2010-2025_DonneesProvisoires-DepartementalesRegionales.zip"
_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "09_build_panel.py")
panel_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panel_mod)


def main() -> None:
    fou = to_long(read_sheet_wide(SAA_ZIP, "FOU"))
    fou = fou[fou.culture_code.isin(["04", "05"]) & fou.metropole].copy()
    fou["modalite"] = fou.culture_code.map({"04": "irrigue", "05": "non_irrigue"})
    ref = fou[fou.annee.between(2010, 2012)].groupby(["dep_code", "modalite"]).surface_ha.mean().unstack()
    pop = ref[(ref.irrigue >= 1000) & (ref.non_irrigue >= 1000)].index
    statut = fou[fou.modalite == "irrigue"].drop_duplicates("dep_code").set_index("dep_code").statut_qualite

    y = fou[fou.dep_code.isin(pop) & (fou.rendement_q_ha > 0)]
    wide = y.pivot_table(index=["dep_code", "annee"], columns="modalite", values="rendement_q_ha").dropna().reset_index()
    wide["ecart_log"] = np.log(wide.irrigue) - np.log(wide.non_irrigue)
    wide["surface_ref_ha"] = wide.dep_code.map(ref.sum(axis=1))
    wide["statut_irrigue"] = wide.dep_code.map(statut)
    n_pairs = len(wide)

    dm = pd.read_parquet(PROC / "weather_dep_month_fodder.parquet")
    h = harvest_year_windows(dm, range(2010, 2026), windows={"ja": [(0, 7), (0, 8)]})[["dep_code", "annee", "dd_32_ja", "swi_ja"]]
    out = wide.merge(h, on=["dep_code", "annee"], how="left", validate="one_to_one")
    out = out.merge(panel_mod.centroids(), on="dep_code", how="left", validate="many_to_one")
    if len(out) != n_pairs or out[["dd_32_ja", "swi_ja", "lat_centroide"]].isna().any().any():
        raise RuntimeError("jointure météo ou centroïdes incomplète dans le panel fourrage")
    out.to_parquet(PROC / "panel_fourrage.parquet", index=False)
    print(f"population : {len(pop)} départements ({int((statut[pop] == '1').sum())} en statut 1) ; "
          f"{n_pairs} paires département-année, {out.annee.min()}-{out.annee.max()} ; "
          f"écart médian {100 * (np.exp(out.ecart_log.median()) - 1):.1f} %")


if __name__ == "__main__":
    main()
