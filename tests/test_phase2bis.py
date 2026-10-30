"""Tests des données de la phase 2 bis (maïs 2000-2025, VigiEau, masque maïs, blé 1959-2025)."""

import numpy as np
import pandas as pd
import pytest

from atlas.download import ROOT

PROC = ROOT / "data" / "processed"


def load(name):
    path = PROC / name
    if not path.exists():
        pytest.skip(f"{name} absent : exécuter les scripts de la phase 2 bis")
    return pd.read_parquet(path)


def test_maize_panel_keys_sources_and_population():
    m = load("panel_mais_long.parquet")
    assert not m.duplicated(["dep_code", "annee", "modalite"]).any()
    assert set(m["modalite"]) == {"irrigue", "non_irrigue"}
    assert m["dep_code"].nunique() == 38 and m.loc[m.echantillon_principal, "dep_code"].nunique() == 17
    assert set(m.loc[m.annee < 2010, "source"]) == {"SAA_ancienne_serie"}
    assert set(m.loc[m.annee >= 2010, "source"]) == {"SAA_series_longues"}
    assert m["rendement_q_ha"].between(10, 200).all()
    assert np.allclose(np.exp(m["log_rendement"]), m["rendement_q_ha"])
    # Irrigué en moyenne au-dessus du non irrigué (contrôle de cohérence de l'étiquetage des modalités).
    w = m.pivot_table(index=["dep_code", "annee"], columns="modalite", values="log_rendement").dropna()
    assert (w["irrigue"] - w["non_irrigue"]).median() > 0.1


def test_maize_weather_and_vigieau_coverage():
    m = load("panel_mais_long.parquet")
    assert m["dd_32_ja"].notna().all() and (m["dd_32_ja"] >= m["dd_32_juillet"] - 1e-9).all()
    assert (m.loc[m.annee < 2012, "jours_crise_ja"].isna()).all()      # VigiEau exploitable dès 2012
    assert (m.loc[m.annee >= 2012, "jours_crise_ja"].notna()).all()


def test_vigieau_indicators_consistent():
    v = load("vigieau_dep_ete.parquet")
    assert not v.duplicated(["dep_code", "annee"]).any()
    assert set(v["annee"]) == set(range(2012, 2026))
    assert (v["jours_crise_ja"] <= v["jours_ar_plus_ja"]).all()
    assert (v["jours_ar_plus_ja"] <= v["jours_vigilance_plus_ja"]).all() and v["jours_vigilance_plus_ja"].le(62).all()
    assert set(v.loc[v.periode_principale, "annee"]) == set(range(2016, 2026))


def test_maize_mask_matches_saa_grain_maize():
    """Le code RPG « MIS » correspond au maïs GRAIN (et non au maïs fourrage) : contrôle de mesure du masque."""
    a = load("maize_area_cell_dep_rpg.parquet")
    saa = pd.read_parquet(ROOT / "data" / "interim" / "saa_cop_departements_long.parquet")
    rpg = a.groupby(["dep_code", "millesime"])["surf_ha"].sum()
    # Code 18 de la SAA : total maïs grain et maïs semence (16 + 17) ; la semence en fait environ 4 % en 2015-2017.
    grain = saa[(saa.culture_code == "18") & saa.metropole & saa.annee.between(2015, 2017)]
    grain = grain.set_index(["dep_code", "annee"])["surface_ha"]
    grain.index.names = rpg.index.names
    c = pd.concat([rpg.rename("rpg"), grain.rename("grain")], axis=1).fillna(0)
    c = c[c.rpg > 2000]
    assert np.corrcoef(c.rpg, c.grain)[0, 1] > 0.98
    ratio = c.groupby(level="millesime").sum()
    assert ((ratio.rpg / ratio.grain).between(0.95, 1.15)).all()


def test_wheat_1959_panel_consistent_with_1990_panel():
    p59, p90 = load("panel_ble_1959.parquet"), load("panel_ble_long.parquet")
    assert not p59.duplicated(["dep_code", "annee"]).any() and p59["annee"].min() == 1959
    cols = ["rendement_q_ha", "dd_32_remplissage", "swi_remplissage", "dd_0_automne"]
    a = p90.set_index(["dep_code", "annee"])[cols]
    b = p59.set_index(["dep_code", "annee"]).loc[a.index, cols]
    assert np.allclose(a.to_numpy(), b.to_numpy())                     # 1990-2025 identique
    assert p59.loc[p59.annee < 1990, "dd_0_automne"].notna().all()     # météo complète dès 1959


def test_maize_mask_2008_covers_main_sample_and_agrees_with_2015_17_mask():
    """Masque d'époque (Q1-R9) : couvre les 17 départements principaux et reste proche du masque 2015-2017."""
    h = load("weather_dep_harvest_maize2008.parquet")
    m = load("panel_mais_long.parquet")
    main = m[m.echantillon_principal & (m.modalite == "irrigue")][["dep_code", "annee", "dd_32_ja"]]
    j = main.merge(h, on=["dep_code", "annee"], how="left", suffixes=("", "_2008"), validate="one_to_one")
    assert j["dd_32_ja_2008"].notna().all()
    assert np.corrcoef(j["dd_32_ja"], j["dd_32_ja_2008"])[0, 1] > 0.98
