"""Tests des degrés-jours sur des cas calculés à la main ou par intégration numérique."""

import numpy as np
import pytest

from atlas.degree_days import double_sine, double_sine_time_in_bin, single_sine, single_sine_time_above


def numeric_single_sine(tmin, tmax, b, n=200_000):
    """Référence indépendante : moyenne numérique de max(T - b, 0) sur un cycle de sinus."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    temp = (tmin + tmax) / 2 + (tmax - tmin) / 2 * np.sin(t)
    return np.maximum(temp - b, 0).mean()


def test_threshold_above_tmax_gives_zero():
    assert single_sine(10, 30, 32) == 0


def test_threshold_below_tmin_gives_mean_minus_threshold():
    assert single_sine(20, 30, 10) == pytest.approx(15.0)


def test_threshold_at_mean_closed_form():
    # b = M : θ = 0, DD = A / π
    assert single_sine(20, 36, 28) == pytest.approx(8 / np.pi)


@pytest.mark.parametrize("tmin, tmax, b", [(20, 36, 32), (15, 33, 30), (-5, 5, 0), (25, 40, 34)])
def test_matches_numeric_integration(tmin, tmax, b):
    assert single_sine(tmin, tmax, b) == pytest.approx(numeric_single_sine(tmin, tmax, b), abs=1e-4)


def test_monotone_in_tmax_and_decreasing_in_threshold():
    tmax = np.linspace(25, 40, 50)
    dd = single_sine(18, tmax, 30)
    assert np.all(np.diff(dd) >= -1e-12)
    dd_b = single_sine(18, 38, np.array([28, 30, 32, 34]))
    assert np.all(np.diff(dd_b) < 0)


def test_gdd_plus_edd_equals_mean_when_bounds_inactive():
    # Tmin > 0 : DD au-dessus de 0 = moyenne journalière, quelle que soit la part au-dessus de 32.
    tmin, tmax = 12.0, 35.0
    gdd_0_32 = single_sine(tmin, tmax, 0) - single_sine(tmin, tmax, 32)
    edd_32 = single_sine(tmin, tmax, 32)
    assert gdd_0_32 + edd_32 == pytest.approx((tmin + tmax) / 2)


def test_constant_temperature_day():
    # tmin == tmax : pas de division par zéro.
    assert single_sine(30, 30, 28) == pytest.approx(2.0)
    assert single_sine(30, 30, 32) == 0


def test_double_sine_equals_single_when_next_tmin_is_equal():
    assert double_sine(18, 34, 18, 32) == pytest.approx(single_sine(18, 34, 32))


def test_double_sine_warm_night_increases_exposure():
    # Une nuit suivante plus chaude augmente l'exposition du jour J.
    assert double_sine(18, 34, 24, 30) > double_sine(18, 34, 14, 30)


def test_missing_values_propagate():
    out = double_sine(np.array([10.0, np.nan]), np.array([30.0, 30.0]), np.array([np.nan, 10.0]), 28)
    assert np.isnan(out).all()



def numeric_time_above(tmin, tmax, b, n=200_000):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return ((tmin + tmax) / 2 + (tmax - tmin) / 2 * np.sin(t) > b).mean()


@pytest.mark.parametrize("tmin, tmax, b", [(10, 30, 20), (10, 30, 28), (15, 35, 33), (-5, 5, 0)])
def test_time_above_matches_numeric(tmin, tmax, b):
    assert single_sine_time_above(tmin, tmax, b) == pytest.approx(numeric_time_above(tmin, tmax, b), abs=1e-4)


def test_time_above_bounds():
    assert single_sine_time_above(10, 20, 5) == 1.0
    assert single_sine_time_above(10, 20, 25) == 0.0
    assert single_sine_time_above(10, 30, 20) == pytest.approx(0.5)


def test_bins_partition_the_day():
    edges = [-np.inf, 9, 12, 15, 18, 21, 24, 27, 30, 33, np.inf]
    tmin, tmax, tnext = np.array([8.0, 14.0]), np.array([31.0, 36.0]), np.array([10.0, 19.0])
    total = sum(double_sine_time_in_bin(tmin, tmax, tnext, lo, hi) for lo, hi in zip(edges[:-1], edges[1:]))
    assert np.allclose(total, 1.0)
    assert np.all(double_sine_time_in_bin(tmin, tmax, tnext, 33, np.inf)[0] == 0)  # Tmax 31 < 33


def numeric_double_sine(tmin, tmax, tmin_next, b, n=200_000):
    """Référence indépendante du double sinus : montée tmin -> tmax, puis descente tmax -> tmin_next,
    chacune sur une demi-journée, sans tri des bornes."""
    t = np.linspace(0, np.pi, n, endpoint=False)
    rise = (tmin + tmax) / 2 - (tmax - tmin) / 2 * np.cos(t)
    fall = (tmax + tmin_next) / 2 + (tmax - tmin_next) / 2 * np.cos(t)
    return 0.5 * np.maximum(rise - b, 0).mean() + 0.5 * np.maximum(fall - b, 0).mean()


@pytest.mark.parametrize("a, b, thr", [(33, 30, 32), (1, -2, 0), (25, 20, 22), (20, 25, 30), (20, 25, 10)])
def test_single_sine_ignores_bound_order(a, b, thr):
    # Bornes inversées (cas observé dans DRIAS : Tmin(J+1) > Tmax(J)) : jamais de degrés-jours négatifs.
    assert single_sine(a, b, thr) == pytest.approx(single_sine(b, a, thr))
    assert single_sine(a, b, thr) == pytest.approx(numeric_single_sine(min(a, b), max(a, b), thr), abs=1e-4)
    assert single_sine(a, b, thr) >= 0
    assert single_sine_time_above(a, b, thr) == pytest.approx(single_sine_time_above(b, a, thr))


@pytest.mark.parametrize("tmin, tmax, tnext, b", [(15, 30, 33, 32), (-3, -2, 1, 0), (18, 35, 22, 32), (10, 20, 24, 21)])
def test_double_sine_with_next_tmin_above_tmax(tmin, tmax, tnext, b):
    assert double_sine(tmin, tmax, tnext, b) == pytest.approx(numeric_double_sine(tmin, tmax, tnext, b), abs=1e-4)


def test_bins_partition_the_day_when_next_tmin_above_tmax():
    edges = [-np.inf, 9, 12, 15, 18, 21, 24, 27, 30, 33, np.inf]
    tmin, tmax, tnext = np.array([8.0, 20.0]), np.array([10.0, 31.0]), np.array([14.0, 34.0])
    parts = [double_sine_time_in_bin(tmin, tmax, tnext, lo, hi) for lo, hi in zip(edges[:-1], edges[1:])]
    assert np.allclose(sum(parts), 1.0) and all(np.all(p >= -1e-12) for p in parts)


def test_bound_sorting_keeps_missing_values():
    assert np.isnan(single_sine(np.nan, 30.0, 32)) and np.isnan(single_sine(35.0, np.nan, 32))
    assert np.isnan(single_sine_time_above(np.nan, 30.0, 32))
