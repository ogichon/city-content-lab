#!/usr/bin/env python3
"""Stitch the Expo dataset's ortho GeoTIFF tiles into one basemap image in
the converter's local coordinates (EPSG:6674 metres minus the Expo anchor).
.tfw files are in degrees (EPSG:4326 grid); corners are projected properly.

Usage: python3 make_expo_ortho.py --zip data/expo2025/geotiff.zip \
           --out assets/basemap/expo-ortho.jpg
"""
import argparse, io, zipfile
import numpy as np
from PIL import Image
from pyproj import Transformer

Image.MAX_IMAGE_PIXELS = None
ANCHOR_E, ANCHOR_N = -56558.314384931065, -149589.72447951962  # from expo-report.json
EXTENT = (-850.0, 860.0, -760.0, 640.0)  # x0, x1, y0, y1 local metres
SCALE = 0.5  # metres per pixel

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    tf = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)

    def to_local(lon, lat):
        e, n = tf.transform(lon, lat)
        return e - ANCHOR_E, n - ANCHOR_N

    x0, x1, y0, y1 = EXTENT
    W = int((x1 - x0) / SCALE); H = int((y1 - y0) / SCALE)
    canvas = Image.new("RGB", (W, H), (168, 175, 180))
    zf = zipfile.ZipFile(args.zip)
    names = [n for n in zf.namelist() if n.endswith(".tif")]
    print(f"{len(names)} tiles")
    for name in sorted(names):
        base = name[:-4]
        tfw = [float(v) for v in zf.read(base + ".tfw").decode().split()]
        px, _, _, py, lon0, lat0 = tfw  # NW corner, degrees
        img = Image.open(io.BytesIO(zf.read(name))).convert("RGB")
        tw, th = img.size
        # tile corners in local metres: NW, NE, SW
        nw = to_local(lon0, lat0)
        ne = to_local(lon0 + px * tw, lat0)
        sw = to_local(lon0, lat0 + py * th)
        # affine: canvas pixel (cx, cy) -> tile pixel (tx, ty)
        # canvas: cx = (lx - x0)/SCALE, cy = (y1 - ly)/SCALE
        # solve with the three corners
        A = np.array([
            [nw[0], nw[1], 1, 0, 0, 0],
            [0, 0, 0, nw[0], nw[1], 1],
            [ne[0], ne[1], 1, 0, 0, 0],
            [0, 0, 0, ne[0], ne[1], 1],
            [sw[0], sw[1], 1, 0, 0, 0],
            [0, 0, 0, sw[0], sw[1], 1],
        ], dtype=float)
        bvec = np.array([0, 0, tw, 0, 0, th], dtype=float)
        try:
            sol = np.linalg.solve(A, bvec)
        except np.linalg.LinAlgError:
            print("skip (singular)", name); continue
        m = sol  # tx = m0*lx + m1*ly + m2 ; ty = m3*lx + m4*ly + m5
        # express in canvas pixel coords: lx = x0 + SCALE*cx ; ly = y1 - SCALE*cy
        a = m[0] * SCALE; b_ = -m[1] * SCALE; c = m[0] * x0 + m[1] * y1 + m[2]
        d = m[3] * SCALE; e = -m[4] * SCALE; f = m[3] * x0 + m[4] * y1 + m[5]
        warped = img.transform((W, H), Image.AFFINE, (a, b_, c, d, e, f), resample=Image.BILINEAR)
        mask = Image.new("L", (tw, th), 255).transform((W, H), Image.AFFINE, (a, b_, c, d, e, f), resample=Image.NEAREST)
        canvas.paste(warped, (0, 0), mask)
        print("placed", base.split("/")[-1], "NW local:", tuple(round(v) for v in nw))
    canvas.save(args.out, quality=90)
    print("saved", args.out, canvas.size)

if __name__ == "__main__":
    main()
