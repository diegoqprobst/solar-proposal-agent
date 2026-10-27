"""Size a site's solar + storage system from a case, and write it up with every number traced."""

from __future__ import annotations

from dataclasses import dataclass

from solar_agent import case as case_mod
from solar_agent.calc import emissions, loads, pv
from solar_agent.trace import Value, explain, fmt, open_questions


@dataclass(frozen=True)
class Design:
    name: str
    daily_energy: Value
    array_power: Value
    modules: Value
    installed_power: Value
    battery_energy: Value
    battery_ah: Value
    loads: tuple[Value, ...]
    co2_avoided: Value | None

    def results(self) -> list[Value]:
        out = [self.daily_energy, self.installed_power, self.modules, self.battery_energy, self.battery_ah]
        return out + ([self.co2_avoided] if self.co2_avoided else [])

    def open_questions(self) -> list[Value]:
        return open_questions(*self.results())


def size(case: dict, design_psh: Value | None = None) -> Design:
    c = case_mod.parse(case)
    psh = design_psh or c.get("solar", {}).get("design_psh")
    if psh is None:
        raise case_mod.MissingData(["Design peak sun hours (site coordinates for NASA POWER, or a measured value)"])

    site_loads: list[Value] = []
    if p := c.get("pumping"):
        site_loads.append(loads.pumping_energy(p["volume_m3_day"], p["head_m"], p["wire_to_water_eff"]))
    if lt := c.get("lighting"):
        count = loads.luminaire_count(lt["route_length_m"], lt["spacing_m"])
        site_loads.append(loads.lighting_energy(count, lt["power_w"], lt["hours"]))

    s = c["system"]
    daily = loads.total_daily_energy(*site_loads)
    array = pv.array_power(daily, psh, s["performance_ratio"])
    modules = pv.module_count(array, s["module_wp"])
    battery = pv.battery_energy(daily, s["autonomy_days"], s["depth_of_discharge"], s["battery_efficiency"])

    co2 = None
    if d := c.get("diesel"):
        litres = emissions.diesel_displaced(daily, d["genset_kwh_per_litre"], d["days_per_year"])
        co2 = emissions.co2_avoided(litres)

    return Design(
        name=case.get("name", "Unnamed site"),
        daily_energy=daily,
        array_power=array,
        modules=modules,
        installed_power=pv.installed_power(modules, s["module_wp"]),
        battery_energy=battery,
        battery_ah=pv.battery_capacity_ah(battery, s["system_voltage"]),
        loads=tuple(site_loads),
        co2_avoided=co2,
    )


def report(design: Design) -> str:
    lines = [f"# {design.name}", "", "## Results", ""]
    lines += [f"- **{v.label}:** {fmt(v)}" for v in design.results()]
    lines += ["", "## How each number was obtained", ""]
    for v in design.results():
        lines += ["```", explain(v), "```", ""]
    questions = design.open_questions()
    lines += ["## Open questions before signing", ""]
    if questions:
        lines += [f"- **{q.label}** = {fmt(q)} is assumed: {q.source.ref}" for q in questions]
    else:
        lines.append("- None: every input is measured, from a datasheet, a standard or a dataset.")
    return "\n".join(lines) + "\n"
