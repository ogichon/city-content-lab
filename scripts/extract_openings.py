#!/usr/bin/env python3
"""CCL EXP-025 — extract REAL opening surfaces (bldg:Window / bldg:Door)
from PLATEAU CityGML into a separate OBJ, in the exact local frame of
scripts/convert_citygml.py (EPSG:6697 -> EPSG:6677, anchor-subtracted,
east/north/height metres, Z-up).

Method (data-driven, no hand-picking): stream the GML one top-level
feature at a time; inside each Building/BuildingPart, every descendant
element whose local name is "Window" or "Door" (CityGML building module)
is an opening. All gml:Polygon geometry under it (local XLinks resolved
within the feature, deduplicated by polygon id, same traversal as the
converter) is exported. Each polygon is nudged 0.03 m along its own
normal, oriented away from the building bbox centre, purely to avoid
z-fighting with the wall surface it sits in — placement, size and shape
are the data's, untouched.

Output OBJ: one object per opening, named  op_<opening gml:id>, with a
group line  g <building gml:id>  so the scene script can attribute it.
A JSON report records per-building window/door/polygon counts.

Usage:
  PYTHONPATH=~/workspace/pylibs python3 scripts/extract_openings.py \
      --gml-dir data/yokohama2024/gml-mm \
      --anchor 35.4546 139.6311 \
      --out data/yokohama2024/yokohama-mm-openings.obj \
      --report data/yokohama2024/yokohama-mm-openings-report.json
"""
import argparse, json, math, sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path.home() / "workspace" / "pylibs"))
from pyproj import Transformer

XLINK = "{http://www.w3.org/1999/xlink}href"


def split_tag(tag):
    if tag.startswith("{"):
        return tag[1:].split("}", 1)
    return "", tag


def is_gml(element, name):
    uri, local = split_tag(element.tag)
    return local == name and uri.startswith("http://www.opengis.net/gml")


def element_id(element):
    return next((v for k, v in element.attrib.items()
                 if split_tag(k)[1] == "id" and "opengis.net/gml" in split_tag(k)[0]), None)


def is_feature(element):
    uri, name = split_tag(element.tag)
    return name in ("Building", "BuildingPart") and "/citygml/building/" in uri


def is_opening(element):
    uri, name = split_tag(element.tag)
    return name in ("Window", "Door") and "/citygml/building/" in uri


def polygons_under(root, index):
    """Same traversal contract as convert_citygml.polygons()."""
    seen, active = set(), set()

    def visit(element):
        if id(element) in active:
            raise ValueError("cyclic geometry XLink")
        active.add(id(element))
        try:
            if is_gml(element, "Polygon"):
                key = element_id(element) or id(element)
                if key not in seen:
                    seen.add(key)
                    yield element
                return
            href = element.get(XLINK)
            if href:
                if not href.startswith("#") or href[1:] not in index:
                    raise ValueError(f"unresolved geometry XLink: {href}")
                yield from visit(index[href[1:]])
            for child in element:
                yield from visit(child)
        finally:
            active.remove(id(element))

    yield from visit(root)


def ring_points(polygon, transformer, anchor_xy):
    exterior = next((e for e in polygon if is_gml(e, "exterior")), None)
    if exterior is None:
        return None
    pos = next((e for e in exterior.iter() if is_gml(e, "posList")), None)
    if pos is None or not pos.text:
        return None
    values = [float(v) for v in pos.text.split()]
    if len(values) % 3:
        return None
    coords = [tuple(values[i:i + 3]) for i in range(0, len(values), 3)]
    if coords and coords[-1] == coords[0]:
        coords.pop()
    if len(coords) < 3:
        return None
    pts = []
    for lat, lon, h in coords:
        east, north = transformer.transform(lon, lat, errcheck=True)
        pts.append((east - anchor_xy[0], north - anchor_xy[1], h))
    return pts


def polygon_normal(pts):
    o = pts[0]
    for i in range(1, len(pts) - 1):
        a = [pts[i][j] - o[j] for j in range(3)]
        b = [pts[i + 1][j] - o[j] for j in range(3)]
        n = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
        ln = math.sqrt(sum(v * v for v in n))
        if ln > 1e-10:
            return tuple(v / ln for v in n)
    return (0.0, 0.0, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml-dir", required=True)
    ap.add_argument("--anchor", type=float, nargs=2, required=True, metavar=("LAT", "LON"))
    ap.add_argument("--target-crs", type=int, default=6677)
    ap.add_argument("--offset", type=float, default=0.03)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    transformer = Transformer.from_crs(6697, args.target_crs, always_xy=True)
    anchor_xy = transformer.transform(args.anchor[1], args.anchor[0], errcheck=True)

    files = sorted(Path(args.gml_dir).rglob("*.gml"))
    report = {"files": [], "buildings": {}, "totals": {"windows": 0, "doors": 0, "polygons": 0, "openings": 0}}
    out_lines = ["# CityGML opening surfaces (bldg:Window / bldg:Door); local east north height in metres, Z-up"]
    v_offset = 0

    for path in files:
        file_stats = {"file": str(path), "features_with_openings": 0}
        context = ET.iterparse(str(path), events=("end",))
        for _event, elem in context:
            if not is_feature(elem):
                continue
            bid = element_id(elem) or "unknown"
            # per-feature id index for local XLink resolution
            index = {}
            for e in elem.iter():
                eid = element_id(e)
                if eid:
                    index[eid] = e
            openings = [e for e in elem.iter() if is_opening(e)]
            if openings:
                # building bbox centre (from all its transformed ring points we touch)
                polys = []
                counts = {"Window": 0, "Door": 0}
                for op in openings:
                    kind = split_tag(op.tag)[1]
                    counts[kind] += 1
                    oid = element_id(op) or f"op_{id(op)}"
                    for poly in polygons_under(op, index):
                        pts = ring_points(poly, transformer, anchor_xy)
                        if pts:
                            polys.append((oid, kind, pts))
                if polys:
                    allpts = [p for _o, _k, pts in polys for p in pts]
                    centre = tuple(sum(p[j] for p in allpts) / len(allpts) for j in range(3))
                    b = report["buildings"].setdefault(bid, {"windows": 0, "doors": 0, "polygons": 0,
                                                             "bbox_min": [1e18] * 3, "bbox_max": [-1e18] * 3})
                    b["windows"] += counts["Window"]
                    b["doors"] += counts["Door"]
                    file_stats["features_with_openings"] += 1
                    # group polygons by opening element for OBJ objects
                    by_opening = {}
                    for oid, kind, pts in polys:
                        by_opening.setdefault((oid, kind), []).append(pts)
                    for (oid, kind), plist in by_opening.items():
                        out_lines.append(f"o op_{oid}")
                        out_lines.append(f"g {bid}")
                        local = []
                        for pts in plist:
                            n = polygon_normal(pts)
                            pc = tuple(sum(p[j] for p in pts) / len(pts) for j in range(3))
                            away = sum(n[j] * (pc[j] - centre[j]) for j in range(3))
                            sgn = 1.0 if away >= 0 else -1.0
                            off = tuple(sgn * args.offset * n[j] for j in range(3))
                            start = v_offset + len(local)
                            for p in pts:
                                q = tuple(p[j] + off[j] for j in range(3))
                                local.append(q)
                                out_lines.append("v {:.9f} {:.9f} {:.9f}".format(*q))
                                for j in range(3):
                                    b["bbox_min"][j] = min(b["bbox_min"][j], q[j])
                                    b["bbox_max"][j] = max(b["bbox_max"][j], q[j])
                            for i in range(1, len(pts) - 1):
                                out_lines.append(f"f {start + 1} {start + i + 1} {start + i + 2}")
                            b["polygons"] += 1
                        v_offset += len(local)
                    report["totals"]["windows"] += counts["Window"]
                    report["totals"]["doors"] += counts["Door"]
                    report["totals"]["openings"] += counts["Window"] + counts["Door"]
                    report["totals"]["polygons"] += b["polygons"] if False else sum(len(v) for v in by_opening.values())
            elem.clear()
        report["files"].append(file_stats)

    Path(args.out).write_text("\n".join(out_lines) + "\n")
    for b in report["buildings"].values():
        b["height_m"] = round(b["bbox_max"][2] - b["bbox_min"][2], 1)
        b["centroid"] = [round((b["bbox_min"][j] + b["bbox_max"][j]) / 2, 1) for j in range(3)]
    Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps(report["totals"], indent=1))
    for bid, b in sorted(report["buildings"].items(), key=lambda kv: -kv[1]["windows"] - kv[1]["doors"]):
        print(f"{bid}: windows={b['windows']} doors={b['doors']} polys={b['polygons']} h={b['height_m']} c={b['centroid']}")


if __name__ == "__main__":
    main()
