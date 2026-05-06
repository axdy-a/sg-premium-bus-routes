"""Build GeoJSON Point features from a bus service JSON + bus-stops.json."""

import json
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    svc_path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "services" / "767.json"
    stops_path = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "data" / "bus-stops.json"
    out_path = (
        Path(sys.argv[3])
        if len(sys.argv) > 3
        else root / "output" / svc_path.stem / f"{svc_path.stem}.geojson"
    )

    with stops_path.open(encoding="utf-8") as f:
        stops_list = json.load(f)
    by_name = {s["name"]: s for s in stops_list}

    with svc_path.open(encoding="utf-8") as f:
        directions = json.load(f)

    features = []
    missing: list[tuple[str, str, str]] = []

    for d in directions:
        dir_name = d["name"]
        for seq, code in enumerate(d["stops"]):
            row = by_name.get(code)
            if not row:
                missing.append((dir_name, code, str(seq)))
                continue
            c = row["coordinates"]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [c["long"], c["lat"]]},
                    "properties": {
                        "stop": code,
                        "details": row.get("details", ""),
                        "wab": row.get("wab", ""),
                        "direction": dir_name,
                        "sequence": seq,
                    },
                }
            )

    fc = {"type": "FeatureCollection", "features": features}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(features)} features)")

    if missing:
        print("Missing from bus-stops.json:", file=sys.stderr)
        for dir_name, code, seq in missing:
            print(f"  {dir_name} seq {seq}: {code}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
