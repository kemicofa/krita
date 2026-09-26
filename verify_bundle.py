#!/usr/bin/env python3
"""Validate bundle integrity, embedded dependencies, and pen-sensor wiring."""
import argparse
import base64
import hashlib
import io
import struct
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PIL import Image


def validate(path):
    ns = '{urn:oasis:names:tc:opendocument:xmlns:manifest:1.0}'
    with ZipFile(path) as z:
        assert z.testzip() is None, 'Corrupt ZIP member'
        assert len(z.namelist()) == len(set(z.namelist())), 'Duplicate archive path'
        assert z.read('mimetype') == b'application/x-krita-resourcebundle'
        entries = ET.fromstring(z.read('META-INF/manifest.xml'))
        counts = {'paintoppresets':0,'brushes':0,'patterns':0}
        names = set()
        for entry in entries:
            name = entry.get(ns+'full-path')
            if name=='/':
                continue
            assert not name.startswith('/') and '..' not in name.split('/')
            data = z.read(name)
            assert hashlib.md5(data).hexdigest()==entry.get(ns+'md5sum'), name
            typ = entry.get(ns+'media-type')
            counts[typ] += 1
            assert name.split('/')[0]==typ
            if typ=='brushes':
                header,version,w,h,depth,magic,spacing = struct.unpack('>7I',data[:28])
                assert (version,depth,magic)==(2,1,0x47494D50)
                assert len(data)==header+w*h and max(data[header:])>0
            elif typ=='patterns':
                Image.open(io.BytesIO(data)).verify()
            else:
                im = Image.open(io.BytesIO(data))
                assert im.size==(200,200) and im.info['version']=='5.0'
                preset = ET.fromstring(im.info['preset'])
                assert preset.get('paintopid')=='paintbrush'
                assert preset.get('name') not in names
                names.add(preset.get('name'))
                resources = preset.findall('resources/resource')
                assert len(resources)==2
                for r in resources:
                    embedded = base64.b64decode(r.text,validate=True)
                    assert embedded==z.read(r.get('type')+'/'+r.get('filename'))
                    assert hashlib.md5(embedded).hexdigest()==r.get('md5sum')
                params = {p.get('name'):p.text for p in preset.findall('param')}
                brush = ET.fromstring(params['brush_definition'])
                assert brush.get('filename') in [r.get('filename') for r in resources]
                assert params['Texture/Pattern/PatternFileName'] in [r.get('filename') for r in resources]
                assert 'pressure' in params['SizeSensor']
                if 'Mechanical' in preset.get('name'):
                    assert 'declination' not in params['SizeSensor']
                    assert params['PressureRotation']=='false'
                    assert params['PressureRatio']=='false'
                else:
                    assert 'declination' in params['SizeSensor']
                    assert params['SizeUseSameCurve']=='false'
                    assert 'ascension' in params['RotationSensor']
                    assert params['PressureRotation']=='true'
                    assert params['PressureRatio']=='true'
                    assert 'declination' in params['Texture/Strength/Sensor']
                for key,value in params.items():
                    if key.endswith('Sensor'):
                        ET.fromstring(value)
        assert counts=={'paintoppresets':10,'brushes':10,'patterns':4}, counts
        ET.fromstring(z.read('meta.xml'))
        assert z.read('LICENSE.txt')
    print('PASS: 10 presets, 10 tips, 4 textures, checksums, embedded resources and tilt sensors.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',nargs='?',type=Path,default=Path('dist/Tilt_Sketch_Pencils.bundle'))
    validate(parser.parse_args().bundle)
