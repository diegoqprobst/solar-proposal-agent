"""python -m solar_agent size CASE.json [--nasa-power PAYLOAD.json]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from solar_agent import case as case_mod
from solar_agent import sizing, solar_resource


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="solar_agent")
    sub = ap.add_subparsers(dest="command", required=True)
    sz = sub.add_parser("size", help="size a case and print the traced report")
    sz.add_argument("case")
    sz.add_argument("--nasa-power", help="saved NASA POWER payload; otherwise fetched if the case has coordinates")
    args = ap.parse_args(argv)

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
