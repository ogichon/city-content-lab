#!/usr/bin/env python3
"""CCL — stitch a georeferenced GSI aerial-photo basemap for a Blender scene.

The plateau-tokyo-station scenes are EPSG:6677 meters recentered by a
constant offset C (scene = 6677 - C). Given C and a scene-coord extent,
download GSI seamlessphoto tiles, stitch, crop to the exact extent, and
optionally write a pale (washed) variant plus an edge-faded variant whose
border blends into a flat color so the sheet sits naturally on the plain
ground plane. Requires: pyproj, Pillow, numpy.

Skytree scene: C = (-2455.1, -31890.2) (tower anchor lat 35.71006,
lon 139.81072 verified against the source README), extent -1850 1850 -1550 1550.

Usage:
  python3 make_basemap.py --cx -2455.1 --cy -31890.2 \
      --extent -1850 1850 -1550 1550 --zoom 17 --out assets/basemap/skytree.jpg
Source: 国土地理院タイル (seamlessphoto) — https://maps.gsi.go.jp/development/ichiran.html
"""
import argparse, io, math, urllib.request
from PIL import Image, ImageEnhance
import numpy as np
import pyproj

ap = argparse.ArgumentParser()
ap.add_argument('--cx', type=float, required=True)
ap.add_argument('--cy', type=float, required=True)
ap.add_argument('--extent', type=float, nargs=4, required=True, metavar=('XMIN', 'XMAX', 'YMIN', 'YMAX'))
ap.add_argument('--zoom', type=int, default=17)
ap.add_argument('--out', required=True)
ap.add_argument('--pale', action='store_true', help='also write <out>-pale.jpg and <out>-pale-faded.jpg')
a = ap.parse_args()

inv = pyproj.Transformer.from_crs('EPSG:6677', 'EPSG:4326', always_xy=True)
xmin, xmax, ymin, ymax = a.extent
lon_min, lat_min = inv.transform(xmin + a.cx, ymin + a.cy)
lon_max, lat_max = inv.transform(xmax + a.cx, ymax + a.cy)

def tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    r = math.radians(lat)
    y = (1.0 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2.0 * n
    return x, y

x0f, y1f = tile_xy(lon_min, lat_min, a.zoom)
x1f, y0f = tile_xy(lon_max, lat_max, a.zoom)
tx0, tx1, ty0, ty1 = int(x0f), int(x1f), int(y0f), int(y1f)
canvas = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
for tx in range(tx0, tx1 + 1):
    for ty in range(ty0, ty1 + 1):
        url = f'https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{a.zoom}/{tx}/{ty}.jpg'
        req = urllib.request.Request(url, headers={'User-Agent': 'CCL-research/1.0'})
        tile = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=20).read()))
        canvas.paste(tile, ((tx - tx0) * 256, (ty - ty0) * 256))
img = canvas.crop((int((x0f - tx0) * 256), int((y0f - ty0) * 256),
                   int((x1f - tx0) * 256), int((y1f - ty0) * 256)))
img.save(a.out, quality=88)
print('CCL: basemap', a.out, img.size)

if a.pale:
    pale = ImageEnhance.Color(img).enhance(0.22)
    pale = ImageEnhance.Brightness(pale).enhance(1.28)
    pale = ImageEnhance.Contrast(pale).enhance(0.82)
    pout = a.out.replace('.jpg', '-pale.jpg')
    pale.save(pout, quality=88)
    arr = np.asarray(pale).astype(np.float32)
    h, w, _ = arr.shape
    edge = np.array([203, 208, 213], dtype=np.float32)
    def ramp(n, f):
        r = np.ones(n, dtype=np.float32); r[:f] = np.linspace(0, 1, f); r[-f:] = np.linspace(1, 0, f)
        return r
    alpha = np.minimum(ramp(w, int(w * 0.07))[None, :, None], ramp(h, int(h * 0.07))[:, None, None]) ** 1.5
    faded = Image.fromarray((arr * alpha + edge * (1 - alpha)).astype(np.uint8))
    fout = a.out.replace('.jpg', '-pale-faded.jpg')
    faded.save(fout, quality=88)
    print('CCL: pale + faded written')
