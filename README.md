# SG premium bus routes

Python tooling to build **GeoJSON** for Singapore bus services: ordered stop codes → point layers and road-following LineStrings (OSRM / Overpass). Stop lists and outputs live in this repo; this is **project-local research data**, not an official LTA product.

## Quick start

From the project root, with **Python 3** available:

```powershell
python .\scripts\run_bus_route.py services\565.json
```

That writes per-direction GeoJSON under `output/<service>/` (e.g. `565-1.geojson`, `565-1-roads.geojson`, …). Use any `services/<number>.json` file the same way.

## Repository layout

| Path | Purpose |
|------|---------|
| `services/` | One JSON per bus service (directions + ordered stop codes). |
| `data/bus-stops.json` | Master stop list with coordinates. |
| `scripts/` | `run_bus_route.py`, `route_to_geojson.py`, `stops_to_road_lines.py`. |
| `output/<service>/` | Generated GeoJSON per service number. |

## Documentation

Full usage (separate script steps, flags, service JSON format, Git notes) is in **[USAGE.md](USAGE.md)**.
