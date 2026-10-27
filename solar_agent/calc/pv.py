"""PV array and battery bank sizing for an off-grid or backup system."""

from __future__ import annotations

import math

from solar_agent.calc.loads import _check_fraction, _check_positive
from solar_agent.trace import Value, derive


def array_power(daily_energy: Value, design_psh: Value, performance_ratio: Value) -> Value:
    """kWp = E [kWh/day] / (peak sun hours [h/day] x PR). Size on the design (worst) month, not the annual mean."""
    _check_positive(daily_energy, design_psh)
    _check_fraction(performance_ratio)
    return derive(
        "PV array power", "kWp", "daily energy / 1000 / (design peak sun hours x performance ratio)",
        lambda energy, psh, pr: energy / 1000 / (psh * pr),
        energy=daily_energy, psh=design_psh, pr=performance_ratio,
    )


def module_count(array: Value, module_power: Value) -> Value:
    _check_positive(array, module_power)
    return derive(
        "PV modules", "units", "ceil(array kWp x 1000 / module Wp)",
        lambda kwp, wp: math.ceil(kwp * 1000 / wp),
        kwp=array, wp=module_power,
    )


def installed_power(modules: Value, module_power: Value) -> Value:
    return derive(
        "Installed PV power", "kWp", "modules x module Wp / 1000",
        lambda n, wp: n * wp / 1000,
        n=modules, wp=module_power,
    )


def battery_energy(daily_energy: Value, autonomy_days: Value, depth_of_discharge: Value,
                   round_trip_eff: Value) -> Value:
    """Nominal capacity so that `autonomy_days` of load stay within the allowed depth of discharge."""
    _check_positive(daily_energy, autonomy_days)
    _check_fraction(depth_of_discharge)
    _check_fraction(round_trip_eff)
    return derive(
        "Battery nominal energy", "Wh", "daily energy x autonomy days / (depth of discharge x efficiency)",
        lambda energy, days, dod, eff: energy * days / (dod * eff),
        energy=daily_energy, days=autonomy_days, dod=depth_of_discharge, eff=round_trip_eff,
    )


def battery_capacity_ah(energy: Value, system_voltage: Value) -> Value:
    _check_positive(energy, system_voltage)
    return derive(
        "Battery capacity", "Ah", "nominal energy / system voltage",
        lambda wh, v: wh / v,
        wh=energy, v=system_voltage,
    )
