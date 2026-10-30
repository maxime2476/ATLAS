"""Tests de schéma, de clés, de cardinalité et de cohérence de la SAA départementale.

Les données ne sont pas versionnées : les tests sur fichiers sont ignorés (skip)
si les étapes 01 et 03 n'ont pas été exécutées.
"""

import pandas as pd
import pyarrow.parquet as pq
import pytest

from atlas.download import ROOT
from atlas.saa import dep_code_from_label, to_long

LONG = ROOT / "data" / "interim" / "saa_cop_departements_long.parquet"
ADMIN = ROOT / "data" / "raw" / "ign_admin_express" / "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet"


def require(path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(ROOT)} absent : exécuter scripts/01 puis 03")


@pytest.fixture(scope="module")
def saa() -> pd.DataFrame:
    require(LONG)
    return pd.read_parquet(LONG)


# --- Normalisation des codes (tests unitaires, sans données) ---------------------

@pytest.mark.parametrize("label, code", [
    ("077 - Seine-et-Marne", "77"),
    ("001 - Ain", "01"),
    ("02A - Corse-du-Sud", "2A"),
    ("02B - Haute-Corse", "2B"),
    ("971 - Guadeloupe", "971"),
])
def test_dep_code_from_label(label, code):
    assert dep_code_from_label(label) == code


def test_dep_code_rejects_unexpected_label():
    with pytest.raises(ValueError):
        dep_code_from_label("Seine-et-Marne")


def test_to_long_on_synthetic_frame():
    """Large -> long sans données réelles : lignes, NaN conservé, types, codes."""
    years = [2010, 2011]
    wide = pd.DataFrame({
        "LIB_REG2": ["94 - Corse", "02 - Martinique"],
        "LIB_DEP": ["02A - Corse-du-Sud", "972 - Martinique"],
        "LIB_SAA": ["01 - Blé tendre d'hiver et épeautre"] * 2,
        "STATUT_QUALITE": ["1", None],
        **{f"SURF_{y}": ["100", "0"] for y in years},
        **{f"REND_{y}": ["50", None] for y in years},   # rendement absent si surface nulle
        **{f"PROD_{y}": ["5000", "0"] for y in years},
    })
    long = to_long(wide)
    assert len(long) == 2 * len(years)
    assert set(long["dep_code"]) == {"2A", "972"}
    assert long["annee"].dtype.kind == "i"
    assert long.loc[long["dep_code"] == "972", "rendement_q_ha"].isna().all()
    corse = long[long["dep_code"] == "2A"].set_index("annee")
    assert corse.loc[2011, "surface_ha"] == 100 and corse.loc[2011, "rendement_q_ha"] == 50
    assert not long["metropole"][long["dep_code"] == "972"].any()


# --- Schéma, clés et cardinalités ------------------------------------------------

def test_schema(saa):
    expected = ["dep_code", "dep_libelle", "reg_libelle", "culture_code", "culture_libelle",
                "statut_qualite", "annee", "surface_ha", "rendement_q_ha", "production_q",
                "provisoire", "metropole"]
    assert list(saa.columns) == expected
    assert saa["annee"].between(2010, 2025).all()
    assert set(saa.loc[saa["provisoire"], "annee"]) == {2025}


def test_key_is_unique(saa):
    assert not saa.duplicated(["dep_code", "culture_code", "annee"]).any()


def test_each_series_has_16_years(saa):
    n_years = saa.groupby(["dep_code", "culture_code"])["annee"].nunique()
    assert (n_years == 16).all()


def test_departement_cardinality(saa):
    metro = set(saa.loc[saa["metropole"], "dep_code"])
    drom = set(saa.loc[~saa["metropole"], "dep_code"])
    assert len(metro) == 95          # 96 départements métropolitains moins Paris (75)
    assert "75" not in metro and {"2A", "2B"} <= metro
    assert drom == {"971", "972", "973", "974", "976"}


def test_codes_match_admin_express(saa):
    """Jointure SAA ↔ ADMIN EXPRESS : tous les codes SAA existent, seul Paris manque côté SAA."""
    require(ADMIN)
    admin = set(pq.read_table(ADMIN, columns=["code_insee"]).column("code_insee").to_pylist())
    saa_codes = set(saa["dep_code"])
    assert saa_codes <= admin
    assert admin - saa_codes == {"75"}


# --- Plages et cohérence ---------------------------------------------------------

def test_non_negative(saa):
    for col in ["surface_ha", "rendement_q_ha", "production_q"]:
        assert (saa[col].dropna() >= 0).all(), col


def test_no_missing_yield_when_area_positive(saa):
    m = saa[saa["metropole"] & (saa["surface_ha"] > 0)]
    assert m["rendement_q_ha"].notna().all()


def test_wheat_yield_plausible(saa):
    """Blé tendre d'hiver, départements ≥ 1000 ha : rendements entre 10 et 130 q/ha."""
    w = saa[(saa["culture_code"] == "01") & saa["metropole"] & (saa["surface_ha"] >= 1000)]
    assert len(w) > 1300
    assert w["rendement_q_ha"].between(10, 130).all()


def test_production_equals_area_times_yield(saa):
    """Production ≈ surface × rendement (tolérance 0,5 %, arrondis de publication)."""
    d = saa.dropna(subset=["surface_ha", "rendement_q_ha"])
    d = d[d["surface_ha"] > 0]
    gap = (d["production_q"] - d["surface_ha"] * d["rendement_q_ha"]).abs()
    within = gap <= 0.005 * d["production_q"].clip(lower=1)
    assert within.mean() > 0.999


def test_total_soft_wheat_is_sum_of_components(saa):
    """Surface « 03 Total blé tendre » = « 01 hiver » + « 02 printemps »."""
    s = saa.pivot_table(index=["dep_code", "annee"], columns="culture_code", values="surface_ha")
    gap = (s["03"] - s["01"] - s["02"]).abs()
    assert (gap <= 1).all()
