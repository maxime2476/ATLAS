"""Tests du repérage des rendements dérivés de la production dans le partage SAA (scripts/48_partage_saa.py)."""

import importlib.util

import pandas as pd
import pytest

from atlas.download import ROOT

spec = importlib.util.spec_from_file_location("partage", ROOT / "scripts" / "48_partage_saa.py")
partage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(partage)
OUT = ROOT / "data" / "processed" / "maize_partage_saa.parquet"


def test_entered_yield_is_not_derived_and_computed_yield_is():
    # Rendement saisi : production = rendement × surface exactement. Rendement calculé à partir de la production,
    # puis arrondi au dixième : le produit ne redonne pas la production publiée.
    prod = pd.Series([91 * 14612, 569990, 1_000_000])
    rdt = pd.Series([91.0, round(569990 / 8407, 1), 80.0])
    surf = pd.Series([14612, 8407, 12500])
    assert partage.derived(prod, rdt, surf).tolist() == [False, True, False]


def test_rounding_of_production_to_the_quintal_is_tolerated():
    # Une production arrondie au quintal (écart < 0,5 q) ne doit pas faire classer le rendement comme dérivé.
    assert not partage.derived(pd.Series([1000.4]), pd.Series([10.0]), pd.Series([100.0])).iloc[0]


@pytest.mark.skipif(not OUT.exists(), reason="table du partage SAA absente (données non versionnées)")
def test_partage_table_covers_the_panel_pairs():
    d = pd.read_parquet(OUT)
    assert len(d) == 981 and not d.duplicated(["dep_code", "annee"]).any()
    main = d[d.echantillon_principal]
    assert len(main) == 435
    # Cher 2003 : irrigué saisi, non irrigué dérivé.
    cher = main[(main.dep_code == "18") & (main.annee == 2003)].iloc[0]
    assert not cher.derive_irrigue and cher.derive_non_irrigue
