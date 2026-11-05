# Brief — Codex I: CityGML → OBJ converter for the Expo 2025 dataset

Worktree: ~/workspace/ccl-wt-expo. Read AGENTS.md and docs/experiments/EXP-007.md first. Do NOT commit (Muse commits).

## Context
PLATEAU Expo dataset CityGML zip is at ~/workspace/city-content-lab/data/expo2025/citygml.zip (357MB; PLATEAU v4 packaging, udx/bldg/*.gml expected — inspect the actual layout first and adapt). A sample GML extracted for you may exist at /tmp/expo_sample.gml — check both.

## Deliverable: `scripts/convert_citygml.py` (stdlib + pyproj only)
- Args: --zip PATH (or --gml-dir PATH), --out PATH.obj, --anchor LAT LON (default: Expo venue centre 34.6500 135.3830 — verify against data bbox and report), --report PATH.json.
- Stream-parse each GML with xml.etree.ElementTree.iterparse (memory-safe). Namespaces: discover from the file, do not hardcode a single PLATEAU version's URIs beyond the standard bldg/gml/core prefixes.
- For every bldg:Building (and BuildingPart as separate object), brid:Bridge, and frn:CityFurniture feature — the Grand Ring may be modelled as a bridge or furniture, not a building. Name OBJ groups as <type>_<gml:id>, pick the HIGHEST available LOD geometry in order lod4 > lod3 > lod2 > lod1, whether expressed as Solid or MultiSurface/CompositeSurface under the building or its boundedBy surfaces. Extract every gml:Polygon's exterior ring posList (ignore interior rings but count them). Fan-triangulate each ring (assume planar/convex-enough patches; count non-planar risk silently, do not crash).
- Source CRS is EPSG:6699 (lat, lon, height). Convert each vertex: pyproj EPSG:6699 → EPSG:6674 (Osaka plane zone VI) → subtract the anchor's 6674 coords → local (east, north, height) metres.
- Write ONE OBJ: per-building `o` groups named by gml:id, vertices as (east, north, height) [Z-up data; the Blender side imports with up_axis='Z'], faces 1-indexed, no materials/textures.
- Report JSON: files parsed, buildings written, per-LOD counts, skipped feature types, vertex/triangle totals, local bbox, anchor used.
- Robustness: a malformed building must not abort the run — catch per-building exceptions, count them in the report.
- Verify: run the converter on the sample (or one GML from the zip), then `python3 -m py_compile`, and print the report contents. State exactly what you verified and what remains unverified (full-zip run is Muse's).
Print a summary at the end.
