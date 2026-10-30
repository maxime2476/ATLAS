"""Degrés-jours au-dessus d'un seuil à partir de Tmin et Tmax quotidiennes.

Sinus simple (Baskerville & Emin 1969) : la température suit
T(t) = M + A sin(t) sur une période, avec M = (Tmin + Tmax)/2 et A = (Tmax - Tmin)/2.
Les degrés-jours au-dessus du seuil b valent la moyenne de max(T - b, 0) :
  - b <= Tmin        : M - b
  - b >= Tmax        : 0
  - sinon, avec θ = arcsin((b - M)/A) : [(M - b)(π/2 - θ) + A cos θ] / π

Double sinus (Gammans et al. 2017) : le jour J est la moyenne de deux demi-journées,
la montée Tmin(J) -> Tmax(J), puis la descente Tmax(J) -> Tmin(J+1). Chaque
demi-journée est un demi-cycle de sinus : sa moyenne est donc celle du sinus complet
de mêmes bornes.

Convention SIM retenue : Tmin(J) = TINF_H(J),
minimum du matin de J ; Tmax(J) = TSUP_H(J), maximum de l'après-midi de J.
Unité : °C·jour.
"""

import numpy as np


def single_sine(tmin, tmax, threshold):
    """Degrés-jours au-dessus de `threshold` pour un sinus entre tmin et tmax (vectorisé).

    L'ordre des bornes est indifférent : la descente Tmax(J) -> Tmin(J+1) du double sinus peut
    monter si Tmin(J+1) > Tmax(J) (rare dans DRIAS, absent de SIM2 et d'E-OBS). Un demi-sinus
    entre a et b a la même distribution de températures dans les deux sens : on trie les bornes.
    """
    a, b = np.asarray(tmin, dtype=float), np.asarray(tmax, dtype=float)
    tmin, tmax = np.minimum(a, b), np.maximum(a, b)  # np.minimum/maximum propagent les NaN
    mean = (tmin + tmax) / 2
    amp = (tmax - tmin) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.clip((threshold - mean) / amp, -1.0, 1.0)
    theta = np.arcsin(ratio)
    partial = ((mean - threshold) * (np.pi / 2 - theta) + amp * np.cos(theta)) / np.pi
    dd = np.where(threshold <= tmin, mean - threshold,
                  np.where(threshold >= tmax, 0.0, partial))
    # Valeurs manquantes conservées (et pas de division par zéro quand tmin == tmax).
    return np.where(np.isnan(tmin) | np.isnan(tmax), np.nan, dd)


def double_sine(tmin, tmax, tmin_next, threshold):
    """Degrés-jours du jour J : moyenne de la montée (tmin, tmax) et de la descente (tmin_next, tmax)."""
    return 0.5 * single_sine(tmin, tmax, threshold) + 0.5 * single_sine(tmin_next, tmax, threshold)


def single_sine_time_above(tmin, tmax, threshold):
    """Fraction du cycle (0 à 1) où le sinus entre tmin et tmax dépasse `threshold`.

    Avec θ = arcsin((b - M)/A) : (π/2 - θ)/π ; 1 si b <= tmin ; 0 si b >= tmax.
    Vaut aussi pour un demi-cycle montant ou descendant (même fraction) ; ordre des bornes
    indifférent, comme pour single_sine.
    """
    a, b = np.asarray(tmin, dtype=float), np.asarray(tmax, dtype=float)
    tmin, tmax = np.minimum(a, b), np.maximum(a, b)
    mean, amp = (tmin + tmax) / 2, (tmax - tmin) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        theta = np.arcsin(np.clip((threshold - mean) / amp, -1.0, 1.0))
    frac = np.where(threshold <= tmin, 1.0, np.where(threshold >= tmax, 0.0, (np.pi / 2 - theta) / np.pi))
    return np.where(np.isnan(tmin) | np.isnan(tmax), np.nan, frac)


def double_sine_time_in_bin(tmin, tmax, tmin_next, low, high):
    """Durée (en jours, 0 à 1) passée dans [low, high) le jour J, double sinus (classes de température)."""
    def above(b):
        if b == -np.inf:
            return 1.0
        if b == np.inf:
            return 0.0
        return 0.5 * single_sine_time_above(tmin, tmax, b) + 0.5 * single_sine_time_above(tmin_next, tmax, b)
    return above(low) - above(high)
