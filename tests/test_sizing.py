import copy
import json
from pathlib import Path

import pytest

from solar_agent import case as case_mod
from solar_agent import sizing, solar_resource
from solar_agent.__main__ import main

EXAMPLE = Path(__file__).parent.parent / "cases" / "example-pumping-route" / "case.json"
FIXTURE = Path(__file__).parent / "fixtures" / "nasa_power_synthetic.json"


def example():
    return case_mod.load(EXAMPLE)


def test_example_case_sizes_end_to_end():
    d = sizing.size(example())
    pumping, lighting = d.loads
    assert pumping.value == pytest.approx(1000 * 9.81 * 60 * 25 / 3600 / 0.45, rel=1e-6)
    assert lighting.value == 15 * 40 * 12
    assert d.daily_energy.value == pytest.approx(pumping.value + lighting.value)
    assert d.installed_power.value >= d.array_power.value
    assert d.co2_avoided is not None and d.co2_avoided.value > 0


def test_every_assumption_becomes_an_open_question():
    labels = {q.label for q in sizing.size(example()).open_questions()}
    assert {"Total dynamic head", "Design peak sun hours", "Diesel density"} <= labels


def test_missing_measurement_stops_sizing_instead_of_guessing():
    c = example()
    del c["pumping"]["head_m"]
    with pytest.raises(case_mod.MissingData) as e:
        sizing.size(c)
    assert e.value.missing == ["Total dynamic head"]


def test_value_without_source_is_rejected():
    c = example()
    c["pumping"]["head_m"] = {"value": 25}
    with pytest.raises(ValueError, match="kind"):
        sizing.size(c)


def test_report_contains_results_traces_and_questions():
    text = sizing.report(sizing.size(example()))
    assert "## Results" in text and "## Open questions before signing" in text
    assert "1000 kg/m3 x 9.81 m/s2 x V x H / 3600" in text


def test_nasa_power_design_value_is_the_worst_month():
    payload = json.loads(FIXTURE.read_text())
    psh = solar_resource.design_peak_sun_hours(payload, -0.25, -79.17)
    assert psh.value == 2.9 and "JUL" in psh.label
    assert psh.source.kind == "dataset" and psh.source.ref.startswith(solar_resource.POWER_URL)


def test_nasa_power_fill_values_are_not_used():
    payload = copy.deepcopy(json.loads(FIXTURE.read_text()))
    payload["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]["MAR"] = -999
    with pytest.raises(ValueError, match="MAR"):
        solar_resource.monthly_irradiance(payload)


def test_dataset_psh_overrides_the_assumed_placeholder():
    payload = json.loads(FIXTURE.read_text())
    psh = solar_resource.design_peak_sun_hours(payload, -0.25, -79.17)
    labels = {q.label for q in sizing.size(example(), psh).open_questions()}
    assert "Design peak sun hours" not in labels


def test_cli(capsys, tmp_path):
    assert main(["size", str(EXAMPLE), "--nasa-power", str(FIXTURE)]) == 0
    assert "PV modules" in capsys.readouterr().out
    c = example()
    del c["system"]
    broken = tmp_path / "case.json"
    broken.write_text(json.dumps(c))
    assert main(["size", str(broken)]) == 2
    assert "PV performance ratio" in capsys.readouterr().err


def test_load_env_reads_file_and_does_not_override(tmp_path, monkeypatch):
    from solar_agent import llm
    env = tmp_path / ".env"
    env.write_text('# c\nMODEL_API_KEY="abc"\nMODEL_API_MODEL=\nOTHER=1\n')
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_API_MODEL", raising=False)
    monkeypatch.setenv("OTHER", "keep")
    llm.load_env(env)
    import os
    assert os.environ["MODEL_API_KEY"] == "abc"
    assert "MODEL_API_MODEL" not in os.environ  # empty value ignored
    assert os.environ["OTHER"] == "keep"
