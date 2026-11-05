#!/usr/bin/env python3
"""Extract selected entries from a huge remote ZIP via HTTP range requests.

Reads a TSV index (name, method, compressed_size, uncompressed_size,
local_header_offset) produced from the ZIP central directory, fetches only
each entry's local header + compressed data, inflates, and writes the file.

Usage:
  python3 extract_zip_ranges.py --url https://.../big.zip \
      --index data/takeshiba/bldg_index.tsv --out-dir data/takeshiba/gml
"""
import argparse, hashlib, struct, sys, urllib.request, zlib
from pathlib import Path

def fetch_range(url, start, end):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for line in Path(args.index).read_text().splitlines():
        if not line.strip():
            continue
        name, method, csize, usize, offset = line.split("\t")
        rows.append((name, int(method), int(csize), int(usize), int(offset)))
    print(f"{len(rows)} entries")
    for name, method, csize, usize, offset in rows:
        base = Path(name).name
        dest = out_dir / base
        if dest.exists() and dest.stat().st_size == usize:
            print("skip (done)", base)
            continue
        hdr = fetch_range(args.url, offset, offset + 30 + 1024)
        sig, _, _, _, _, _, _, _, _, fnlen, extralen = struct.unpack("<IHHHHHIIIHH", hdr[:30])
        assert sig == 0x04034B50, f"bad local header for {name}"
        data_start = offset + 30 + fnlen + extralen
        blob = fetch_range(args.url, data_start, data_start + csize - 1)
        assert len(blob) == csize, f"{base}: got {len(blob)} of {csize} compressed bytes"
        if method == 8:
            data = zlib.decompress(blob, wbits=-15)
        elif method == 0:
            data = blob
        else:
            raise SystemExit(f"unsupported method {method} for {name}")
        assert len(data) == usize, f"{base}: {len(data)} != expected {usize}"
        dest.write_bytes(data)
        print(f"ok {base}  md5={hashlib.md5(data).hexdigest()}  {usize} bytes", flush=True)
    print("all done")

if __name__ == "__main__":
    main()
