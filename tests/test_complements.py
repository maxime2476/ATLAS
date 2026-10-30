"""Tests des analyses complémentaires (scripts/28_complements_python.py et tables associées)."""

import importlib.util

import numpy as np
import pandas as pd
import pytest

from atlas.download import ROOT

spec = importlib.util.spec_from_file_location("compl", ROOT / "scripts" / "28_complements_python.py")
compl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compl)
PROC = ROOT / "data" / "processed"


def test_two_way_residuals_remove_department_and_year_means():
    # y = effet département + effet année + bruit : les résidus ne doivent garder que le bruit (centré).
    rng = np.random.default_rng(0)
    df = pd.DataFrame([(d, t) for d in "abcd" for t in range(2000, 2006)], columns=["dep_code", "annee"])
    noise = rng.normal(size=len(df))
    df["y"] = df.dep_code.map({"a": 1, "b": 2, "c": 3, "d": 4}) + (df.annee - 2000) * 0.5 + noise
    r = compl.two_way_residuals(df, ["y"], np.ones(len(df)))
    assert np.allclose(r.groupby(df.dep_code).y.mean(), 0, atol=1e-10)
    assert np.allclose(r.groupby(df.annee).y.mean(), 0, atol=1e-10)


@pytest.mark.skipif(not (PROC / "phase7_covariables_dep.parquet").exists(), reason="covariables absentes")
def test_covariates_and_fodder():
    cov = pd.read_parquet(PROC / "phase7_covariables_dep.parquet")
    assert len(cov) == 38 and cov.dep_code.is_unique
    assert cov.part_irriguee.between(0, 1).all() and cov.relief.sum() == 6
    fod = pd.read_parquet(PROC / "phase7_fourrage.parquet")
    assert not fod.duplicated(["dep_code", "annee"]).any()
    assert fod.annee.between(2010, 2025).all()
    assert fod.part_fourrage_non_irr.dropna().between(0, 1).all()


@pytest.mark.skipif(not (PROC / "panel_fourrage.parquet").exists(), reason="panel fourrage absent")
def test_fodder_panel():
    fo = pd.read_parquet(PROC / "panel_fourrage.parquet")
    assert not fo.duplicated(["dep_code", "annee"]).any()
    assert fo.annee.between(2010, 2025).all() and fo.dep_code.nunique() == 28
    assert (fo.irrigue > 0).all() and (fo.non_irrigue > 0).all()
    assert np.allclose(fo.ecart_log, np.log(fo.irrigue) - np.log(fo.non_irrigue))
    assert fo[["dd_32_ja", "swi_ja", "surface_ref_ha"]].notna().all().all() and (fo.dd_32_ja >= 0).all()


def test_tetens_saturation_pressure():
    # Valeurs de référence de la formule de Tetens : 0,6108 kPa à 0 °C, environ 3,17 kPa à 25 °C.
    spec = importlib.util.spec_from_file_location("vpd", ROOT / "scripts" / "34_vpd.py")
    vpd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vpd)
    assert np.isclose(vpd.es(0.0), 0.6108) and np.isclose(vpd.es(25.0), 3.168, atol=0.002)


@pytest.mark.skipif(not (PROC / "vpd_dep_ja.parquet").exists(), reason="VPD absent")
def test_vpd_panel():
    v = pd.read_parquet(PROC / "vpd_dep_ja.parquet")
    assert not v.duplicated(["dep_code", "annee"]).any() and v.annee.between(2000, 2025).all()
    assert v.vpd_ja.between(0.1, 5).all()      # kPa, ordre de grandeur estival


@pytest.mark.skipif(not (PROC / "vpd_dep_ja_fourrage.parquet").exists(), reason="VPD fourrage absent")
def test_vpd_fodder_panel():
    v = pd.read_parquet(PROC / "vpd_dep_ja_fourrage.parquet")
    assert not v.duplicated(["dep_code", "annee"]).any() and v.vpd_ja.between(0.1, 5).all()


DEP17 = ["01", "03", "18", "26", "28", "36", "37", "38", "39", "41", "45", "58", "63", "67", "68", "69", "89"]


@pytest.mark.skipif(not (PROC / "bnpe_irr_dep_annee.parquet").exists(), reason="BNPE absente")
def test_bnpe_panel_matches_raw_total():
    v = pd.read_parquet(PROC / "bnpe_irr_dep_annee.parquet")
    assert sorted(v.dep_code.unique()) == DEP17 and len(v) == 17 * 12
    assert not v.duplicated(["dep_code", "annee"]).any() and (v.volume_m3 > 0).all()
    raw = pd.concat(pd.read_csv(f, sep=";", usecols=["volume"]) for f in (ROOT / "data" / "raw" / "hubeau_bnpe").glob("*.csv"))
    assert np.isclose(v.volume_m3.sum(), raw.volume.sum())   # l'agrégation ne perd ni ne double aucun volume


@pytest.mark.skipif(not (PROC / "ra_irrigation_dep.parquet").exists(), reason="RA2020 absent")
def test_ra2020_shares():
    ra = pd.read_parquet(PROC / "ra_irrigation_dep.parquet")
    assert set(ra.annee_ra) == {2010, 2020} and not ra.duplicated(["dep_code", "annee_ra"]).any()
    assert ra.part_mais_grain_irrigue.dropna().between(0, 1).all()
    r68 = ra[(ra.dep_code == "68") & (ra.annee_ra == 2020)].iloc[0]   # valeurs lues dans le fichier brut
    assert r68.mais_grain_irrigue_ha == 30584 and r68.sau_irriguee_ha == 41994


@pytest.mark.skipif(not (ROOT / "reports" / "tables" / "phase7_valeur_m3_departement_annee.csv").exists(), reason="valeur du m³ absente")
def test_water_value_identities():
    w = pd.read_csv(ROOT / "reports" / "tables" / "phase7_valeur_m3_departement_annee.csv", dtype={"dep_code": str})
    assert sorted(w.dep_code.unique()) == ["01", "03", "18", "63", "67", "68"]
    assert np.allclose(w.dose_m3_ha, w.volume_m3 * w.part_2020 / w.surface_ha)
    ok = w.plausible
    assert (ok == w.dose_m3_ha.between(500, 3000)).all() and w.eur_par_m3[~ok].isna().all()
    assert np.allclose(w.eur_par_m3[ok], w.kg_par_m3[ok] / 100 * w.prix_eur_q[ok])


def test_water_value_medians_share_the_plausible_sample():
    # Dose, écart, kg/m³ et €/m³ : médianes sur les mêmes années plausibles ; la dose sur toutes les années à part.
    w = pd.read_csv(ROOT / "reports" / "tables" / "phase7_valeur_m3_departement_annee.csv", dtype={"dep_code": str})
    s = pd.read_csv(ROOT / "reports" / "tables" / "phase7_valeur_m3.csv", dtype={"dep_code": str}).set_index("dep_code")
    groups = {"ensemble": w, **dict(tuple(w.groupby("dep_code")))}
    for dep, g in groups.items():
        p = g[g.plausible]
        row = s.loc[dep]
        assert row.annees == len(g) and row.exclues == (~g.plausible).sum()
        assert row.dose_mediane_m3_ha == pytest.approx(p.dose_m3_ha.median())
        assert row.dose_mediane_toutes_m3_ha == pytest.approx(g.dose_m3_ha.median())
        assert row.gain_median_q_ha == pytest.approx(p.gain_q_ha.median())
        assert row.kg_par_m3_median == pytest.approx(p.kg_par_m3.median())
        assert row.eur_par_m3_median == pytest.approx(p.eur_par_m3.median())
    tot = s.loc["ensemble"]
    assert (tot.annees, tot.exclues) == (72, 8) and s.loc["63", "exclues"] == 6
    assert 500 <= tot.dose_mediane_m3_ha <= 3000


def _drias():
    spec = importlib.util.spec_from_file_location("drias", ROOT / "scripts" / "38_drias_indicateurs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pressure_and_vapour_pressure():
    d = _drias()
    assert np.isclose(d.pressure_kpa(0.0), 101.3) and np.isclose(d.pressure_kpa(1000.0), 90.0, atol=0.1)   # FAO-56
    # q = 0,622 e / (p − 0,378 e) inversée : e retrouvé à partir de q
    e, p = 1.8, 98.0
    q = 0.622 * e / (p - 0.378 * e)
    assert np.isclose(d.vapour_pressure(q, p), e)


@pytest.mark.skipif(not (PROC / "drias_dep_annee.parquet").exists(), reason="DRIAS absent")
def test_drias_panel():
    v = pd.read_parquet(PROC / "drias_dep_annee.parquet")
    assert v.modele.nunique() == 17 and sorted(v.dep_code.unique()) == DEP17
    assert not v.duplicated(["modele", "periode", "dep_code", "annee"]).any()
    assert v[["dd_32_ja", "vpd_ja"]].notna().all().all() and (v.dd_32_ja >= 0).all() and v.vpd_ja.between(0.1, 6).all()
    hist = v[v.periode == "historique"]
    assert hist.annee.between(1976, 2005).all() and len(hist) == 17 * 17 * 30
    syn = pd.read_csv(ROOT / "reports" / "tables" / "phase7_drias_synthese.csv")
    assert list(syn.horizon) == ["1976-2005", "France +2.0", "France +2.7", "France +4.0"]
    assert syn.dd_32_ja_mediane.is_monotonic_increasing


TAB = ROOT / "reports" / "tables"


@pytest.mark.skipif(not ((TAB / "phase7_signatures_saa.csv").exists() and (PROC / "panel_mais_long.parquet").exists()),
                    reason="signatures SAA ou panel absents")
def test_v2_signatures_recomputed_from_panel():
    # Arrondis et répétitions de R/28 recalculés indépendamment depuis le panel (échantillon principal).
    m = pd.read_parquet(PROC / "panel_mais_long.parquet").query("echantillon_principal")
    w = m.pivot_table(index=["dep_code", "annee"], columns="modalite", values="rendement_q_ha").dropna().reset_index()
    w = w.sort_values(["dep_code", "annee"])
    r = (w.irrigue / w.non_irrigue).round(2)
    prev, prev_year = r.groupby(w.dep_code).shift(), w.groupby("dep_code").annee.shift()
    repet = ((r == prev) & (w.annee - prev_year == 1))[prev.notna()]   # première année de chaque département exclue
    v2 = pd.read_csv(TAB / "phase7_signatures_saa.csv").iloc[0]
    assert len(w) == v2.n_paires == 435 and len(repet) == 418
    assert np.isclose(repet.mean(), v2.s2_repetition)
    old = w.annee <= 2009
    assert np.isclose((w.non_irrigue[old] % 1 == 0).mean(), v2.s1_entiers_pluvial_2000_2009)
    assert np.isclose((w.irrigue[~old] % 1 == 0).mean(), v2.s1_entiers_irrigue_2010_2025)
    assert v2.s2_ref_mediane < v2.s2_ref_p95 < v2.s2_repetition   # la signature retenue dépasse la référence


@pytest.mark.skipif(not (TAB / "phase7_taille_cv3.csv").exists(), reason="taille du CV3 absente")
def test_v1_cv3_table():
    v1 = pd.read_csv(TAB / "phase7_taille_cv3.csv")
    obs = v1[v1.diagnostic == "p CV3 observé"].cv3.iloc[0]
    g9 = pd.read_csv(TAB / "phase7_inferences.csv")
    assert np.isclose(obs, g9.p_unilateral_droite[g9.specification.str.contains("CV3")].iloc[0])
    pw = v1[v1.diagnostic.str.startswith("puissance")]
    assert pw.cv3.is_monotonic_increasing and v1[["cv3", "wcr"]].dropna().apply(lambda c: c.between(0, 1)).all().all()


@pytest.mark.skipif(not (PROC / "panel_mais_2026.parquet").exists(), reason="panel 2026 absent")
def test_panel_2026():
    # Mêmes départements que le panel 2000-2025, deux modes chacun, météo complète ; rien d'autre n'est modifié.
    p = pd.read_parquet(PROC / "panel_mais_2026.parquet")
    old = pd.read_parquet(PROC / "panel_mais_long.parquet")
    assert set(p.dep_code) == set(old.dep_code) and len(p) == 2 * 38
    assert not p.duplicated(["dep_code", "modalite"]).any()
    assert p.rendement_q_ha.between(5, 200).all() and p.dd_32_ja.notna().all() and p.swi_ja.between(-0.5, 2).all()
    main = p[p.echantillon_principal]
    assert main.dep_code.nunique() == 17
    # La surface de référence et le statut viennent du panel existant, sans changement.
    ref = old.drop_duplicates("dep_code").set_index("dep_code")
    assert (p.set_index("dep_code").surface_ref_ha == ref.surface_ref_ha.reindex(p.dep_code).to_numpy()).all()


FROZEN = {"phase7_p4_prevision_ble_2026_preenregistree.csv": "27cb25dfc1c36c4f96d067626d4c2b54202078f1b5ecae2c8f69afcde0427030",
          "phase7_p4_prevision_ble_2026.csv": "ff6b68195087e12f6f561745f4db932d2e531da2409111d30d85a7b08b9e7a6c"}


def test_frozen_specification_unchanged():
    # La spécification des tests sur les récoltes futures ne doit plus être modifiée.
    import hashlib
    spec = ROOT / "specification_recoltes_futures.md"
    assert hashlib.sha256(spec.read_bytes()).hexdigest() == "2c491d70842155e33c9e9bb7201c136337e356a26034e83dbe2638b8202cf8b2"


@pytest.mark.skipif(not (TAB / "phase7_p4_prevision_ble_2026.csv").exists(), reason="prévision 2026 absente")
def test_frozen_wheat_forecast_2026_registered():
    # Les fichiers enregistrés ne doivent plus changer : leurs empreintes SHA-256 sont fixées ici.
    # La prévision enregistrée la première (graine d'origine) est conservée à côté de celle recalculée avec la graine 123.
    import hashlib
    for name, sha in FROZEN.items():
        f = TAB / name
        assert hashlib.sha256(f.read_bytes()).hexdigest() == sha
        pred = pd.read_csv(f, dtype={"dep_code": str})
        assert len(pred) == 83 and pred.annee.eq(2026).all() and pred[["B0", "RF_B0", "GBM_B0"]].notna().all().all()


@pytest.mark.skipif(not (TAB / "phase7_drias_eau_horizons.csv").exists(), reason="humidité du sol projetée absente")
def test_p3_soil_projection_identities():
    out = pd.read_csv(TAB / "phase7_drias_eau_horizons.csv")
    assert len(out) == 17 * 3 and out.modele.nunique() == 17
    h = pd.read_csv(TAB / "phase4bis_q1_hypotheses.csv").set_index("hypothese")
    beta, delta = h.loc["H1", "estimation"], h.loc["H2a", "estimation"]
    assert np.allclose(out.terme_chaleur, beta * out.delta_dd_32_ja)
    assert np.allclose(out.ecart_pct_total, 100 * (np.exp(beta * out.delta_dd_32_ja + delta * out.delta_swi_ja) - 1))
    assert out.delta_swi_ja.between(-0.5, 0.5).all()


@pytest.mark.skipif(not (TAB / "phase7_levier_par_annee.csv").exists(), reason="levier absent")
def test_l1_leverage_and_wcr_cv3():
    lev = pd.read_csv(TAB / "phase7_levier_par_annee.csv")
    assert len(lev) == 26 and np.isclose(lev.levier_partiel.sum(), 1)       # parts de la variance résiduelle
    assert lev.loc[lev.levier_partiel.idxmax(), "annee"] == 2003
    l1b = pd.read_csv(TAB / "phase7_wcr_cv3.csv").iloc[0]
    g9 = pd.read_csv(TAB / "phase7_inferences.csv")
    assert np.isclose(l1b.se_cv3, g9.se[g9.specification.str.contains("CV3")].iloc[0])  # même CV3 que dans R/22
    assert 0 <= l1b.taille_placebo <= 1 and 0 <= l1b.p_unilateral_droite <= 1
