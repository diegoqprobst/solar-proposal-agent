"""Daily energy of the loads a site needs to keep running: water pumping and lighting."""

from __future__ import annotations

import math

from solar_agent.trace import Value, derive

RHO_G_OVER_3600 = 1000 * 9.81 / 3600  # water density x gravity, J -> Wh: 2.725 Wh per m3 per m of head


def _check_fraction(v: Value) -> None:
    if not 0 < v.value <= 1:
        raise ValueError(f"{v.label} must be in (0, 1], got {v.value}")


def _check_positive(*values: Value) -> None:
    for v in values:
        if v.value <= 0:
            raise ValueError(f"{v.label} must be positive, got {v.value}")


def pumping_energy(volume: Value, head: Value, wire_to_water_eff: Value) -> Value:
    """Electrical energy per day to lift `volume` m3/day over total dynamic `head` m."""
    _check_positive(volume, head)
    _check_fraction(wire_to_water_eff)
    hydraulic = derive(
        "Hydraulic energy per day", "Wh/day", "1000 kg/m3 x 9.81 m/s2 x V x H / 3600",
        lambda volume, head: RHO_G_OVER_3600 * volume * head,
        volume=volume, head=head,
    )
    return derive(
        "Pumping energy per day", "Wh/day", "hydraulic energy / wire-to-water efficiency",
        lambda hydraulic, eff: hydraulic / eff,
        hydraulic=hydraulic, eff=wire_to_water_eff,
    )


def luminaire_count(route_length: Value, spacing: Value) -> Value:
    """Poles along a route, one at each end: ceil(L / s) + 1."""
    _check_positive(route_length, spacing)
    return derive(
        "Luminaires on route", "units", "ceil(route length / spacing) + 1",
        lambda length, spacing: math.ceil(length / spacing) + 1,
        length=route_length, spacing=spacing,
    )


def lighting_energy(count: Value, power: Value, hours: Value) -> Value:
    _check_positive(count, power, hours)
    return derive(
        "Lighting energy per night", "Wh/day", "luminaires x power x hours on",
        lambda count, power, hours: count * power * hours,
        count=count, power=power, hours=hours,
    )


def total_daily_energy(*loads: Value) -> Value:
    if not loads:
        raise ValueError("at least one load is required")
    named = {f"load_{i}": v for i, v in enumerate(loads)}
    return derive(
        "Total daily energy", "Wh/day", "sum of loads",
        lambda **kw: sum(kw.values()),
        **named,
    )
