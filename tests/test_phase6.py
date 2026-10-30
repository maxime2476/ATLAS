"""Tests des données des extensions exploratoires (prix, pertes valorisées, panel maïs)."""

import numpy as np
import pandas as pd
import pytest

from atlas.download import ROOT

PRIX = ROOT / "data" / "processed" / "prix_ble_tendre.parquet"
PERTES = ROOT / "reports" / "tables" / "phase6_pertes_valeur.csv"
MAIS = ROOT / "data" / "processed" / "panel_mais.parquet"


def load(path):
    if not path.exists():
        pytest.skip("exécuter scripts/16_phase6_build.py")
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def test_price_series_complete_and_matches_eurostat_2012_2016():
    p = load(PRIX).set_index("annee")
    assert list(p.index) == list(range(2010, 2026)) and p["prix_eur_q"].notna().all()
    ref = p.loc[2012:2016]
    assert np.allclose(ref["prix_eur_q"], ref["prix_eurostat_eur_q"], rtol=0.005)  # raccord exact à 0,5 % près
    assert p["prix_eur_q"].between(10, 60).all()


def test_losses_are_consistent():
    loss = load(PERTES)
    assert len(loss) == 16
    assert np.allclose(loss["perte_valeur_Meur"], loss["perte_volume_Mq"] * loss["prix_eur_q"])
    assert loss.set_index("annee").loc[2016, "perte_volume_Mq"] == loss["perte_volume_Mq"].max()  # 2016, pire année


def test_maize_panel_keys_and_definition():
    m = load(MAIS)
    assert not m.duplicated(["dep_code", "annee"]).any()
    assert m["dep_code"].nunique() == 38 and m.drop_duplicates("dep_code")["echantillon_principal"].sum() == 17
    assert np.allclose(m["ecart_log"], np.log(m["rdt_irrigue"]) - np.log(m["rdt_non_irrigue"]))
    assert (m["surface_ref_ha"] >= 2000).all()  # ≥ 1000 ha irrigué + ≥ 1000 ha non irrigué


COMP = ROOT / "data" / "processed" / "ndvi_dep_composite.parquet"


def test_ndvi_features_use_only_composites_finished_before_forecast_date(monkeypatch):
    """Au 1er juin, aucune variable NDVI ne doit dépendre d'un composite se terminant le 1er juin ou après."""
    comp = load(COMP)
    import importlib.util
    spec = importlib.util.spec_from_file_location("n", ROOT / "scripts" / "19_forecast_ndvi.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    base = mod.ndvi_features()
    late = comp["fin"] >= pd.to_datetime(dict(year=comp["annee"], month=6, day=1))
    comp_mod = comp.copy()
    comp_mod.loc[late, "ndvi"] = 99.0          # valeurs absurdes sur les composites non disponibles au 1er juin
    orig = pd.read_parquet
    # monkeypatch restaure pandas.read_parquet à la fin du test, même en cas d'échec.
    monkeypatch.setattr(mod.pd, "read_parquet",
                        lambda p, *a, **k: comp_mod if str(p).endswith("ndvi_dep_composite.parquet") else orig(p, *a, **k))
    changed = mod.ndvi_features()
    june = [c for c in base.columns if c.endswith("_juin") and c.startswith("ndvi")]
    assert np.allclose(base[june].to_numpy(), changed[june].to_numpy(), equal_nan=True)
    assert (changed[[c for c in base.columns if c.endswith("_juillet")]] == 99.0).any().any()  # le 1er juillet les voit


def test_ndvi_imputation_ignores_test_year_values():
    """Les valeurs manquantes du NDVI sont remplacées par la moyenne d'ENTRAÎNEMENT du département."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("n", ROOT / "scripts" / "19_forecast_ndvi.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    train = pd.DataFrame({"dep_code": ["01", "01", "02"], "annee": [2010, 2011, 2010], "x": [0.4, np.nan, np.nan]})
    test = pd.DataFrame({"dep_code": ["01", "02", "01"], "annee": [2012, 2012, 2012], "x": [np.nan, np.nan, 50.0]})
    tr, te = mod.impute_by_train_dep_mean(train, test, ["x"])
    assert tr.x.tolist() == [0.4, 0.4, 0.4]          # département sans valeur : moyenne globale d'entraînement
    assert te.x.tolist() == [0.4, 0.4, 50.0]         # la valeur 50 de l'année test n'entre dans aucune moyenne
