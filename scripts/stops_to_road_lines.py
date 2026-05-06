"""Road-following LineStrings from bus stop sequences.

* ``--allow-service`` — OSRM only, waypoints are raw stop coordinates (may use
  ``highway=service`` where OSRM snaps).
* Default — snap each stop to the closest **non-service** OSM car way via the
  public Overpass API, then route with OSRM (no API key). Optional
  ``GRAPHHOPPER_API_KEY`` uses GraphHopper to exclude ``SERVICE`` in one shot
  instead.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


OSRM_DEFAULT = "https://router.project-osrm.org"
OVERPASS_DEFAULT = "https://overpass-api.de/api/interpreter"
GRAPHHOPPER_DEFAULT = "https://graphhopper.com/api/1"
MAX_WAYPOINTS = 100

# Ways we consider for snapping (excludes service, paths, pedestrian, etc.)
_HIGHWAY_RE = (
    r"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|"
    r"living_street|motorway_link|trunk_link|primary_link|secondary_link|"
    r"tertiary_link|road|busway|bus_guideway)$"
)

NO_SERVICE_MODEL = {
    "priority": [{"if": "road_class == SERVICE", "multiply_by": "0"}],
}

_SNAP_CACHE: dict[tuple[float, float], tuple[float, float]] = {}


def load_stop_coords(
    svc_path: Path, stops_path: Path
) -> tuple[list[tuple[str, list[tuple[float, float]]]], list[tuple[str, str]]]:
    with stops_path.open(encoding="utf-8") as f:
        by_name = {s["name"]: s for s in json.load(f)}
    with svc_path.open(encoding="utf-8") as f:
        directions = json.load(f)

    legs: list[tuple[str, list[tuple[float, float]]]] = []
    missing: list[tuple[str, str]] = []

    for d in directions:
        name = d["name"]
        coords: list[tuple[float, float]] = []
        for code in d["stops"]:
            row = by_name.get(code)
            if not row:
                missing.append((name, code))
                continue
            c = row["coordinates"]
            lon, lat = float(c["long"]), float(c["lat"])
            if not coords or (coords[-1][0] != lon or coords[-1][1] != lat):
                coords.append((lon, lat))
        if len(coords) >= 2:
            legs.append((name, coords))
        elif coords:
            print(f"Skip '{name}': need at least 2 stops with coordinates", file=sys.stderr)

    return legs, missing


def _dist_m(px: float, py: float, qx: float, qy: float) -> float:
    mid_lat = (py + qy) / 2
    dx = (qx - px) * 111_320 * math.cos(math.radians(mid_lat))
    dy = (qy - py) * 110_540
    return math.hypot(dx, dy)


def _closest_on_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> tuple[float, float, float]:
    apx, apy = px - ax, py - ay
    abx, aby = bx - ax, by - ay
    ab2 = abx * abx + aby * aby
    if ab2 < 1e-18:
        return ax, ay, _dist_m(px, py, ax, ay)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    qx, qy = ax + t * abx, ay + t * aby
    return qx, qy, _dist_m(px, py, qx, qy)


def _closest_on_geometry(
    px: float, py: float, geom: list[dict]
) -> tuple[float, float, float] | None:
    best: tuple[float, float, float] | None = None
    for i in range(len(geom) - 1):
        a, b = geom[i], geom[i + 1]
        ax, ay = float(a["lon"]), float(a["lat"])
        bx, by = float(b["lon"]), float(b["lat"])
        qx, qy, d = _closest_on_segment(px, py, ax, ay, bx, by)
        if best is None or d < best[2]:
            best = (qx, qy, d)
    return best


def _overpass_query(overpass_url: str, query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        overpass_url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SG-BUS-DATA-stops_to_road_lines/1.0 (local project)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def snap_to_non_service_highway(
    lon: float,
    lat: float,
    overpass_url: str,
    radii: tuple[int, ...] = (90, 180, 400, 900),
    pause_s: float = 0.35,
) -> tuple[float, float]:
    key = (round(lon, 6), round(lat, 6))
    if key in _SNAP_CACHE:
        return _SNAP_CACHE[key]

    px, py = lon, lat
    best: tuple[float, float, float] | None = None

    for ri, radius in enumerate(radii):
        q = (
            f"[out:json][timeout:90];\n"
            f"(\n"
            f'  way(around:{radius},{lat},{lon})["highway"~"{_HIGHWAY_RE}"];\n'
            f");\n"
            "out geom;\n"
        )
        if ri and pause_s > 0:
            time.sleep(pause_s)
        try:
            data = _overpass_query(overpass_url, q)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"Overpass error at ({lat:.5f},{lon:.5f}) r={radius}m: {e}", file=sys.stderr)
            break

        for el in data.get("elements") or []:
            if el.get("type") != "way":
                continue
            geom = el.get("geometry")
            if not geom or len(geom) < 2:
                continue
            hit = _closest_on_geometry(px, py, geom)
            if hit is None:
                continue
            qx, qy, d = hit
            if best is None or d < best[2]:
                best = (qx, qy, d)

        if best is not None:
            out = (best[0], best[1])
            _SNAP_CACHE[key] = out
            return out

    print(f"Snap fallback to raw stop near ({lat:.5f},{lon:.5f})", file=sys.stderr)
    out = (lon, lat)
    _SNAP_CACHE[key] = out
    return out


def snap_leg_coords(
    coords: list[tuple[float, float]],
    overpass_url: str,
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for lon, lat in coords:
        slon, slat = snap_to_non_service_highway(lon, lat, overpass_url)
        if not out or (out[-1][0] != slon or out[-1][1] != slat):
            out.append((slon, slat))
    return out


def osrm_line(coords: list[tuple[float, float]], base: str, profile: str) -> dict:
    if len(coords) > MAX_WAYPOINTS:
        raise ValueError(f"At most {MAX_WAYPOINTS} waypoints for this OSRM server")
    coord_str = ";".join(f"{lon},{lat}" for lon, lat in coords)
    q = urllib.parse.urlencode(
        {"overview": "full", "geometries": "geojson", "continue_straight": "true"}
    )
    url = f"{base.rstrip('/')}/route/v1/{profile}/{coord_str}?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "SG-BUS-DATA-stops_to_road_lines/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM: {data.get('code')} {data.get('message', '')}")
    return data["routes"][0]["geometry"]


def _graphhopper_points_to_linestring(points: object) -> dict:
    if isinstance(points, dict) and points.get("type") == "LineString":
        raw = points["coordinates"]
    elif isinstance(points, list):
        raw = points
    else:
        raise RuntimeError(f"Unexpected GraphHopper points format: {type(points)}")

    coordinates: list[list[float]] = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        coordinates.append([float(row[0]), float(row[1])])
    return {"type": "LineString", "coordinates": coordinates}


def graphhopper_line_no_service(
    coords: list[tuple[float, float]],
    api_key: str,
    base: str,
    profile: str,
) -> dict:
    if len(coords) > MAX_WAYPOINTS:
        raise ValueError(f"Use at most {MAX_WAYPOINTS} waypoints per request")
    body = {
        "points": [[lon, lat] for lon, lat in coords],
        "profile": profile,
        "instructions": False,
        "points_encoded": False,
        "ch.disable": True,
        "custom_model": NO_SERVICE_MODEL,
    }
    q = urllib.parse.urlencode({"key": api_key})
    url = f"{base.rstrip('/')}/route?{q}"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SG-BUS-DATA-stops_to_road_lines/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GraphHopper HTTP {e.code}: {err_body[:500]}") from e

    paths = data.get("paths") or data.get("routes")
    if not paths:
        msg = data.get("message") or data.get("hints") or json.dumps(data)[:400]
        raise RuntimeError(f"GraphHopper: no paths — {msg}")
    return _graphhopper_points_to_linestring(paths[0]["points"])


def parse_args() -> tuple[list[str], bool]:
    raw = sys.argv[1:]
    allow_service = "--allow-service" in raw
    positional = [a for a in raw if not a.startswith("-")]
    return positional, allow_service


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    positional, allow_service = parse_args()

    svc_path = Path(positional[0]) if len(positional) > 0 else root / "services" / "767.json"
    stops_path = Path(positional[1]) if len(positional) > 1 else root / "data" / "bus-stops.json"
    out_path = (
        Path(positional[2])
        if len(positional) > 2
        else root / "output" / svc_path.stem / f"{svc_path.stem}-roads.geojson"
    )

    gh_key = os.environ.get("GRAPHHOPPER_API_KEY", "").strip()
    gh_base = os.environ.get("GRAPHHOPPER_URL", GRAPHHOPPER_DEFAULT).strip() or GRAPHHOPPER_DEFAULT
    profile_gh = os.environ.get("GRAPHHOPPER_PROFILE", "car").strip() or "car"
    overpass_url = os.environ.get("OVERPASS_URL", OVERPASS_DEFAULT).strip() or OVERPASS_DEFAULT

    osrm_base = OSRM_DEFAULT
    profile_osrm = "driving"
    if allow_service:
        if len(positional) > 3:
            osrm_base = positional[3]
        if len(positional) > 4:
            p = positional[4]
            profile_osrm = "driving" if p == "car" else p

    exclude_service = not allow_service
    use_graphhopper = exclude_service and bool(gh_key)

    legs, missing = load_stop_coords(svc_path, stops_path)
    if missing:
        for direction, code in missing:
            print(f"Missing stop {code} ({direction})", file=sys.stderr)

    features = []
    for direction, coords in legs:
        try:
            if allow_service:
                geom = osrm_line(coords, osrm_base, profile_osrm)
                router = "osrm"
                props_profile = profile_osrm
                snap_method = "none"
            elif use_graphhopper:
                geom = graphhopper_line_no_service(coords, gh_key, gh_base, profile_gh)
                router = "graphhopper"
                props_profile = profile_gh
                snap_method = "graphhopper_custom_model"
            else:
                snapped = snap_leg_coords(coords, overpass_url)
                if len(snapped) < 2:
                    raise RuntimeError("After snapping, fewer than 2 distinct waypoints remain.")
                geom = osrm_line(snapped, osrm_base, profile_osrm)
                router = "osrm"
                props_profile = profile_osrm
                snap_method = "overpass_non_service"
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, ValueError) as e:
            print(f"Routing failed for '{direction}': {e}", file=sys.stderr)
            sys.exit(1)
        features.append(
            {
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "direction": direction,
                    "profile": props_profile,
                    "waypoints": len(coords),
                    "router": router,
                    "exclude_service": exclude_service,
                    "snap_method": snap_method,
                },
            }
        )

    fc = {"type": "FeatureCollection", "features": features}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(features)} LineStrings)")


if __name__ == "__main__":
    main()
