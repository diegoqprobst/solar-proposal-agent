"""CO2 avoided when solar replaces a diesel generator. No 'X tonnes': it is computed or it is not stated."""

from __future__ import annotations

from solar_agent.calc.loads import _check_positive
from solar_agent.trace import Value, assumed, derive, given

IPCC_DIESEL_CO2 = given(
    74.1, "kg CO2/GJ", "Diesel CO2 emission factor", "standard",
    "IPCC 2006 Guidelines, Vol. 2, Ch. 2, Table 2.2 (gas/diesel oil, 74,100 kg/TJ)",
)
IPCC_DIESEL_NCV = given(
    43.0, "MJ/kg", "Diesel net calorific value", "standard",
    "IPCC 2006 Guidelines, Vol. 2, Ch. 1, Table 1.2 (gas/diesel oil, 43.0 TJ/Gg)",
)


def diesel_co2_per_litre(density: Value | None = None) -> Value:
    density = density or assumed(0.84, "kg/L", "Diesel density", "typical value; use the supplier's figure if known")
    return derive(
        "CO2 per litre of diesel", "kg CO2/L", "emission factor x NCV x density / 1000",
        lambda ef, ncv, rho: ef * ncv * rho / 1000,
        ef=IPCC_DIESEL_CO2, ncv=IPCC_DIESEL_NCV, rho=density,
    )


def diesel_displaced(daily_energy: Value, genset_specific_output: Value, days_per_year: Value) -> Value:
    _check_positive(daily_energy, genset_specific_output, days_per_year)
    return derive(
        "Diesel displaced per year", "L/year", "daily energy / 1000 x days / generator kWh per litre",
        lambda e, out, days: e / 1000 * days / out,
        e=daily_energy, out=genset_specific_output, days=days_per_year,
    )


def co2_avoided(litres_per_year: Value, co2_per_litre: Value | None = None) -> Value:
    co2_per_litre = co2_per_litre or diesel_co2_per_litre()
    return derive(
        "CO2 avoided per year", "t CO2/year", "litres x kg CO2 per litre / 1000",
        lambda l, f: l * f / 1000,
        l=litres_per_year, f=co2_per_litre,
    )
