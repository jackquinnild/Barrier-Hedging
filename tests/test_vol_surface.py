import numpy as np

from barrierhedge.vol_surface import SVISlice, VolSurface, fit_svi


def flat_surface(vol=0.2):
    slices = [SVISlice(T, a=vol**2 * T, b=0.0, rho=0.0, m=0.0, s=0.1) for T in (0.1, 0.25, 0.5, 1.0)]
    return VolSurface(slices, spot=100.0, r=0.03, q=0.01)


def test_flat_smile_gives_flat_local_vol():
    surf = flat_surface()
    for T in (0.05, 0.2, 0.7):
        assert np.allclose(surf.local_vol(np.array([-0.3, -0.1, 0.0, 0.1]), T), 0.20, atol=1e-6)


def test_svi_fit_recovers_a_known_smile():
    true = SVISlice(0.25, a=0.004, b=0.06, rho=-0.75, m=0.02, s=0.15)
    k = np.linspace(-0.5, 0.1, 40)
    fitted = fit_svi(k, true.iv(k), 0.25)
    assert fitted.rmse_vol < 1e-4
    assert np.allclose(fitted.iv(k), true.iv(k), atol=1e-4)


def test_local_vol_is_higher_on_the_put_side_of_a_skewed_smile():
    slices = [SVISlice(T, a=0.01 * T, b=0.12 * T, rho=-0.8, m=0.0, s=0.1) for T in (0.1, 0.25, 0.5, 1.0)]
    surf = VolSurface(slices, 100.0, 0.03, 0.01)
    low, at_the_money = surf.local_vol(np.array([-0.15, 0.0]), 0.25)
    assert low > at_the_money


def test_calendar_inconsistent_expiry_is_dropped():
    good = [SVISlice(T, a=0.04 * T, b=0.0, rho=0.0, m=0.0, s=0.1) for T in (0.1, 0.5)]
    bad = SVISlice(0.3, a=0.001, b=0.0, rho=0.0, m=0.0, s=0.1)   # less total variance than the 0.1y slice
    surf = VolSurface(good + [bad], 100.0, 0.03, 0.01)
    assert [s.T for s in surf.slices] == [0.1, 0.5]


def test_cached_vol_function_and_bump():
    vol = flat_surface().local_vol_function()
    spots = np.linspace(80, 120, 5)
    assert np.allclose(vol(0.1, spots), 0.2, atol=1e-6)
    assert np.allclose(vol.with_bump(0.01)(0.1, spots), 0.21, atol=1e-6)


def test_density_check():
    assert SVISlice(0.25, a=0.004, b=0.06, rho=-0.75, m=0.02, s=0.15).density_ok()
    assert not SVISlice(0.25, a=0.0001, b=3.0, rho=-0.99, m=0.0, s=0.001).density_ok()
