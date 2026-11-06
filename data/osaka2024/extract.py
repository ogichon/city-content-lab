import json, sys, urllib.request, zlib, struct, os
U = "https://assets.cms.plateau.reearth.io/assets/40/a85f8e-049c-4b3f-a97b-4a217df787df/27100_osaka-shi_city_2024_citygml_1_op.zip"
BASE = os.path.dirname(os.path.abspath(__file__))
idx = {e["name"]: e for e in json.load(open(os.path.join(BASE, "index.json")))}
os.makedirs(os.path.join(BASE, "gml"), exist_ok=True)
for name in sys.argv[1:]:
    e = idx[name]
    lho, csize, method = e["local_header_offset"], e["csize"], e["method"]
    req = urllib.request.Request(U, headers={"Range": f"bytes={lho}-{lho + 30 + 65536 + csize - 1}"})
    buf = urllib.request.urlopen(req).read()
    nlen, elen = struct.unpack_from("<HH", buf, 26)
    raw = buf[30 + nlen + elen: 30 + nlen + elen + csize]
    data = zlib.decompress(raw, -15) if method == 8 else raw
    out = os.path.join(BASE, "gml", os.path.basename(name))
    open(out, "wb").write(data)
    print(out, len(data), "ok:", len(data) == e["usize"])
