import math

import pytest

from solar_agent.calc import budget, emissions, loads, pv
from solar_agent.trace import Value, assumed, explain, given, open_questions


def m(value, unit="", label="x"):
    return given(value, unit, label, "measured", "test")


def test_value_is_given_or_derived_never_both_or_neither():
    with pytest.raises(ValueError):
        Value(1.0, "", "orphan")


def test_pumping_energy_matches_hand_calculation():
    # 10 m3/day over 20 m at 50%: 1000*9.81*10*20/3600 = 545 Wh hydraulic, 1090 Wh electrical
    e = loads.pumping_energy(m(10, "m3/day"), m(20, "m"), m(0.5))
    assert e.value == pytest.approx(1090.0, rel=1e-3)
    assert e.inputs[0].value == pytest.approx(545.0, rel=1e-3)


def test_efficiency_outside_0_1_is_rejected():
    with pytest.raises(ValueError):
        loads.pumping_energy(m(10), m(20), m(45))  # 45 typed instead of 0.45


def test_luminaires_include_both_ends():
    assert loads.luminaire_count(m(420, "m"), m(30, "m")).value == 15
    assert loads.luminaire_count(m(400, "m"), m(30, "m")).value == 15
    assert loads.luminaire_count(m(30, "m"), m(30, "m")).value == 2


def test_array_and_modules_round_up():
    kwp = pv.array_power(m(5000, "Wh/day"), m(4.0, "h/day"), m(0.75))
    assert kwp.value == pytest.approx(5 / 3)
    n = pv.module_count(kwp, m(550, "Wp"))
    assert n.value == math.ceil(1666.67 / 550) == 4
    assert pv.installed_power(n, m(550, "Wp")).value == pytest.approx(2.2)


def test_battery_sizing():
    wh = pv.battery_energy(m(5000), m(1.5), m(0.8), m(0.95))
    assert wh.value == pytest.approx(5000 * 1.5 / 0.76)
    assert pv.battery_capacity_ah(wh, m(48, "V")).value == pytest.approx(wh.value / 48)


def test_diesel_co2_factor_is_derived_from_ipcc_not_typed():
    f = emissions.diesel_co2_per_litre()
    assert f.value == pytest.approx(74.1 * 43.0 * 0.84 / 1000)  # 2.68 kg/L
    assert 2.6 < f.value < 2.75
    assert [q.label for q in open_questions(f)] == ["Diesel density"]


def test_co2_avoided():
    litres = emissions.diesel_displaced(m(10_000, "Wh/day"), m(2.5, "kWh/L"), m(365, "days/year"))
    assert litres.value == pytest.approx(1460)
    assert emissions.co2_avoided(litres).value == pytest.approx(1460 * 74.1 * 43.0 * 0.84 / 1e6)


def test_open_questions_lists_each_assumption_once():
    a = assumed(0.45, "", "Pump efficiency", "typical")
    e1 = loads.pumping_energy(m(10), m(20), a)
    e2 = loads.pumping_energy(m(5), m(20), a)
    total = loads.total_daily_energy(e1, e2)
    assert [q.label for q in open_questions(total)] == ["Pump efficiency"]


def test_explain_traces_back_to_sources():
    e = loads.pumping_energy(m(10, "m3/day", "Water demand"), m(20, "m", "Head"), m(0.5, "", "Eff"))
    text = explain(e)
    assert "Water demand" in text and "[measured: test]" in text


def usd(v):
    return given(v, "USD", "price", "datasheet", "quote")


def test_budget_adds_up_by_construction():
    b = budget.Budget((
        budget.LineItem("Equipment", "Modules", m(4, "units"), usd(120)),
        budget.LineItem("Equipment", "Pump", m(1, "units"), usd(900)),
        budget.LineItem("Labour", "Installation", m(3, "days"), usd(150)),
    ))
    assert b.category_total("Equipment").value == 1380
    assert b.total().value == 1830
    assert sum(b.shares().values()) == pytest.approx(1.0)


def test_budget_rejects_mixed_currencies():
    with pytest.raises(ValueError):
        budget.Budget((budget.LineItem("A", "x", m(1), given(1, "CHF", "p", "datasheet", "q")),))


def test_check_declared_flags_totals_that_do_not_add_up():
    assert budget.check_declared(1000, {"a": 600, "b": 400}, "ok") == []
    [d] = budget.check_declared(8800, {"pump": 4200, "lights": 3200}, "pumping and lighting")
    assert d.difference == 1400
