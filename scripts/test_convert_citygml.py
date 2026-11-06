"""Regression checks: python3 -m unittest discover -s scripts -p 'test_convert_citygml.py'."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from convert_citygml import run


HEADER = '''<c:CityModel xmlns:c="http://www.opengis.net/citygml/2.0"
 xmlns:b="http://www.opengis.net/citygml/building/2.0"
 xmlns:r="http://www.opengis.net/citygml/bridge/2.0"
 xmlns:f="http://www.opengis.net/citygml/cityfurniture/3.0"
 xmlns:g="http://www.opengis.net/gml/3.2"
 xmlns:x="http://www.w3.org/1999/xlink"
 xmlns:v="http://www.opengis.net/citygml/vegetation/2.0">'''
COORDS = '34.65 135.383 10 34.65 135.38301 10 34.65001 135.38301 10 34.65001 135.383 10 34.65 135.383 10'


def polygon(identity, coords=COORDS, hole=False):
    interior = '<g:interior><g:LinearRing><g:posList>'+COORDS+'</g:posList></g:LinearRing></g:interior>' if hole else ''
    return f'<g:Polygon g:id="{identity}"><g:exterior><g:LinearRing><g:posList>{coords}</g:posList></g:LinearRing></g:exterior>{interior}</g:Polygon>'


def geometry(identity, level=3, prefix='b', shape='MultiSurface', **kwargs):
    return f'<{prefix}:lod{level}{shape}><g:CompositeSurface><g:surfaceMember>{polygon(identity, **kwargs)}</g:surfaceMember></g:CompositeSurface></{prefix}:lod{level}{shape}>'


def member(tag, identity, contents):
    return f'<c:cityObjectMember><{tag} g:id="{identity}">{contents}</{tag}></c:cityObjectMember>'


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'input'
        self.source.mkdir()

    def convert(self, xml, zipped=False):
        path = self.source/'test.gml'
        path.write_text(HEADER+xml+'</c:CityModel>')
        archive = self.root/'input.zip'
        if zipped:
            with zipfile.ZipFile(archive, 'w') as z:
                z.write(path, 'udx/test.GML')
                z.writestr('textures/ignored.jpg', 'not xml')
        args = argparse.Namespace(zip=archive if zipped else None,
                                  gml_dir=None if zipped else self.source,
                                  out=self.root/'test.obj', report=self.root/'report.json',
                                  anchor=(34.65, 135.383), target_crs=6674)
        report = run(args)
        self.assertEqual(report, json.loads(args.report.read_text()))
        lines = args.out.read_text().splitlines()
        vertices = [list(map(float, line.split()[1:])) for line in lines if line.startswith('v ')]
        faces = [list(map(int, line.split()[1:])) for line in lines if line.startswith('f ')]
        self.assertEqual(len(vertices), report['vertices'])
        self.assertEqual(len(faces), report['triangles'])
        self.assertTrue(all(1 <= i <= len(vertices) for face in faces for i in face))
        return report, lines, vertices

    def test_highest_lod_nested_parts_xlinks_and_holes(self):
        part = '<b:consistsOfBuildingPart><b:BuildingPart g:id="part">'+geometry('part_polygon', 4)+'</b:BuildingPart></b:consistsOfBuildingPart>'
        contents = geometry('low', 1, shape='Solid')
        contents += '<b:lod3Solid><g:Solid><g:exterior><g:CompositeSurface><g:surfaceMember x:href="#high"/></g:CompositeSurface></g:exterior></g:Solid></b:lod3Solid>'
        contents += '<b:boundedBy><b:WallSurface>'+geometry('high', 3, hole=True)+'</b:WallSurface></b:boundedBy>'+part
        report, lines, vertices = self.convert(member('b:Building', 'parent', contents))
        self.assertEqual(report['feature_type_counts'], {'Building': 1, 'BuildingPart': 1})
        self.assertEqual(report['per_lod_counts'], {'1': 0, '2': 0, '3': 1, '4': 1})
        self.assertEqual((report['vertices'], report['triangles'], report['interior_rings_ignored']), (8, 4, 1))
        self.assertIn('o parent', lines)
        self.assertIn('g BuildingPart_part', lines)
        self.assertEqual(vertices[0], [0., 0., 10.])
        self.assertGreater(vertices[1][0], 0.)
        self.assertGreater(vertices[2][1], 0.)

    def test_bad_feature_continues_bridge_furniture_zip_and_skipped(self):
        xml = member('b:Building', 'bad', geometry('bad_poly', coords='bad data'))
        xml += member('r:Bridge', 'bridge', geometry('bridge_poly', 2, prefix='r', shape='Solid'))
        xml += member('f:CityFurniture', 'furniture', geometry('furniture_poly', 1, prefix='f', shape='Geometry'))
        xml += member('v:PlantCover', 'ignored', '')
        xml += member('b:Building', 'empty', '')
        directory, lines, _ = self.convert(xml)
        zipped, zip_lines, _ = self.convert(xml, zipped=True)
        self.assertEqual(lines, zip_lines)
        for report in (directory, zipped):
            self.assertEqual(report['feature_errors'], 1)
            self.assertEqual(report['features_without_geometry'], 1)
            self.assertEqual(report['buildings_written'], 0)
            self.assertEqual(report['feature_type_counts'], {'Bridge': 1, 'CityFurniture': 1})
            self.assertEqual(sum(report['skipped_feature_types'].values()), 1)
            self.assertEqual(report['files_parsed'], 1)

    def test_textures_directory_zip_aggregate_and_missing_image(self):
        # Appearance follows geometry, as in Expo. Solid members use XLinks.
        for zipped in (False, True):
            for aggregate in (False, True):
                with self.subTest(zipped=zipped, aggregate=aggregate):
                    shape = polygon('poly').replace('<g:LinearRing>', '<g:LinearRing g:id="ring">')
                    solid = ('<b:lod3Solid><g:Solid g:id="solid"><g:exterior>'
                             '<g:CompositeSurface><g:surfaceMember x:href="#poly"/>'
                             '</g:CompositeSurface></g:exterior></g:Solid></b:lod3Solid>')
                    target = 'solid' if aggregate else '#poly'
                    app = f'''<a:appearance xmlns:a="http://www.opengis.net/citygml/appearance/2.0">
                      <a:Appearance><a:surfaceDataMember><a:ParameterizedTexture>
                      <a:imageURI>mesh_appearance/test.jpg</a:imageURI>
                      <a:target uri="{target}"><a:TexCoordList>
                      <a:textureCoordinates ring="#ring">0 0 1 0 1 1 0 1 0 0</a:textureCoordinates>
                      </a:TexCoordList></a:target>
                      </a:ParameterizedTexture></a:surfaceDataMember></a:Appearance></a:appearance>'''
                    xml = member('b:Building', 'textured', solid + shape + app)
                    xml += member('b:Building', 'plain', geometry('plain_poly'))
                    if aggregate:
                        # Expo also has global appearanceMember after city objects.
                        xml = xml.replace(app, '') + app.replace('a:appearance', 'a:appearanceMember')
                    path = self.source/'test.gml'
                    path.write_text(HEADER + xml + '</c:CityModel>')
                    image = self.source/'mesh_appearance'/'test.jpg'
                    image.parent.mkdir(exist_ok=True)
                    image.write_bytes(b'fixture image')
                    archive = self.root/'textures.zip'
                    with zipfile.ZipFile(archive, 'w') as z:
                        z.write(path, 'udx/bldg/test.gml')
                        z.write(image, 'udx/bldg/mesh_appearance/test.jpg')
                    args = argparse.Namespace(zip=archive if zipped else None,
                                              gml_dir=None if zipped else self.source,
                                              out=self.root/'textured.obj', report=self.root/'texture.json',
                                              anchor=(34.65, 135.383), target_crs=6674, textures=True)
                    report = run(args)
                    self.assertEqual((report['textured_surfaces'], report['textures_copied'],
                                      report['missing_images']), (1, 1, 0))
                    lines = args.out.read_text().splitlines()
                    self.assertIn('mtllib textured.mtl', lines)
                    self.assertIn('usemtl texture_1', lines)
                    self.assertIn('vt 0.000000000 1.000000000', lines)
                    self.assertEqual([line for line in lines if line.startswith('f ')],
                                     ['f 1/1 2/2 3/3', 'f 1/1 3/3 4/4', 'f 5 6 7', 'f 5 7 8'])
                    self.assertLess(lines.index('usemtl default'), lines.index('f 5 6 7'))
                    self.assertIn('map_Kd textured_textures/texture_1.jpg',
                                  args.out.with_suffix('.mtl').read_text())
                    self.assertEqual((self.root/'textured_textures/texture_1.jpg').read_bytes(), b'fixture image')
        # Missing images fall back to untextured faces and count distinct images.
        args.zip = None
        args.gml_dir = self.source
        image.unlink()
        report = run(args)
        self.assertEqual(report['missing_images'], 1)
        self.assertEqual(report['textured_surfaces'], 0)
        self.assertNotIn('vt ', args.out.read_text())
        self.assertIn('f 1 2 3', args.out.read_text())

    def test_nonplanar_and_unresolved_xlink(self):
        coords = COORDS.replace('34.65001 135.383 10', '34.65001 135.383 11')
        xml = member('b:Building', 'nonplanar', geometry('nonplanar_poly', coords=coords))
        xml += member('b:Building', 'unresolved', '<b:lod3MultiSurface x:href="#absent"/>')
        report, _, _ = self.convert(xml)
        self.assertEqual(report['non_planar_risk_count'], 1)
        self.assertEqual(report['feature_errors'], 1)
        self.assertEqual(report['features_written'], 1)


if __name__ == '__main__':
    unittest.main()
