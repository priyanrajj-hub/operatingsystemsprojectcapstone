from __future__ import annotations

import numpy as np

from aidax.scheduler import OnlineScaler


def test_online_scaler_cold_start() -> None:
    d = 3
    scaler = OnlineScaler(d=d)
    x0 = np.array([10.0, 20.0, 30.0])

    # With n=0, transform returns copy
    assert np.allclose(scaler.transform(x0), x0)

    # With n=1, transform still passes raw features
    scaler.update(x0)
    assert np.allclose(scaler.transform(x0), x0)


def test_online_scaler_welford_accuracy() -> None:
    d = 2
    scaler = OnlineScaler(d=d)
    data = [
        np.array([2.0, 10.0]),
        np.array([4.0, 20.0]),
        np.array([6.0, 30.0]),
        np.array([8.0, 40.0]),
    ]
    for x in data:
        scaler.update(x)

    mat = np.array(data)
    expected_mean = np.mean(mat, axis=0)
    expected_std = np.std(mat, axis=0, ddof=1)

    assert np.allclose(scaler.mean, expected_mean)
    test_vec = np.array([5.0, 25.0])
    transformed = scaler.transform(test_vec)
    expected_transformed = (test_vec - expected_mean) / expected_std
    assert np.allclose(transformed, expected_transformed)
