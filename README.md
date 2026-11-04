# Solar Proposal Agent

**An agent that never invents a number.** It turns a site's documents (datasheets, surveys, photos) into a sized solar + storage design where every figure traces back to its source, and anything it cannot prove is handed to a person.

Built for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details) (Oct 27 – Nov 4, 2026), track *Build for Your World*. Model: **Muse Spark 1.3** through the Meta Model API.

## The problem

In 2024 Ecuador rationed power for up to 14 hours a day. Rural water plants stopped pumping and footbridges used for evacuation went dark. Solar plus storage is the obvious answer; what blocks it is the proposal. Someone has to survey the site, size the system, choose products and write a budget that survives review. Installers do it by hand for every quote, and communities applying to a fund rarely have an engineer.

The author lived this firsthand. In 2024 he wrote a proposal to protect a rural water plant and its evacuation route with solar power in Santo Domingo de los Tsáchilas, Ecuador. It was never funded: it was set aside before anyone reviewed it. Reading his own proposal again, the weak spot was the technical basis. The system was never sized and the budget did not add up. This project is the tool that proposal needed.

## What it does

```
case folder: objective.md · site.json · documents/ (.txt .md .pdf, photos)
        │
        ▼
 Muse Spark agent ── reads documents ── records inputs through tools
        │                               (each input cites its source)
        ├─ get_solar_resource   NASA POWER, worst-month design value (code, not the model)
        ├─ ask_human            what the documents cannot prove goes to a person
        └─ size_system          deterministic sizing code
        │
        ▼
 proposal.md  — written by code: results, the full derivation of every number,
                and "open questions before signing"
 trace.json   — every tool call, every rejected input
```

## The principle: what you measure, you show

The model reads and records; it never does arithmetic and never decides what counts as proven.

- **Quote-checked inputs.** A value taken from a document must quote that document exactly, and the value must appear inside the quote. An invented quote, or a number that is not in its own quote, is rejected in code.
- **Units are enforced.** Efficiencies and similar fields must be fractions between 0 and 1 (45 % is 0.45). The live model once recorded `45`; the check now rejects it and the model corrects itself.
- **Sizing is deterministic code**: pumping energy, lighting, PV array, battery bank, CO2 avoided (the emission factor is derived from IPCC tables, never typed in). Every result carries its formula and inputs.
- **Assumptions become open questions.** Engineering defaults are allowed, but each is listed for a person to confirm before signing. Facts about the world (land, permits, access) cannot be assumed: the agent must ask.
- **The proposal text is written by code**, not by the model, so it cannot contain a figure that was not computed.
- **Missing data stops the process** instead of being papered over. A scanned PDF with no text layer is reported as unreadable.
- **Photos cannot be verified by code**, so a value read from one is recorded with its own kind (`image`), cites the photo, and always appears under open questions for confirmation on site.

## Built with Meta

| Meta tool | How it is used |
|---|---|
| **Muse Spark 1.3** (Meta Model API, OpenAI-compatible) | Agent loop with tool calling. It reads the case, records inputs with citations, decides what to ask a person, and triggers the sizing. It is a reasoning model, so each call is given a large token budget. |
| Image input | `read_image` shows a photo to the model. Implemented and unit-tested; see Status. |

Not used: SAM 3.1, Muse Voice, open-weight models.

## What was built during the hackathon, and what was not

Everything in this repository was written between Oct 27 and Nov 4, 2026. No code existed before. The 2024 funding proposal is background research that motivated the project; it is not included here.

## Evidence from live runs

On the synthetic example case (`cases/example-agent`), Muse Spark read two documents, recorded eleven quote-checked inputs, fetched real irradiance for the site from NASA POWER (3.23 h/day in the worst month, June), and sized the system in 18 turns: 16,283 Wh/day of load and about 7.15 kWp of PV (13 modules of 550 Wp). That daily energy matches an independent hand calculation.

A second live run used a real product datasheet (a solar street luminaire) and short notes taken from the 2024 proposal. The agent read both, then asked six questions it could not answer from the documents: water demand, pumping head, route length, pole spacing, luminaire power and hours of operation. It sized the system with flagged placeholders. (The "ILLUSTRATIVE ONLY" stamp on the report was added after this run, because the placeholders made the result look like a real design.) This run also exposed two limits, listed below.

The first live run exposed three defects, all fixed and covered by tests:

1. The model recorded percentages as `45` instead of `0.45`, and my validation accepted it because "45 %" appears in the quote. Fields are now range-checked.
2. After asking a person about a design parameter, the agent called `get_status` seven times in a row without progress. Repeated calls are now told nothing changed, and the instructions separate facts about the world (ask) from design defaults (assume and flag).
3. The run was reported as finished although the system was never sized. A run is now a success only if it was sized.

## Status and limits, honestly

- The worked example is **synthetic**. It exercises the pipeline and describes no real site.
- It sizes pumping and lighting loads with solar plus battery. It does not choose between products, price a budget from real quotes, or design the electrical layout. The budget module exists and is tested, but the agent does not use it yet.
- **Autonomous luminaires are not recognised.** The real datasheet describes a luminaire with its own integrated panel and battery. The agent sized a central supply for it anyway. Such luminaires should be counted, not powered from the central system.
- **The model sometimes does arithmetic.** The datasheet gives 15,000 lm at 230 lm/W and no wattage; the model divided to get 65 W and recorded it as an assumption. It is flagged for a person to confirm, but the division was not done by code.
- Facts about the place (water demand, head, route length) are placeholders unless a document provides them, and the report says so in its header.
- Photo reading and PDF datasheets are implemented and unit-tested against a scripted model. Live results on real photos are not part of the evidence above.
- Sizing uses NASA climatology for the worst month. It is a preliminary design for a qualified installer or engineer to review and sign.
- 41 offline tests, none of which call a live API.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest                       # offline
cp .env.example .env                             # add MODEL_API_KEY
.venv/bin/python -m solar_agent ping             # check the key
.venv/bin/python -m solar_agent agent cases/example-agent
```

Your own case goes in `private/<name>/` (git-ignored) with `objective.md`, `site.json` and `documents/`.

## Layout

```
solar_agent/
  trace.py           values that know their source: given / assumed / derived
  calc/              loads, PV and battery, emissions (IPCC-derived), budgets that add up
  solar_resource.py  NASA POWER client, worst-month design value
  case.py            case format; missing data names what to measure
  sizing.py          case -> design -> traced report
  agent/workspace.py the agent's tools and the checks that keep it honest
  agent/loop.py      the agent loop (plain OpenAI SDK)
  llm.py             Meta Model API client, .env loading, image input
cases/example-agent  synthetic case: survey, datasheets
tests/               offline tests and a scripted fake model
```

## License

MIT. Code is MIT; the example case is synthetic.
