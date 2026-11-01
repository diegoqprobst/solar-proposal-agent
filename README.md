# Solar Proposal Agent

**Site photos, a map and product datasheets in; a sized, budgeted and verifiable solar + storage proposal out.**

Built for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details) (Oct 27 – Nov 4, 2026), track *Build for Your World*.

## The problem

In 2024 Ecuador went through rationing of up to 14 hours a day. Businesses, schools, health posts and rural water systems went dark. Solar plus storage is the obvious answer. What blocks it is the proposal: the site survey, the sizing, the bill of materials and a budget that holds up. An installer builds every quote by hand. A community applying to a fund rarely has an engineer to do it.

The author ran into this firsthand. In 2024 he wrote a proposal to protect a rural water system and an evacuation route with solar in Santo Domingo de los Tsáchilas, Ecuador. It was never funded. That proposal is background research only. **No code existed before this hackathon.**

## The principle: what you measure, you show

The language model never does arithmetic and never invents a number.

- **Every number is traceable.** It is either *given*, with a source (measured on site, read from a datasheet, taken from a standard or a dataset, or explicitly assumed), or *derived*, with its formula and inputs. Any figure in a proposal can be explained back to where it came from.
- **Sizing is deterministic code.** Pumping energy, lighting, PV array, battery bank and CO2 avoided are all computed in code, with tests. The CO2 factor is derived from IPCC tables, not typed in.
- **Budgets add up by construction.** Totals and percentages are computed from line items. A hand-written budget can be audited for totals that do not match their parts.
- **Assumptions become open questions.** Anything nobody measured is listed for a person to confirm before signing.
- **Missing data stops the process.** If a required measurement is missing, sizing stops and says what to measure.

The agent built on top of this core uses Meta's models:

- **Muse Spark** reads photos and datasheets and drives the workflow.
- **SAM 3.1** segments equipment and surfaces in site photos.

The agent only fills in *given* values, with their source, and calls the calculators. A verification step rechecks every number and every citation.

## Status

| Part | State |
|---|---|
| Traceable values, sizing calculators, budget, CO2 | Done, tested |
| Case format (`case.json`), CLI, traced report | Done, tested |
| Solar resource from NASA POWER (worst-month design) | Done. Tested on a synthetic payload; not yet run live. |
| Meta Model API client | Written; not yet run against the live API |
| Agent loop (Muse Spark + tools), photo and datasheet reading, SAM 3.1 | Next |
| Verification layer, human sign-off, proposal document, UI | Next |

## Try it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/python -m solar_agent size cases/example-pumping-route/case.json \
    --nasa-power tests/fixtures/nasa_power_synthetic.json
```

The example case and the NASA POWER fixture are **synthetic**. They exercise the pipeline and do not describe a real site.

A value in `case.json` always states its origin:

```json
"head_m": {"value": 25, "kind": "measured", "ref": "site survey 2026-10-30, static lift + pipe losses"}
```

`kind` is one of `measured`, `datasheet`, `standard`, `dataset` or `assumption`.

## Layout

```
solar_agent/
  trace.py           traceable values: given / assumed / derived, explain, open questions
  calc/loads.py      pumping and lighting energy
  calc/pv.py         PV array, modules, battery bank
  calc/emissions.py  diesel displaced and CO2 avoided (IPCC-derived factor)
  calc/budget.py     budgets that add up; audit of hand-written totals
  solar_resource.py  NASA POWER client, worst-month design value
  case.py            case.json parsing; missing data -> what to measure
  sizing.py          case -> design -> traced report
  llm.py             Meta Model API client (OpenAI-compatible)
cases/               example case (synthetic)
tests/               offline tests; never call a live API
```

## Configuration

Copy `.env.example` to `.env` and set `MODEL_API_KEY`. Never commit `.env`.

## Disclaimer

This tool produces a preliminary design for a qualified installer or engineer to review and sign. It does not replace a site survey, an electrical design or compliance with local regulation.

## License

MIT

## Agent

```bash
python -m solar_agent ping                                  # check the Meta API key
python -m solar_agent agent cases/example-agent             # run the agent; writes runs/example-agent/
```

The agent only records inputs. A value cited from a document must quote it exactly, and the value must appear in the quote, or it is rejected. What a document cannot prove goes to a person. The proposal is written by code, never by the model. Muse Spark reasons before answering, so each call is given a generous token limit.
