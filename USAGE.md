# SG premium bus routes

Build GeoJSON for Singapore bus services: ordered stops → point layers and OSRM/Overpass road LineStrings. Data is project-local (not an official LTA product).

Run commands from the **project root** (`sg-premium-bus-routes`), unless you use absolute paths.

## Layout

| Folder | Contents |
|--------|----------|
| `services/` | One JSON per bus service (directions + ordered stop codes). |
| `data/bus-stops.json` | Master stop list with coordinates. |
| `scripts/` | Python tools. |
| `output/<service>/` | Generated GeoJSON for that service number. |

## One-shot: points + road lines

Runs `route_to_geojson.py`, then `stops_to_road_lines.py`, and writes **per-direction** GeoJSON files under `output/<service>/` (no combined “all directions” files).

```powershell
python .\scripts\run_bus_route.py services/565.json
```

Other examples:

```powershell
python .\scripts\run_bus_route.py services\722.json
python .\scripts\run_bus_route.py "C:\path\to\960.json" --bus-stops "C:\path\to\bus-stops.json"
```

Default stops database: `data/bus-stops.json`. Override with `--bus-stops`.

### Faster roads step (skip Overpass snap)

By default, `stops_to_road_lines.py` uses Overpass + OSRM (slow; snaps stops to non-service OSM ways first). To use **OSRM only** (much faster; may still use `highway=service` links where OSRM snaps):

```powershell
python .\scripts\run_bus_route.py services/565.json -- --allow-service
```

Anything **after `--`** is passed only to `stops_to_road_lines.py`.

### Note

The default roads step uses the public **Overpass** service (can be slow or return HTTP 429) and then **OSRM** with `continue_straight=true` on the route request. For a faster run without the Overpass snap, use `-- --allow-service` as above. You can set **`OVERPASS_URL`** to another Overpass endpoint. With **`GRAPHHOPPER_API_KEY`** set, the default path uses GraphHopper instead of Overpass+OSRM. Final lines match **OSM + the router**; adjust OSM or self-host a router if a corridor is wrong.

### Outputs

Files follow the **order of directions in the service JSON** (1-based index `i`):

- `{service}-i.geojson` — stop points for that direction  
- `{service}-i-roads.geojson` — road LineString for that direction (empty `features` if that direction has fewer than two stops with coordinates)  

The third path argument to `route_to_geojson.py` / `stops_to_road_lines.py` only selects the **output folder** (the path’s parent directory); the filename is ignored.

---

## Run scripts separately

From project root, pass explicit paths (recommended):

**Points only**

```powershell
python .\scripts\route_to_geojson.py services\565.json data\bus-stops.json output\565\565.geojson
```

**Road lines only**

```powershell
python .\scripts\stops_to_road_lines.py services\565.json data\bus-stops.json output\565\565-roads.geojson
```

If you omit arguments, defaults assume **`services/767.json`**, **`data/bus-stops.json`**, and outputs under **`output/767/`** (see inside each script).

---

## Service JSON shape

Each file is a JSON array of directions:

```json
[
  {
    "name": "Direction label",
    "stops": ["-Z665", "-Z805", "..."]
  }
]
```

Stop codes must match `"name"` entries in `data/bus-stops.json`.

---

## Git (this repo is initialized on `main`)

The project root is already a Git repository with an initial commit.

**Push to a new empty GitHub repo**

1. Create a repository on GitHub (no README/license if you want a clean push).
2. From the project root:

```powershell
cd ".\Desktop\My Projects\sg-premium-bus-routes"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Use SSH instead if you prefer: `git@github.com:YOUR_USERNAME/YOUR_REPO.git`.

**Install [GitHub CLI](https://cli.github.com/)** (`gh`) if you want one-command create + push after `gh auth login`:

```powershell
gh repo create sg-premium-bus-routes --public --source=. --remote=origin --push
```
