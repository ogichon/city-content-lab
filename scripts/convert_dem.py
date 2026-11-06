#!/usr/bin/env python3
"""CCL — PLATEAU DEM (TINRelief) to OBJ in the same local frame as
convert_citygml.py output. Streams gml:trianglePatches posLists.
Usage: convert_dem.py --gml a.gml [b.gml ...] --anchor-lat 34.65 \
    --anchor-lon 135.383 --source-crs EPSG:6697 --target-crs EPSG:6674 \
    --out terrain.obj --report report.json
"""
import argparse, json, re, sys
import xml.etree.ElementTree as ET
from pyproj import Transformer

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", nargs="+", required=True)
    ap.add_argument("--anchor-lat", type=float, required=True)
    ap.add_argument("--anchor-lon", type=float, required=True)
    ap.add_argument("--source-crs", default="EPSG:6697")
    ap.add_argument("--target-crs", default="EPSG:6674")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    to_plane = Transformer.from_crs(a.source_crs, a.target_crs, always_xy=True)
    ax, ay = to_plane.transform(a.anchor_lon, a.anchor_lat)
    verts, tris = [], []
    zmin, zmax = float("inf"), float("-inf")
    n_patch = 0
    POSLIST = "{http://www.opengis.net/gml}posList"
    import math
    dropped = 0
    for path in a.gml:
        for _ev, el in ET.iterparse(path, events=("end",)):
            if el.tag == POSLIST:
                vals = [float(v) for v in el.text.split()]
                # Source axis order is (lat, lon, h) per EPSG:6697 — the
                # same convention convert_citygml.py uses. Each Triangle
                # posList is a closed ring of 4 points (12 values); the
                # triangle is the first 3.
                pts = [(vals[i], vals[i + 1], vals[i + 2])
                       for i in range(0, len(vals) - 2, 3)]
                if len(pts) == 4:
                    pts = pts[:3]
                if len(pts) != 3:
                    dropped += 1
                    el.clear()
                    continue
                tri = []
                ok = True
                for (lat, lon, z) in pts:
                    ex, ny = to_plane.transform(lon, lat)
                    if not (math.isfinite(ex) and math.isfinite(ny) and math.isfinite(z)):
                        ok = False
                        break
                    verts.append((ex - ax, ny - ay, z))
                    zmin, zmax = min(zmin, z), max(zmax, z)
                    tri.append(len(verts))
                if ok:
                    tris.append(tuple(tri))
                    n_patch += 1
                else:
                    dropped += 1
                    del verts[-len(tri):]
                el.clear()
    if dropped:
        print(f"CCL DEM: dropped {dropped} non-triangle/non-finite patches", flush=True)
    with open(a.out, "w") as f:
        f.write("# CCL DEM terrain\n")
        for v in verts:
            f.write(f"v {v[0]:.3f} {v[1]:.3f} {v[2]:.3f}\n")
        for t in tris:
            f.write(f"f {t[0]} {t[1]} {t[2]}\n")
    rep = {"patches": n_patch, "vertices": len(verts), "triangles": len(tris),
           "z_min": zmin, "z_max": zmax, "anchor_plane": [ax, ay]}
    print(json.dumps(rep, ensure_ascii=False))
    if a.report:
        json.dump(rep, open(a.report, "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
