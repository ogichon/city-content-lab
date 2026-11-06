#!/usr/bin/env python3
"""Stream CityGML features into a single Z-up, metre-based OBJ.

Only stdlib and pyproj are required. Geometry is retained for one top-level
feature at a time; local XLinks can refer to geometry anywhere in that feature.
With --textures, an initial streaming pass indexes appearance targets on disk,
including CityModel-level appearanceMember records. Images are copied beside the
OBJ with UVs as-is (no vertical flip: CityGML texture coordinates already
match OBJ sampling for these atlases — flipping v moved samples into the
black padding of the atlas images and blacked out whole roofs; verified by
A/B render, EXP-014). Texture statistics count exported
surfaces and distinct successfully copied / missing images.
Interior rings are counted but omitted; fan triangulation assumes convex patches.
Cross-feature/external geometry XLinks are reported as feature errors.

Example:
    python3 scripts/convert_citygml.py --zip citygml.zip --out expo.obj \
        --report expo.json

CRS correction to the brief: EPSG:6699 is a vertical coordinate operation,
not a source CRS. The Expo files declare EPSG:6697. Their horizontal coordinates
are projected to EPSG:6674; heights remain unchanged. The report records this.
A successful exit may include skipped malformed features; inspect feature_errors.
Malformed XML is a file error and results in a nonzero exit with a partial OBJ.

"""
import argparse
from contextlib import contextmanager, ExitStack
import json
import math
import posixpath
import shutil
import sqlite3
import tempfile
from urllib.parse import unquote, urlsplit
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

from pyproj import Transformer


FEATURES = {('building', 'Building'), ('building', 'BuildingPart'),
            ('bridge', 'Bridge'), ('cityfurniture', 'CityFurniture')}
LOD = re.compile(r'^lod([1-4])(?:Solid|MultiSurface|CompositeSurface|Geometry)$')


def split_tag(tag):
    if tag.startswith('{'):
        return tag[1:].split('}', 1)
    return '', tag


def feature_type(element):
    uri, name = split_tag(element.tag)
    if any((module, name) in FEATURES and f'/citygml/{module}/' in uri
           for module, _ in FEATURES):
        return name
    return None


def gml(element, name):
    uri, local = split_tag(element.tag)
    return local == name and (uri == 'http://www.opengis.net/gml' or
                             uri.startswith('http://www.opengis.net/gml/'))


def element_id(element):
    return next((v for k, v in element.attrib.items()
                 if split_tag(k)[1] == 'id' and 'opengis.net/gml' in split_tag(k)[0]), None)


def owned_elements(feature):
    """Exclude nested features, whose geometry belongs to separate OBJ objects."""
    yield feature
    for child in feature:
        if not feature_type(child):
            yield from owned_elements(child)


def polygons(roots, index):
    seen, active = set(), set()

    def visit(element):
        if id(element) in active:
            raise ValueError('cyclic geometry XLink')
        if feature_type(element):
            return
        active.add(id(element))
        try:
            if gml(element, 'Polygon'):
                key = element_id(element) or id(element)
                if key not in seen:
                    seen.add(key)
                    yield element
                return
            href = element.get('{http://www.w3.org/1999/xlink}href')
            if href:
                if not href.startswith('#') or href[1:] not in index:
                    raise ValueError(f'unresolved geometry XLink: {href}')
                yield from visit(index[href[1:]])
            for child in element:
                yield from visit(child)
        finally:
            active.remove(id(element))

    for root in roots:
        yield from visit(root)


def nonplanar(points):
    origin = points[0]
    for i in range(1, len(points) - 1):
        a = [points[i][j] - origin[j] for j in range(3)]
        b = [points[i + 1][j] - origin[j] for j in range(3)]
        n = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        length = math.sqrt(sum(v*v for v in n))
        if length > 1e-10:
            return any(abs(sum(n[j]*(p[j]-origin[j]) for j in range(3))) / length > .01
                       for p in points)
    return False


def appearance(element, name):
    uri, local = split_tag(element.tag)
    return local == name and '/citygml/appearance/' in uri


@contextmanager
def appearance_index(opener):
    """Expo stores appearanceMember at CityModel scope, after the features.

    First stream only texture targets into a temporary disk index; the second
    pass still buffers just one feature. Neither XML pass retains the file tree.
    """
    with tempfile.TemporaryDirectory(prefix='citygml-appearance-') as directory:
        db = sqlite3.connect(str(Path(directory) / 'targets.sqlite'))
        try:
            db.execute('CREATE TABLE targets (identity TEXT PRIMARY KEY, image TEXT, xml TEXT)')
            with opener() as stream:
                stack = []
                target_depth = 0
                image = None
                for event, element in ET.iterparse(stream, events=('start', 'end')):
                    if event == 'start':
                        stack.append(element)
                        if appearance(element, 'ParameterizedTexture'):
                            image = None
                        if appearance(element, 'target'):
                            target_depth += 1
                        continue
                    if appearance(element, 'imageURI'):
                        image = (element.text or '').strip()
                    if appearance(element, 'target'):
                        if image:
                            db.execute('INSERT OR REPLACE INTO targets VALUES (?, ?, ?)',
                                       (element.get('uri', '').lstrip('#'), image,
                                        ET.tostring(element, encoding='unicode')))
                        target_depth -= 1
                    if not target_depth:
                        element.clear()
                        if len(stack) > 1:
                            stack[-2].remove(element)
                    stack.pop()
            db.commit()
            yield db
        finally:
            db.close()


def texture_bindings(index, database):
    """Resolve polygon and aggregate targets using this feature's geometry only."""
    bindings = {}
    identities = list(index)
    for start in range(0, len(identities), 500):
        chunk = identities[start:start+500]
        rows = database.execute('SELECT identity, image, xml FROM targets WHERE identity IN ('
                                + ','.join('?' for _ in chunk) + ')', chunk)
        for identity, image, xml in rows:
            target = ET.fromstring(xml)
            rings = {}
            for uv in target.iter():
                if appearance(uv, 'textureCoordinates') and uv.text:
                    values = [float(v) for v in uv.text.split()]
                    if len(values) % 2 or not all(math.isfinite(v) for v in values):
                        raise ValueError('invalid texture coordinates')
                    rings[uv.get('ring', '').lstrip('#')] = list(zip(values[::2], values[1::2]))
            for polygon in polygons([index[identity]], index):
                bindings[id(polygon)] = (image, rings)
    return bindings


class TextureWriter:
    """Copy each referenced image once; material/image names cannot escape output."""
    def __init__(self, args, stack, report):
        self.folder = args.out.with_name(args.out.stem + '_textures')
        self.mtl = stack.enter_context(args.out.with_suffix('.mtl').open('w', encoding='utf-8'))
        self.mtl.write('newmtl default\nKd 0.8 0.8 0.8\n\n')
        self.archive = stack.enter_context(zipfile.ZipFile(args.zip)) if args.zip else None
        self.materials = {}
        self.report = report
        self.uv_count = 0
        self.current = None

    def material(self, filename, uri):
        parsed = urlsplit(uri)
        path = unquote(parsed.path).replace('\\', '/')
        if self.archive:
            key = posixpath.normpath(posixpath.join(posixpath.dirname(filename), path))
        else:
            key = str((Path(filename).parent / path).resolve())
        if key in self.materials:
            return self.materials[key]
        name = f'texture_{len(self.materials) + 1}'
        suffix = Path(path).suffix
        if not re.fullmatch(r'\.[A-Za-z0-9]+', suffix):
            suffix = '.img'
        dest = self.folder / (name + suffix)
        try:
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                raise FileNotFoundError(uri)
            stream = self.archive.open(key) if self.archive else Path(key).open('rb')
            with stream:
                self.folder.mkdir(parents=True, exist_ok=True)
                with dest.open('wb') as output:
                    shutil.copyfileobj(stream, output)
        except (FileNotFoundError, KeyError, IsADirectoryError):
            self.materials[key] = None
            self.report['missing_images'] += 1
            return None
        self.materials[key] = name
        self.report['textures_copied'] += 1
        self.mtl.write(f'newmtl {name}\nKd 1 1 1\nmap_Kd {self.folder.name}/{dest.name}\n\n')
        return name

    def faces(self, obj, surface_data, offset, filename):
        for start, count, binding in surface_data:
            material, uv_start = None, None
            if binding:
                image, uvs = binding
                material = self.material(filename, image)
                if material:
                    uv_start = self.uv_count + 1
                    for u, v in uvs:
                        obj.write(f'vt {u:.9f} {v:.9f}\n')
                    self.uv_count += len(uvs)
                    self.report['textured_surfaces'] += 1
            chosen = material or 'default'
            if self.current != chosen:
                obj.write(f'usemtl {chosen}\n')
                self.current = chosen
            for i in range(1, count-1):
                indices = (start, start+i, start+i+1)
                if uv_start is None:
                    obj.write('f {} {} {}\n'.format(*(offset+j for j in indices)))
                else:
                    obj.write('f ' + ' '.join(f'{offset+j}/{uv_start+j-start}' for j in indices) + '\n')


def convert_feature(feature, index, transformer, anchor_xy, textures=False, bindings=None):
    levels = {}
    for e in owned_elements(feature):
        match = LOD.match(split_tag(e.tag)[1])
        if match:
            levels.setdefault(int(match[1]), []).append(e)
    selected = None
    patches = []
    for level in sorted(levels, reverse=True):
        patches = list(polygons(levels[level], index))
        if patches:
            selected = level
            break
    if selected is None:
        return None
    vertices, faces = [], []
    surface_data = []
    holes = risks = 0
    for polygon in patches:
        holes += sum(gml(e, 'interior') for e in polygon)
        exterior = next((e for e in polygon if gml(e, 'exterior')), None)
        if exterior is None:
            raise ValueError('Polygon has no exterior')
        pos = next((e for e in exterior.iter() if gml(e, 'posList')), None)
        if pos is None or not pos.text:
            raise ValueError('exterior has no posList')
        dimension = int(pos.get('srsDimension', '3'))
        values = [float(v) for v in pos.text.split()]
        if dimension != 3 or len(values) % 3:
            raise ValueError('expected 3D posList')
        coords = [tuple(values[i:i+3]) for i in range(0, len(values), 3)]
        if coords and coords[-1] == coords[0]:
            coords.pop()
        if len(coords) < 3 or not all(math.isfinite(v) for p in coords for v in p):
            raise ValueError('invalid exterior ring')
        points = []
        for lat, lon, height in coords:
            east, north = transformer.transform(lon, lat, errcheck=True)
            points.append((east-anchor_xy[0], north-anchor_xy[1], height))
        risks += nonplanar(points)
        start = len(vertices)
        if textures:
            binding = (bindings or {}).get(id(polygon))
            resolved = None
            if binding:
                image, rings = binding
                ring = next((e for e in exterior.iter() if gml(e, 'LinearRing')), None)
                uvs = rings.get(element_id(ring)) if ring is not None else None
                if uvs is not None:
                    # A closed GML ring usually repeats its first UV as well.
                    if len(uvs) == len(coords)+1 and uvs[0] == uvs[-1]:
                        uvs = uvs[:-1]
                    if len(uvs) != len(coords):
                        raise ValueError('texture coordinate count differs from exterior ring')
                    resolved = (image, uvs)
            surface_data.append((start, len(points), resolved))
        vertices.extend(points)
        faces.extend((start, start+i, start+i+1) for i in range(1, len(points)-1))
    result = selected, vertices, faces, holes, risks
    return (*result, surface_data) if textures else result


@contextmanager
def sources(args):
    if args.zip:
        with zipfile.ZipFile(args.zip) as archive:
            names = sorted(n for n in archive.namelist() if n.lower().endswith('.gml'))
            yield [(n, lambda n=n: archive.open(n)) for n in names]
    else:
        paths = sorted(p for p in args.gml_dir.rglob('*') if p.is_file() and p.suffix.lower() == '.gml')
        yield [(str(p), lambda p=p: p.open('rb')) for p in paths]


def run(args):
    # EPSG:6699 is an operation code, not a CRS. The dataset declares
    # EPSG:6697 (JGD2011 + vertical height); project its horizontal component
    # and preserve source heights rather than applying a vertical operation.
    transformer = Transformer.from_crs(6697, args.target_crs, always_xy=True)
    lat, lon = args.anchor
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('anchor must be finite latitude/longitude in degrees')
    anchor_xy = transformer.transform(lon, lat, errcheck=True)
    report = dict(files_parsed=0, buildings_written=0, features_written=0,
                  feature_type_counts={}, per_lod_counts={str(i): 0 for i in range(1, 5)},
                  skipped_feature_types={}, features_without_geometry=0,
                  feature_errors=0, errors=[], vertices=0, triangles=0,
                  interior_rings_ignored=0, non_planar_risk_count=0, local_bbox=None,
                  anchor_used={'latitude': lat, 'longitude': lon,
                               f'epsg_{args.target_crs}_east_north': list(anchor_xy)},
                  source_crs='EPSG:6697', target_crs=f'EPSG:{args.target_crs}',
                  brief_source_crs='EPSG:6699',
                  crs_note='EPSG:6699 is a vertical operation, not a CRS; use dataset EPSG:6697. Heights are preserved.',
                  declared_crs={}, namespaces={}, source_envelopes=[],
                  file_errors=0)
    textures = getattr(args, 'textures', False)
    if textures:
        report.update(textured_surfaces=0, textures_copied=0, missing_images=0)
    low, high = [math.inf]*3, [-math.inf]*3
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack, sources(args) as inputs, args.out.open('w', encoding='utf-8') as obj:
        if not inputs:
            raise ValueError('no GML files found')
        obj.write('# CityGML; local east north height in metres, Z-up\n')
        writer = TextureWriter(args, stack, report) if textures else None
        if writer:
            obj.write(f'mtllib {args.out.with_suffix(".mtl").name}\n')
        for filename, opener in inputs:
            stack = []
            feature_depth = 0
            try:
                with ExitStack() as file_stack:
                    database = file_stack.enter_context(appearance_index(opener)) if textures else None
                    stream = file_stack.enter_context(opener())
                    for event, item in ET.iterparse(stream, events=('start-ns', 'start', 'end')):
                        if event == 'start-ns':
                            prefix, uri = item
                            report['namespaces'].setdefault(prefix, [])
                            if uri not in report['namespaces'][prefix]:
                                report['namespaces'][prefix].append(uri)
                            continue
                        if event == 'start':
                            stack.append(item)
                            if feature_type(item):
                                feature_depth += 1
                            crs = item.get('srsName')
                            if crs:
                                report['declared_crs'][crs] = report['declared_crs'].get(crs, 0)+1
                            continue
                        parent = stack[-2] if len(stack) > 1 else None
                        if gml(item, 'Envelope'):
                            corners = {split_tag(c.tag)[1]: [float(v) for v in (c.text or '').split()]
                                       for c in item if split_tag(c.tag)[1] in ('lowerCorner', 'upperCorner')}
                            report['source_envelopes'].append({'file': filename, **corners})
                        if feature_type(item):
                            feature_depth -= 1
                            if feature_depth == 0:
                                index = {element_id(e): e for e in item.iter() if element_id(e)}
                                bindings = None
                                for feature in item.iter():
                                    kind = feature_type(feature)
                                    if kind is None:
                                        continue
                                    identity = element_id(feature)
                                    try:
                                        if identity is None:
                                            raise ValueError('missing gml:id')
                                        if textures and bindings is None:
                                            bindings = texture_bindings(index, database)
                                        result = convert_feature(feature, index, transformer, anchor_xy, textures, bindings)
                                    except Exception as exc:
                                        report['feature_errors'] += 1
                                        report['errors'].append({'file': filename, 'type': kind,
                                                                 'id': identity, 'error': str(exc)})
                                        continue
                                    if result is None:
                                        report['features_without_geometry'] += 1
                                        continue
                                    level, vertices, faces, holes, risks = result[:5]
                                    name = re.sub(r'\s+', '_', identity)
                                    obj.write(f'o {name}\ng {kind}_{name}\n')
                                    for p in vertices:
                                        obj.write('v {:.9f} {:.9f} {:.9f}\n'.format(*p))
                                        for j in range(3):
                                            low[j], high[j] = min(low[j], p[j]), max(high[j], p[j])
                                    offset = report['vertices']+1
                                    if writer:
                                        writer.faces(obj, result[5], offset, filename)
                                    else:
                                        for face in faces:
                                            obj.write('f {} {} {}\n'.format(*(offset+i for i in face)))
                                    report['vertices'] += len(vertices)
                                    report['triangles'] += len(faces)
                                    report['features_written'] += 1
                                    report['buildings_written'] += kind in ('Building', 'BuildingPart')
                                    report['feature_type_counts'][kind] = report['feature_type_counts'].get(kind, 0)+1
                                    report['per_lod_counts'][str(level)] += 1
                                    report['interior_rings_ignored'] += holes
                                    report['non_planar_risk_count'] += risks
                                    del result, vertices, faces
                                # Do not retain an index into the preceding feature tree
                                # while iterparse buffers the next feature.
                                del index, bindings, feature
                        if parent is not None and split_tag(parent.tag)[1] == 'cityObjectMember' and not feature_type(item):
                            uri, name = split_tag(item.tag)
                            key = f'{{{uri}}}{name}'
                            report['skipped_feature_types'][key] = report['skipped_feature_types'].get(key, 0)+1
                        # Keep active feature trees and the tiny Envelope until complete.
                        inside_envelope = any(gml(e, 'Envelope') for e in stack[:-1])
                        if feature_depth == 0 and not inside_envelope:
                            item.clear()
                            if parent is not None:
                                parent.remove(item)
                        stack.pop()
                report['files_parsed'] += 1
            except ET.ParseError as exc:
                report['file_errors'] += 1
                report['errors'].append({'file': filename, 'error': str(exc)})
    if report['vertices']:
        report['local_bbox'] = {'min': low, 'max': high}
    for envelope in report['source_envelopes']:
        lower, upper = envelope.get('lowerCorner', []), envelope.get('upperCorner', [])
        envelope['anchor_inside_horizontal_bbox'] = (lower[0] <= lat <= upper[0] and lower[1] <= lon <= upper[1]
                                                     if len(lower) >= 2 and len(upper) >= 2 else None)
    report['declared_crs_mismatch'] = [crs for crs in report['declared_crs']
                                       if crs.split('/')[-1].split(':')[-1] != '6697']
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--zip', type=Path)
    source.add_argument('--gml-dir', type=Path)
    parser.add_argument('--textures', action='store_true', help='preserve appearance images and UVs in OBJ/MTL')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--anchor', type=float, nargs=2, default=(34.6500, 135.3830), metavar=('LAT', 'LON'))
    parser.add_argument('--target-crs', type=int, default=6674, help='plane-rectangular EPSG code (6674=Osaka zone VI, 6677=Tokyo zone IX)')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.out.resolve() == args.report.resolve():
        parser.error('--out and --report must differ')
    try:
        report = run(args)
    except (OSError, ValueError, zipfile.BadZipFile, sqlite3.Error) as exc:
        parser.exit(1, f'conversion failed: {exc}\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report['file_errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
