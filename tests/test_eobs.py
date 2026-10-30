"""Tests de la lecture E-OBS (scripts/27_eobs_heat.py) sur un fichier netCDF-4 artificiel."""

import datetime as dt
import importlib.util

import h5py
import numpy as np

from atlas.download import ROOT

spec = importlib.util.spec_from_file_location("eobs", ROOT / "scripts" / "27_eobs_heat.py")
eobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eobs)


def test_nearest_index_on_regular_grid():
    grid = np.array([45.05, 45.15, 45.25, 45.35])
    assert eobs.nearest_index([45.04, 45.19, 45.21, 45.36], grid).tolist() == [0, 1, 2, 3]


def test_read_window_dates_scale_and_fill(tmp_path, monkeypatch):
    # Un an de données, 2 × 3 points ; valeur = numéro du jour dans l'année, en centièmes de °C.
    start = (dt.date(2003, 1, 1) - eobs.EPOCH).days
    n = 365
    values = np.repeat(np.arange(n, dtype=np.int16)[:, None, None] * 100, 2, axis=1).repeat(3, axis=2)
    values[200, 1, 2] = -9999                                      # 20 juillet, point (1, 2) manquant
    path = tmp_path / "tx.nc"
    with h5py.File(path, "w") as f:
        f["time"] = np.arange(start, start + n, dtype=np.int32)
        v = f.create_dataset("tx", data=values)
        v.attrs["_FillValue"] = np.array([-9999], dtype=np.int16)
        v.attrs["scale_factor"] = np.array([0.01], dtype=np.float32)
    monkeypatch.setattr(eobs, "eobs_file", lambda var, year: path)

    out = eobs.read_window("tx", 2003, np.array([0, 1]), np.array([0, 2]))
    assert out.shape == (63, 2)                                    # 1er juillet - 1er septembre inclus
    assert np.isclose(out[0, 0], 181) and np.isclose(out[-1, 0], 243)   # jours 182 et 244 de l'année (base 0)
    assert np.isnan(out[200 - 181, 1]) and not np.isnan(out[:, 0]).any()
