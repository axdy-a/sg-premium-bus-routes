"""Run route_to_geojson.py then stops_to_road_lines.py for one bus service JSON file.

Writes only per-direction files under output/<service>/, in service JSON order:
  {n}-1.geojson, {n}-2.geojson, … and {n}-1-roads.geojson, {n}-2-roads.geojson, …

Does not modify the logic of those scripts; they are invoked as subprocesses.
Usage:
  python run_bus_route.py 767.json
  python run_bus_route.py path/to/960.json --bus-stops path/to/bus-stops.json
  python run_bus_route.py 767.json -- --allow-service
Anything after -- is passed only to stops_to_road_lines.py.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    argv = sys.argv[1:]
    if "--" in argv:
        i = argv.index("--")
        main_argv = argv[:i]
        stops_extra = argv[i + 1 :]
    else:
        main_argv = argv
        stops_extra = []

    parser = argparse.ArgumentParser(
        description="Build points GeoJSON and roads GeoJSON for one bus service file."
    )
    parser.add_argument(
        "service_json",
        type=Path,
        help="Bus service JSON (array of {name, stops}) e.g. 767.json",
    )
    parser.add_argument(
        "--bus-stops",
        type=Path,
        default=None,
        metavar="PATH",
        help="Defaults to data/bus-stops.json in the project root (parent of scripts/)",
    )
    args = parser.parse_args(main_argv)

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    svc = args.service_json.resolve()
    if not svc.is_file():
        print(f"Not found: {svc}", file=sys.stderr)
        sys.exit(1)

    stops_path = (
        args.bus_stops.resolve()
        if args.bus_stops
        else (project_root / "data" / "bus-stops.json")
    )
    if not stops_path.is_file():
        print(f"Not found: {stops_path}", file=sys.stderr)
        sys.exit(1)

    stem = svc.stem
    out_dir = project_root / "output" / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    points_out = out_dir / f"{stem}.geojson"
    roads_out = out_dir / f"{stem}-roads.geojson"

    route_py = script_dir / "route_to_geojson.py"
    roads_py = script_dir / "stops_to_road_lines.py"
    for p in (route_py, roads_py):
        if not p.is_file():
            print(f"Missing script: {p}", file=sys.stderr)
            sys.exit(1)

    py = sys.executable
    print(f"Service {stem} -> output: {out_dir}", flush=True)

    print("Step 1/2: stop points (route_to_geojson.py)", flush=True)
    subprocess.run(
        [py, str(route_py), str(svc), str(stops_path), str(points_out)],
        check=True,
    )

    print("Step 2/2: road lines (stops_to_road_lines.py)", flush=True)
    subprocess.run(
        [py, str(roads_py), str(svc), str(stops_path), str(roads_out), *stops_extra],
        check=True,
    )
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
