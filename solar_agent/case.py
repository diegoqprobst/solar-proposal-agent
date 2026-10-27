"""A case is a site described in case.json. Every number in it states where it came from.

    {"value": 12, "kind": "measured", "ref": "flow meter reading, 2026-10-20"}
    {"value": 0.45, "kind": "assumption", "ref": "typical small DC pump; confirm with the pump curve"}

A required number that is missing is not guessed: sizing stops and says what to measure.
"""

from __future__ import annotations

import json
from pathlib import Path

from solar_agent.trace import Value, given

# section -> field -> (unit, label)
FIELDS: dict[str, dict[str, tuple[str, str]]] = {
    "pumping": {
        "volume_m3_day": ("m3/day", "Water demand"),
        "head_m": ("m", "Total dynamic head"),
        "wire_to_water_eff": ("", "Pump wire-to-water efficiency"),
    },
    "lighting": {
        "route_length_m": ("m", "Route length"),
        "spacing_m": ("m", "Pole spacing"),
        "power_w": ("W", "Luminaire power"),
        "hours": ("h/day", "Hours on per night"),
    },
    "system": {
        "performance_ratio": ("", "PV performance ratio"),
        "module_wp": ("Wp", "PV module power"),
        "autonomy_days": ("days", "Battery autonomy"),
        "depth_of_discharge": ("", "Battery depth of discharge"),
        "battery_efficiency": ("", "Battery round-trip efficiency"),
        "system_voltage": ("V", "System DC voltage"),
    },
    "solar": {
        "design_psh": ("h/day", "Design peak sun hours"),
    },
    "diesel": {
        "genset_kwh_per_litre": ("kWh/L", "Generator specific output"),
        "days_per_year": ("days/year", "Days per year the generator would run"),
    },
}
REQUIRED_SECTIONS = ("system",)


class MissingData(ValueError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("missing data, measure or confirm: " + "; ".join(missing))


def _value(raw: dict, unit: str, label: str) -> Value:
    kind = raw.get("kind")
    ref = raw.get("ref", "").strip()
    if kind is None or not ref:
        raise ValueError(f"{label}: every value needs 'kind' and 'ref'")
    return given(raw["value"], unit, label, kind, ref, raw.get("note", ""))


def parse(case: dict) -> dict[str, dict[str, Value]]:
    missing: list[str] = []
    parsed: dict[str, dict[str, Value]] = {}
    for section, fields in FIELDS.items():
        raw_section = case.get(section)
        if raw_section is None:
            if section in REQUIRED_SECTIONS:
                missing += [label for _, label in fields.values()]
            continue
        parsed[section] = {}
        for key, (unit, label) in fields.items():
            if key in raw_section:
                parsed[section][key] = _value(raw_section[key], unit, label)
            else:
                missing.append(label)
    if "pumping" not in parsed and "lighting" not in parsed:
        missing.append("at least one load (pumping or lighting)")
    if missing:
        raise MissingData(missing)
    return parsed


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
