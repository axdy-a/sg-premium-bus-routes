"""Build GeoJSON Point features from a bus service JSON + bus-stops.json.

Writes one FeatureCollection per direction: ``{service}-1.geojson``, ``{service}-2.geojson``, …
The optional third CLI argument sets the output directory (its parent folder); the filename is ignored.
"""

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

    stem = svc_path.stem
    features_per_dir: list[list[dict]] = []
    missing: list[tuple[str, str, str]] = []

    for d in directions:
        dir_name = d["name"]
        dir_features: list[dict] = []
        for seq, code in enumerate(d["stops"]):
            row = by_name.get(code)
            if not row:
                missing.append((dir_name, code, str(seq)))
                continue
            c = row["coordinates"]
            dir_features.append(
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
        features_per_dir.append(dir_features)

    if missing:
        print("Missing from bus-stops.json:", file=sys.stderr)
        for dir_name, code, seq in missing:
            print(f"  {dir_name} seq {seq}: {code}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_dir = len(features_per_dir)
    print(f"Points GeoJSON: {svc_path.name} ({n_dir} direction(s))", flush=True)

    for i, group in enumerate(features_per_dir, start=1):
        dir_name = directions[i - 1]["name"]
        split_path = out_path.parent / f"{stem}-{i}.geojson"
        print(
            f"  [{i}/{n_dir}] {dir_name}: {len(group)} stops -> {split_path.name}",
            flush=True,
        )
        split_fc = {"type": "FeatureCollection", "features": group}
        split_path.write_text(json.dumps(split_fc, indent=2), encoding="utf-8")
        print(f"      wrote {len(group)} point features", flush=True)


if __name__ == "__main__":
    main()
