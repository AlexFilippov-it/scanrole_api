from queries import compute_delta


def test_compute_delta_positive():
    delta_abs, delta_pct, trend = compute_delta(120, 100)
    assert delta_abs == 20
    assert round(delta_pct, 2) == 20.0
    assert trend == "up"


def test_compute_delta_zero():
    delta_abs, delta_pct, trend = compute_delta(0, 0)
    assert delta_abs == 0
    assert delta_pct == 0
    assert trend == "flat"
