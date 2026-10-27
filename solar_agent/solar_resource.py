"""Solar resource at a site from NASA POWER (free, no key): monthly mean irradiance in kWh/m2/day.

kWh/m2/day on a horizontal surface equals peak sun hours. An off-grid or backup system is sized on the
worst month, so the design value is the monthly minimum, not the annual mean.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from solar_agent.trace import Value, given

POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
PARAMETER = "ALLSKY_SFC_SW_DWN"
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
FILL_VALUE = -999


def request_url(latitude: float, longitude: float) -> str:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError(f"invalid coordinates: {latitude}, {longitude}")
    query = urllib.parse.urlencode({
        "parameters": PARAMETER, "community": "RE",
        "latitude": f"{latitude:.4f}", "longitude": f"{longitude:.4f}", "format": "JSON",
    })
    return f"{POWER_URL}?{query}"


def fetch(latitude: float, longitude: float, timeout: float = 30) -> dict:
    with urllib.request.urlopen(request_url(latitude, longitude), timeout=timeout) as resp:
        return json.load(resp)


def monthly_irradiance(payload: dict) -> dict[str, float]:
    series = payload["properties"]["parameter"][PARAMETER]
    months = {m: float(series[m]) for m in MONTHS}
    missing = [m for m, v in months.items() if v == FILL_VALUE]
    if missing:
        raise ValueError(f"NASA POWER returned no data for {', '.join(missing)}")
    return months


def design_peak_sun_hours(payload: dict, latitude: float, longitude: float) -> Value:
    months = monthly_irradiance(payload)
    worst = min(months, key=months.get)
    return given(
        months[worst], "h/day", f"Design peak sun hours (worst month: {worst})", "dataset",
        request_url(latitude, longitude),
        note=f"NASA POWER climatology, {PARAMETER}; annual mean {sum(months.values()) / 12:.2f} kWh/m2/day",
    )
