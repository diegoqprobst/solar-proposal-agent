"""python -m solar_agent size CASE.json [--nasa-power PAYLOAD.json]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from solar_agent import case as case_mod
from solar_agent import sizing, solar_resource


def ping() -> int:
    from solar_agent import llm

    try:
        resp = llm.client().chat.completions.create(
            model=llm.model(), max_tokens=500,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        )
    except Exception as e:  # report the cause without ever printing the key
        print(f"FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    choice, usage = resp.choices[0], resp.usage
    print(f"model={llm.model()} finish_reason={choice.finish_reason}")
    if usage:
        details = getattr(usage, "completion_tokens_details", None)
        print(f"tokens: prompt={usage.prompt_tokens} completion={usage.completion_tokens} details={details}")
    extra = [k for k in ("reasoning", "reasoning_content") if getattr(choice.message, k, None)]
    if extra:
        print(f"message also carries: {', '.join(extra)}")
    text = (choice.message.content or "").strip()
    if not text:
        print("FAILED: the model returned no text. See finish_reason and tokens above.", file=sys.stderr)
        return 1
    print(f"OK, answered: {text!r}")
    return 0


def agent(case_dir: str, out: str, max_turns: int) -> int:
    from solar_agent import llm
    from solar_agent.agent import loop
    from solar_agent.agent.workspace import load_workspace

    ws, objective = load_workspace(case_dir)
    result = loop.run(llm.client(), llm.model(), ws, objective, max_turns=max_turns, log=print)
    dest = Path(out) / Path(case_dir).name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "proposal.md").write_text(ws.proposal(), encoding="utf-8")
    (dest / "trace.json").write_text(ws.trace_json(), encoding="utf-8")
    sized = ws.design is not None
    if result["final_text"]:
        print(f"\nagent: {result['final_text']}")
    status = "finished and sized" if result["finished"] and sized else (
        "finished but did NOT size the system" if result["finished"] else "STOPPED before finishing")
    print(f"\n{status} in {result['turns']} turns; wrote {dest}/proposal.md and trace.json")
    return 0 if result["finished"] and sized else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="solar_agent")
    sub = ap.add_subparsers(dest="command", required=True)
    sz = sub.add_parser("size", help="size a case and print the traced report")
    sz.add_argument("case")
    sz.add_argument("--nasa-power", help="saved NASA POWER payload; otherwise fetched if the case has coordinates")
    ag = sub.add_parser("agent", help="run the agent on a case folder and write the proposal")
    ag.add_argument("case_dir")
    ag.add_argument("--out", default="runs")
    ag.add_argument("--max-turns", type=int, default=25)
    sub.add_parser("ping", help="check the Meta Model API key with one tiny request")
    args = ap.parse_args(argv)

    if args.command == "ping":
        return ping()
    if args.command == "agent":
        return agent(args.case_dir, args.out, args.max_turns)

    case = case_mod.load(args.case)
    psh = None
    site = case.get("site", {})
    if args.nasa_power:
        payload = json.loads(Path(args.nasa_power).read_text(encoding="utf-8"))
        psh = solar_resource.design_peak_sun_hours(payload, site["latitude"], site["longitude"])
    elif "latitude" in site and "design_psh" not in case.get("solar", {}):
        payload = solar_resource.fetch(site["latitude"], site["longitude"])
        psh = solar_resource.design_peak_sun_hours(payload, site["latitude"], site["longitude"])

    try:
        design = sizing.size(case, psh)
    except case_mod.MissingData as e:
        print("Cannot size this site yet. Measure or confirm:", file=sys.stderr)
        for item in e.missing:
            print(f"  - {item}", file=sys.stderr)
        return 2
    print(sizing.report(design))
    return 0


if __name__ == "__main__":
    sys.exit(main())
