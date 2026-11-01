import json
from pathlib import Path

from solar_agent.agent import loop
from solar_agent.agent.workspace import Workspace, load_workspace, value_in_quote
from tests.fake_model import FakeClient, call, reply

CASE = Path(__file__).parent.parent / "cases" / "example-agent"
FIXTURE = Path(__file__).parent / "fixtures" / "nasa_power_synthetic.json"


def workspace():
    ws, objective = load_workspace(CASE, solar_fetcher=lambda lat, lon: json.loads(FIXTURE.read_text()))
    return ws, objective


def sv(section, field, value, kind, quote, doc):
    return call("set_value", section=section, field=field, value=value, kind=kind, why_or_quote=quote, document=doc)


SURVEY, SHEETS = "site_survey.txt", "datasheets.txt"
GOOD_TURN = [
    sv("pumping", "volume_m3_day", 60, "measured", "Daily water consumption from the plant log: 60 m3/day.", SURVEY),
    sv("pumping", "head_m", 25, "measured", "Total dynamic head (static lift plus pipe losses), measured: 25 m.", SURVEY),
    sv("pumping", "wire_to_water_eff", 0.45, "datasheet", "wire-to-water efficiency at the duty point 45 %", SHEETS),
    sv("lighting", "route_length_m", 420, "measured", "Evacuation route length measured on foot: 420 m.", SURVEY),
    sv("lighting", "spacing_m", 30, "standard", "Pole spacing allowed by the municipal lighting rule: 30 m.", SURVEY),
    sv("lighting", "power_w", 40, "datasheet", "Solar street luminaire SL-40: power 40 W.", SHEETS),
    sv("lighting", "hours", 12, "measured", "dusk to dawn, 12 hours per night", SURVEY),
    sv("system", "module_wp", 550, "datasheet", "PV module XM-550: rated power 550 Wp.", SHEETS),
    sv("system", "depth_of_discharge", 0.8, "datasheet", "usable depth of discharge 80 %", SHEETS),
    sv("system", "battery_efficiency", 0.95, "datasheet", "round-trip efficiency 95 %", SHEETS),
    sv("system", "system_voltage", 51.2, "datasheet", "nominal voltage 51.2 V", SHEETS),
    sv("system", "performance_ratio", 0.75, "assumption", "typical off-grid performance ratio for the climate", ""),
    sv("system", "autonomy_days", 1.5, "assumption", "design choice to be agreed with the community", ""),
]


def test_value_in_quote_accepts_percentages_and_decimal_commas():
    assert value_in_quote(0.45, "efficiency 45 %") and value_in_quote(51.2, "51,2 V") and value_in_quote(25, "25 m")
    assert not value_in_quote(26, "25 m") and not value_in_quote(0.5, "efficiency 45 %")


def test_full_run_sizes_the_system_and_writes_the_proposal(tmp_path):
    ws, objective = workspace()
    script = [reply(call("get_status")), reply(call("get_solar_resource")), reply(*GOOD_TURN),
              reply(call("size_system")), reply(text="Done.")]
    result = loop.run(FakeClient(script), "fake", ws, objective)
    assert result == {"finished": True, "turns": 5, "final_text": "Done."}
    assert ws.design is not None
    md = ws.proposal()
    assert "Installed PV power" in md and "datasheets.txt" in md
    assert "performance ratio" in md.lower()  # the assumption shows up as an open question
    assert not [e for e in ws.events if e["event"] == "rejected"]


def test_invented_quote_is_rejected_and_nothing_is_recorded():
    ws, _ = workspace()
    r = ws.set_value("pumping", "head_m", 40, "measured", "Total dynamic head measured: 40 m", SURVEY)
    assert r["accepted"] is False and "quote does not appear" in r["reason"]
    assert "pumping" not in ws.case


def test_value_not_in_its_own_quote_is_rejected():
    ws, _ = workspace()
    r = ws.set_value("pumping", "head_m", 40, "measured", "Total dynamic head (static lift plus pipe losses), measured: 25 m.", SURVEY)
    assert r["accepted"] is False and "does not appear in the quote" in r["reason"]


def test_model_cannot_set_dataset_values_or_unknown_fields_or_empty_assumptions():
    ws, _ = workspace()
    assert not ws.set_value("solar", "design_psh", 9, "dataset", "x", "")["accepted"]
    assert not ws.set_value("pumping", "nonsense", 1, "assumption", "a reason that is long enough", "")["accepted"]
    assert not ws.set_value("system", "autonomy_days", 2, "assumption", "ok", "")["accepted"]


def test_sizing_without_inputs_lists_what_is_missing_instead_of_guessing():
    ws, _ = workspace()
    r = ws.size_system()
    assert r["sized"] is False and "PV performance ratio" in r["missing"]


def test_unprovable_matter_goes_to_a_person():
    ws, objective = workspace()
    script = [reply(call("ask_human", question="Who owns the land under the plant?", why="No document says.")),
              reply(text="Stopping.")]
    loop.run(FakeClient(script), "fake", ws, objective)
    assert "Who owns the land" in ws.proposal()


def test_turn_limit_and_token_exhaustion_are_reported_not_hidden():
    ws, objective = workspace()
    endless = [reply(call("get_status")) for _ in range(3)]
    assert loop.run(FakeClient(endless), "fake", ws, objective, max_turns=3)["finished"] is False
    truncated = [reply(finish="length")]
    assert loop.run(FakeClient(truncated), "fake", ws, objective)["finished"] is False


def test_bad_tool_arguments_do_not_crash_the_loop():
    ws, objective = workspace()
    bad = reply(call("read_document"), call("nope"))  # missing argument, unknown tool
    result = loop.run(FakeClient([bad, reply(text="ok")]), "fake", ws, objective)
    assert result["finished"] is True


def test_percentages_must_be_fractions_not_45():
    ws, _ = workspace()
    r = ws.set_value("pumping", "wire_to_water_eff", 45, "datasheet", "wire-to-water efficiency at the duty point 45 %", SHEETS)
    assert r["accepted"] is False and "0.45" in r["reason"]
    assert ws.set_value("pumping", "wire_to_water_eff", 0.45, "datasheet", "wire-to-water efficiency at the duty point 45 %", SHEETS)["accepted"]


def test_incomplete_diesel_section_only_drops_co2_it_does_not_block_sizing():
    ws, objective = workspace()
    script = [reply(call("get_solar_resource")), reply(*GOOD_TURN), reply(call("size_system")), reply(text="Done.")]
    script[1].choices[0].message.tool_calls.append(sv("diesel", "genset_kwh_per_litre", 3, "assumption", "routine small generator default", ""))
    loop.run(FakeClient(script), "fake", ws, objective)
    assert ws.design is not None and ws.design.co2_avoided is None


def test_repeated_get_status_is_told_nothing_changed():
    ws, _ = workspace()
    assert "note" not in ws.get_status()
    assert "Do not call it again" in ws.get_status()["note"]
    ws.ask_human("Who owns the land?", "unknown")
    assert "note" not in ws.get_status()


def test_out_of_range_input_reaches_the_model_as_text_not_a_crash():
    from solar_agent import case as case_mod
    ws, _ = workspace()
    ws.case.update({k: v for k, v in case_mod.load(CASE.parent / "example-pumping-route" / "case.json").items()
                    if k in ("pumping", "lighting", "system", "solar")})
    ws.case["system"]["performance_ratio"] = {"value": 75, "kind": "assumption", "ref": "typed as a percent"}
    r = loop.dispatch(ws, "size_system", {})
    assert r["sized"] is False and "out of range" in r["error"]
    ws.case["system"]["performance_ratio"]["value"] = 0.75
    assert loop.dispatch(ws, "size_system", {})["sized"] is True


def image_workspace(tmp_path):
    (tmp_path / "documents").mkdir()
    (tmp_path / "objective.md").write_text("Size it.")
    (tmp_path / "documents" / "plate.jpg").write_bytes(b"\xff\xd8not really a jpeg")
    (tmp_path / "documents" / "notes.txt").write_text("Head: 25 m")
    return load_workspace(tmp_path)


def test_photo_is_shown_to_the_model_in_the_next_message(tmp_path):
    ws, objective = image_workspace(tmp_path)
    client = FakeClient([reply(call("read_image", name="plate.jpg")), reply(text="seen")])
    loop.run(client, "fake", ws, objective)
    last = client.seen[-1]
    assert last["role"] == "user" and last["content"][1]["type"] == "image_url"
    assert last["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert ws.pending_images == []


def test_photo_values_need_a_real_photo_and_always_become_open_questions(tmp_path):
    from solar_agent import case as case_mod
    from solar_agent.calc import loads
    from solar_agent.trace import open_questions

    ws, _ = image_workspace(tmp_path)
    assert not ws.set_value("pumping", "head_m", 25, "image", "visible on the pump plate", "notes.txt")["accepted"]
    assert not ws.set_value("pumping", "head_m", 25, "image", "x", "plate.jpg")["accepted"]
    assert ws.set_value("pumping", "head_m", 25, "image", "pump nameplate shows max head 25 m", "plate.jpg")["accepted"]

    ws.case["pumping"]["volume_m3_day"] = {"value": 10, "kind": "measured", "ref": "plant log"}
    ws.case["pumping"]["wire_to_water_eff"] = {"value": 0.5, "kind": "datasheet", "ref": "pump sheet"}
    p = case_mod.parse({**ws.case, "system": {k: {"value": 0.5 if k in ("performance_ratio", "depth_of_discharge", "battery_efficiency") else 1,
                                                  "kind": "measured", "ref": "x"} for k in case_mod.FIELDS["system"]}})["pumping"]
    energy = loads.pumping_energy(p["volume_m3_day"], p["head_m"], p["wire_to_water_eff"])
    [q] = open_questions(energy)
    assert q.label == "Total dynamic head" and q.source.kind == "image" and "plate.jpg" in q.source.ref


def test_oversized_photo_is_refused_with_a_clear_message(tmp_path, monkeypatch):
    ws, _ = image_workspace(tmp_path)
    from solar_agent import llm
    monkeypatch.setattr(llm, "MAX_IMAGE_BYTES", 5)
    assert "resize" in ws.read_image("plate.jpg")["error"]
