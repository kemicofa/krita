#!/usr/bin/env python3
"""Build original, self-contained Krita 5.x pencil presets and a resource bundle.

Requires Pillow and NumPy. Brush masks are calculated coverage maps; paper
height maps use periodic noise so the texture tiles without a seam.
"""
from __future__ import annotations

import base64
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'dist'
VERSION = (ROOT/'VERSION').read_text().strip()
ICON_ASSETS = {
    entry['id']: ROOT/'assets/icons'/entry['file']
    for entry in json.loads((ROOT/'assets/icons/prompts.json').read_text())['assets']
}
NAME = 'Tilt Sketch Pencils'
IDENTITY = '0,0;1,1;'

# The size is the maximum tip diameter, reached at strong pressure/low elevation.
# upright is a multiplier, so detail drawing uses a much smaller contact patch.
SPECS = [
    dict(id=1, name='2H Construction', grade='2H', size=16, upright=.15,
         pressure_floor=.65, opacity=.60, flow=.60, grain='fine', shape='round',
         softness=.18, tooth=.18, ratio=.68, spacing=.10, texture=.34,
         purpose='Light construction lines and precise hatching; modest tilt shading.'),
    dict(id=2, name='HB Everyday', grade='HB', size=28, upright=.15,
         pressure_floor=.40, opacity=.82, flow=.67, grain='fine', shape='round',
         softness=.23, tooth=.24, ratio=.55, spacing=.11, texture=.35,
         purpose='Balanced outlines and crosshatching; smooth transition into side shading.'),
    dict(id=3, name='2B Gesture', grade='2B', size=44, upright=.13,
         pressure_floor=.18, opacity=.94, flow=.76, grain='medium', shape='round',
         softness=.25, tooth=.28, ratio=.45, spacing=.12, texture=.38,
         purpose='Expressive pressure taper for figure gestures and lively contours.'),
    dict(id=4, name='4B Soft Graphite', grade='4B', size=66, upright=.105,
         pressure_floor=.42, opacity=.90, flow=.55, grain='medium', shape='round',
         softness=.52, tooth=.32, ratio=.42, spacing=.10, texture=.40,
         purpose='Soft edges and layered values; broad, velvety shading when tilted.'),
    dict(id=5, name='6B Graphite Block', grade='6B', size=96, upright=.10,
         pressure_floor=.45, opacity=1.0, flow=.82, grain='rough', shape='block',
         softness=.25, tooth=.34, ratio=.40, spacing=.10, texture=.39,
         purpose='Dark, chunky graphite marks and broad planes with visible paper tooth.'),
    dict(id=6, name='Mechanical 0.5', grade='0.5', size=2.6, upright=1.0,
         pressure_floor=.88, opacity=.92, flow=.95, grain='fine', shape='round',
         softness=.10, tooth=.06, ratio=1., spacing=.08, texture=1.,
         purpose='Consistent fine lines for small details; pressure changes darkness, tilt is disabled.'),
    dict(id=7, name='Carpenter Edge', grade='FLAT', size=80, upright=.12,
         pressure_floor=.60, opacity=.92, flow=.76, grain='medium', shape='chisel',
         softness=.12, tooth=.22, ratio=.25, spacing=.08, texture=.34,
         purpose='A rectangular contact patch for narrow edges and wide architectural shading.'),
    dict(id=8, name='Hard Charcoal', grade='H', size=58, upright=.10,
         pressure_floor=.30, opacity=.96, flow=.76, grain='rough', shape='round',
         softness=.23, tooth=.48, ratio=.38, spacing=.13, texture=.38,
         purpose='Dry, broken contours and scratchy hatching; rough side-of-pencil shading.'),
    dict(id=9, name='Willow Charcoal', grade='SOFT', size=126, upright=.075,
         pressure_floor=.45, opacity=.82, flow=.43, grain='rough', shape='round',
         softness=.68, tooth=.44, ratio=.44, spacing=.10, texture=.42,
         purpose='Powdery, airy strokes for large shadow masses and soft tonal studies.'),
    dict(id=10, name='Conte Sketch', grade='CONTE', size=64, upright=.12,
         pressure_floor=.48, opacity=.98, flow=.87, grain='laid', shape='block',
         softness=.18, tooth=.30, ratio=.32, spacing=.10, texture=.39,
         purpose='Dense, slightly waxy marks with a squared edge; use rust red for sanguine studies.'),
    dict(id=11, name='Soft Touch', grade='SOFT', size=48, upright=.25,
         pressure_floor=0., opacity=1., flow=1., grain='fine', shape='round',
         softness=.14, tooth=.14, ratio=.40, spacing=.07, texture=.42,
         size_curve='0,0;0.02,0.03;0.04,0.10;0.08,0.28;0.15,0.62;0.25,0.88;0.45,1;1,1;',
         opacity_curve='0,0;0.02,0.55;0.06,0.85;0.15,0.97;0.3,1;1,1;',
         flow_curve='0,0.55;0.05,0.90;0.15,1;1,1;',
         recommended_color='#101010',
         purpose='Dark, thick graphite with light pressure; eases down to a pointy end on lift, with broad tilt shading.'),
]


def png_bytes(image):
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def md5(data):
    return hashlib.md5(data).hexdigest()


def periodic_noise(rng, size, radius):
    field = rng.normal(size=(size, size))
    f = np.fft.fftfreq(size)
    filt = np.exp(-2 * np.pi**2 * radius**2 * (f[:, None]**2 + f[None, :]**2))
    field = np.fft.ifft2(np.fft.fft2(field) * filt).real
    return (field - field.mean()) / field.std()


def make_pattern(kind):
    rng = np.random.default_rng({'fine': 117, 'medium': 231, 'rough': 429, 'laid': 603}[kind])
    size = 256
    radius = {'fine': .55, 'medium': 1.05, 'rough': 1.80, 'laid': .85}[kind]
    field = .72 * periodic_noise(rng, size, radius)
    field += .22 * periodic_noise(rng, size, 3.2)
    field += .12 * periodic_noise(rng, size, 10)
    if kind == 'laid':
        yy, xx = np.mgrid[:size, :size]
        field += .24 * np.sin(2 * np.pi * yy / 8) + .08 * np.sin(2 * np.pi * xx / 64)
    # Retain actual valleys and peaks: pressure will decide which receive pigment.
    pixels = np.uint8(np.clip(.52 + .22 * field, .03, .98) * 255)
    return Image.fromarray(pixels).convert('RGB')


def make_tip(spec):
    size = 160
    rng = np.random.default_rng(700 + spec['id'])
    y, x = np.mgrid[:size, :size].astype(float)
    x = (x + .5 - size/2) / (size*.46)
    y = (y + .5 - size/2) / (size*.46)
    if spec['shape'] == 'round':
        dist = np.sqrt(x*x + (y/.92)**2)
    elif spec['shape'] == 'block':
        dist = (abs(x)**5 + abs(y/.85)**5)**.2
    else:
        dist = (abs(x)**10 + abs(y/.72)**10)**.1
    rough = periodic_noise(rng, size, 2.1)
    dist += rough * (.012 if spec['id'] == 6 else .028)
    coverage = np.clip((1-dist) / spec['softness'], 0, 1)
    grain = np.clip(.60 + .20*periodic_noise(rng, size, .8), 0, 1)
    coverage *= (1-spec['tooth']) + spec['tooth'] * grain
    # A slight worn facet makes repeated marks less perfectly geometric.
    coverage *= np.clip(1 - .14*x + .04*y, .65, 1)
    alpha = np.uint8(np.clip(coverage, 0, 1)*255)
    label = ('TSP ' + spec['name']).encode('ascii') + b'\0'
    # GIMP GBR v2: header size, version, width, height, depth, magic, spacing.
    header = struct.pack('>7I', 28+len(label), 2, size, size, 1, 0x47494D50, 10)
    return header + label + alpha.tobytes(), alpha


def param(root, name, value):
    kind = 'string' if isinstance(value, str) else 'internal'
    if isinstance(value, bool):
        value = 'true' if value else 'false'
    ET.SubElement(root, 'param', name=name, type=kind).text = str(value)


def sensor_xml(sensors):
    root = ET.Element('params', id=sensors[0][0] if len(sensors)==1 else 'sensorslist')
    for sid, curve in sensors:
        node = root if len(sensors)==1 else ET.SubElement(root, 'ChildSensor', id=sid)
        ET.SubElement(node, 'curve').text = curve
    return ET.tostring(root, encoding='unicode')


def option(root, name, sensors, value=1., enabled=True, use_curve=True):
    param(root, 'Pressure'+name, enabled)
    param(root, name+'Sensor', sensor_xml(sensors))
    param(root, name+'UseCurve', use_curve)
    param(root, name+'UseSameCurve', len(sensors)==1)
    param(root, name+'Value', value)
    param(root, name+'curveMode', 0)
    param(root, name+'commonCurve', sensors[0][1])


def make_preset(spec, tip_name, tip_data, pattern_name, pattern_data):
    root = ET.Element('Preset', paintopid='paintbrush', name=spec['preset_name'], embedded_resources='2')
    embedded = ET.SubElement(root, 'resources')
    for typ, name, data in [('brushes', tip_name, tip_data), ('patterns', pattern_name, pattern_data)]:
        r = ET.SubElement(embedded, 'resource', type=typ, name=Path(name).stem,
                          filename=name, md5sum=md5(data))
        r.text = base64.b64encode(data).decode('ascii')

    for key, value in {
        'paintop':'paintbrush', 'CompositeOp':'normal', 'ColorSource/Type':'plain',
        'PaintOpAction':2, 'EraserMode':False, 'MaskingBrush/Enabled':False,
        'PaintOpSettings/isAirbrushing':False, 'PaintOpSettings/ignoreSpacing':False,
        'PaintOpSettings/updateSpacingBetweenDabs':True, 'Spacing/Isotropic':True,
        'KisPrecisionOption/AutoPrecisionEnabled':True,
        'KisPrecisionOption/precisionLevel':5, 'lodUserAllowed':False,
        'requiredBrushFile':tip_name, 'requiredBrushFilesList':tip_name,
    }.items():
        param(root, key, value)
    tip = ET.Element('Brush', type='gbr_brush', BrushVersion='2', filename=tip_name,
                     md5sum=md5(tip_data), scale=str(spec['size']/160),
                     spacing=str(spec['spacing']), useAutoSpacing='0', autoSpacingCoeff='1',
                     angle=str(math.pi/2 if spec['id']!=6 else 0), brushApplication='0',
                     ColorAsMask='1', AdjustmentVersion='2', AdjustmentMidPoint='127',
                     BrightnessAdjustment='0', ContrastAdjustment='0', AutoAdjustMidPoint='0')
    param(root, 'brush_definition', ET.tostring(tip, encoding='unicode'))
    pf = spec['pressure_floor']
    # A zero floor lets Soft Touch close to a point. Its early rise supplies
    # useful width without requiring high pressure; the other pencils keep
    # their original response curves.
    size_sensors = [('pressure', spec.get('size_curve', f'0,{pf};0.5,{pf+(1-pf)*.55};1,1;'))]
    if spec['id'] != 6:
        u = spec['upright']
        size_sensors.append(('declination', f'0,1;0.25,0.95;0.55,0.56;0.80,{u*1.9};1,{u};'))
    option(root, 'Size', size_sensors)
    option(root, 'Opacity', [('pressure', spec.get('opacity_curve', '0,0.03;0.25,0.26;0.60,0.70;1,1;'))], spec['opacity'])
    option(root, 'Flow', [('pressure', spec.get('flow_curve', '0,0.35;0.5,0.78;1,1;'))], spec['flow'])
    option(root, 'Rotation', [('ascension', IDENTITY)], enabled=spec['id']!=6)
    option(root, 'Ratio', [('declination', f"0,{spec['ratio']};0.55,{(spec['ratio']+1)/2};1,1;")], enabled=spec['id']!=6)
    for name in ['Scatter','Mirror','Softness','Sharpness','Spacing','Darken','Mix','h','s','v','Rate']:
        param(root, 'Pressure'+name, False)

    for key, value in {
        'Enabled':True, 'Scale':1.0 if spec['grain']!='fine' else .8,
        'Brightness':0., 'Contrast':1., 'NeutralPoint':.5,
        'OffsetX':0, 'OffsetY':0, 'MaximumOffsetX':256, 'MaximumOffsetY':256,
        'isRandomOffsetX':False, 'isRandomOffsetY':False,
        'TexturingMode':0 if spec['id']==6 else 12, 'CutoffLeft':0, 'CutoffRight':255,
        'CutoffPolicy':0, 'Invert':False,
        'Name':Path(pattern_name).stem, 'PatternFileName':pattern_name,
        'PatternMD5Sum':md5(pattern_data),
    }.items():
        param(root, 'Texture/Pattern/'+key, value)
    texture_sensors = [('pressure', '0,0.78;0.25,0.82;0.65,0.92;1,1;')]
    if spec['id'] != 6:
        # Small upright dabs need more coverage than a broad side contact:
        # otherwise downsampling plus height texturing can erase a fine line.
        texture_sensors.append(('declination', '0,0.54;0.30,0.62;0.65,0.90;1,1;'))
    option(root, 'Texture/Strength/', texture_sensors,
           spec['texture']/.60 if spec['id']!=6 else 1., use_curve=spec['id']!=6)
    param(root, 'Texture/Strength/StrengthVersion', 2)
    ET.indent(root)
    return ET.tostring(root, encoding='unicode')


def font(size, bold=False):
    # Pillow's bundled font keeps builds independent of installed system fonts.
    return ImageFont.load_default(size=size)


def icon(spec):
    with Image.open(ICON_ASSETS[spec['id']]) as artwork:
        im = artwork.convert('RGB').resize((200,200),Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(im)
    colors = ['#4f6277','#89631c','#185d61','#762d40','#44505f',
              '#41596a','#aa4e16','#383b3d','#403c38','#9b482e','#101010']
    accent = colors[spec['id']-1]
    label_font = font(24,True)
    label_width = draw.textbbox((0,0),spec['grade'],font=label_font)[2]
    draw.rounded_rectangle((6,6,22+label_width,39),radius=6,fill='#f4f0e8')
    draw.text((14,9),spec['grade'],font=label_font,fill=accent)
    draw.rectangle((0,182,199,199),fill='#f4f0e8')
    draw.text((10,185),'FIXED TIP' if spec['id']==6 else 'TILT',font=font(11),fill=accent)
    draw.text((173,184),f"{spec['id']:02}",font=font(13),fill=accent)
    return im


def icon_preview(thumbnails):
    footer = 126 + math.ceil(len(thumbnails)/5)*280
    page = Image.new('RGB',(1280,footer+126),'#efeee8')
    draw = ImageDraw.Draw(page)
    draw.text((40,25),'TILT SKETCH PENCILS / ICONS',font=font(34),fill='#253b3c')
    draw.text((40,73),f'{len(thumbnails)} illustrated presets, with grade labels and distinct tool silhouettes.',font=font(19),fill='#526563')
    for index,(spec,thumbnail) in enumerate(thumbnails):
        x,y = 40+(index%5)*240,110+(index//5)*280
        draw.rounded_rectangle((x-8,y-8,x+216,y+251),radius=10,fill='#ffffff')
        page.paste(thumbnail,(x+4,y))
        draw.text((x+2,y+218),spec['name'],font=font(18),fill='#253b3c')
    draw.text((40,footer),'64 PX / COMPACT PRESET GRID',font=font(15),fill='#526563')
    for index,(_,thumbnail) in enumerate(thumbnails):
        page.paste(thumbnail.resize((64,64),Image.Resampling.LANCZOS),(40+index*80,footer+32))
    page.save(OUTPUT/'Icon_Preview.png')


def bundle(files):
    ns = 'urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'
    ET.register_namespace('manifest',ns)
    manifest = ET.Element('{'+ns+'}manifest', {'{'+ns+'}version':'1.2'})
    ET.SubElement(manifest, '{'+ns+'}file-entry', {
        '{'+ns+'}full-path':'/', '{'+ns+'}media-type':'application/x-krita-resourcebundle'})
    for path, data in files.items():
        kind = path.split('/')[0]
        node = ET.SubElement(manifest, '{'+ns+'}file-entry', {
            '{'+ns+'}full-path':path, '{'+ns+'}media-type':kind, '{'+ns+'}md5sum':md5(data)})
        tags = ET.SubElement(node, '{'+ns+'}tags')
        ET.SubElement(tags, '{'+ns+'}tag').text = NAME
    meta = f'''<?xml version="1.0" encoding="UTF-8"?>
<meta:meta xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<meta:generator>Tilt Sketch Pencils builder {VERSION}</meta:generator>
<meta:bundle-version>1</meta:bundle-version>
<dc:title>Tilt Sketch Pencils</dc:title>
<dc:author>kemicofa</dc:author>
<dc:description>{len(SPECS)} original pencils for sketching, with pressure, pen tilt, and embedded paper grain.</dc:description>
<meta:creation-date>2026-09-26</meta:creation-date>
<meta:meta-userdefined meta:name="tag" meta:value="Tilt Sketch Pencils"/>
<meta:meta-userdefined meta:name="license" meta:value="MIT"/>
<meta:meta-userdefined meta:name="website" meta:value="https://github.com/kemicofa/krita"/>
</meta:meta>'''
    cover = Image.new('RGB',(400,400),'#f4f0e8')
    d = ImageDraw.Draw(cover)
    d.rectangle((0,0,399,17),fill='#397777')
    for i,line in enumerate(['TILT','SKETCH','PENCILS']):
        d.text((32,35+i*65),line,font=font(48,True),fill='#253b3c')
    d.text((34,279),f'{len(SPECS)} tools for line & shade',font=font(23),fill='#397777')
    d.text((34,335),'GRAPHITE / CHARCOAL / CONTE',font=font(16),fill='#575854')
    def write(z, path, data, compress=zipfile.ZIP_DEFLATED):
        entry = zipfile.ZipInfo(path, date_time=(2026,1,1,0,0,0))
        entry.compress_type = compress
        entry.external_attr = 0o100644 << 16
        z.writestr(entry,data)
    with zipfile.ZipFile(OUTPUT/'Tilt_Sketch_Pencils.bundle','w',zipfile.ZIP_DEFLATED) as z:
        write(z,'mimetype','application/x-krita-resourcebundle',zipfile.ZIP_STORED)
        write(z,'META-INF/manifest.xml',ET.tostring(manifest,encoding='utf-8',xml_declaration=True))
        write(z,'meta.xml',meta)
        write(z,'preview.png',png_bytes(cover))
        write(z,'LICENSE.txt',(ROOT/'LICENSE').read_bytes())
        for path,data in files.items():
            write(z,path,data)


def main():
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    OUTPUT = parser.parse_args().output.resolve()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    palette = b'GIMP Palette\nName: TSP Graphite Charcoal\nColumns: 1\n# Deep graphite / charcoal\n16 16 16 Near Black Charcoal\n'
    files = {'palettes/TSP_Graphite_Charcoal.gpl': palette}
    (OUTPUT/'TSP_Graphite_Charcoal.gpl').write_bytes(palette)
    thumbnails = []
    (OUTPUT/'icons').mkdir(exist_ok=True)
    patterns = {}
    for kind in ['fine','medium','rough','laid']:
        name = f'TSP_paper_{kind}.png'
        data = png_bytes(make_pattern(kind))
        patterns[kind] = name,data
        files['patterns/'+name] = data
    for spec in SPECS:
        spec['preset_name'] = f"TSP {spec['id']:02} - {spec['name']}"
        stem = f"TSP_{spec['id']:02}_"+spec['name'].replace(' ','_')
        tip_name = stem+'.gbr'
        tip_data,_ = make_tip(spec)
        files['brushes/'+tip_name] = tip_data
        pattern_name,pattern_data = patterns[spec['grain']]
        xml = make_preset(spec,tip_name,tip_data,pattern_name,pattern_data)
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('version','5.0')
        metadata.add_text('preset',xml,zip=True)
        out = io.BytesIO()
        thumbnail = icon(spec)
        thumbnail.save(OUTPUT/'icons'/(stem+'.png'))
        thumbnails.append((spec,thumbnail))
        thumbnail.save(out,format='PNG',pnginfo=metadata)
        files['paintoppresets/'+stem+'.kpp'] = out.getvalue()
    for path,data in files.items():
        target = OUTPUT/'resources'/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
    bundle(files)
    icon_preview(thumbnails)
    (OUTPUT/'brush_catalog.json').write_text(json.dumps(SPECS,indent=2)+'\n')
    print(f"Built {len(SPECS)} presets, {len(SPECS)} brush tips, 4 paper textures, 1 palette.")
    print(OUTPUT/'Tilt_Sketch_Pencils.bundle')


if __name__=='__main__':
    main()
