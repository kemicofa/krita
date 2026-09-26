#!/usr/bin/env python3
"""Lay out actual Krita-rendered strokes, without simulating brush behavior."""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size):
    return ImageFont.load_default(size=size)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strokes',type=Path,default=Path('build/krita-test/strokes'))
    parser.add_argument('--output',type=Path,default=Path('dist/Brush_Preview.png'))
    parser.add_argument('--catalog',type=Path,default=Path('dist/brush_catalog.json'))
    args=parser.parse_args()
    specs=json.loads(args.catalog.read_text())
    footer=235+math.ceil(len(specs)/2)*392
    page=Image.new('RGB',(1920,footer+65),'#efeee8')
    d=ImageDraw.Draw(page)
    d.rectangle((0,0,1919,18),fill='#397777')
    d.text((44,46),'TILT SKETCH PENCILS',font=font(54),fill='#253b3c')
    d.text((46,118),f'{len(specs)} original Krita brushes  /  graphite, charcoal & Conte',font=font(26),fill='#526563')
    d.text((46,160),'Actual Krita strokes with synthetic pressure and pen tilt. Each sample uses its default brush size.',font=font(20),fill='#66716c')
    for index,spec in enumerate(specs):
        x=30+(index%2)*950
        y=216+(index//2)*392
        d.rounded_rectangle((x,y,x+920,y+370),radius=13,fill='#ffffff')
        accent='#a76144' if spec['id']>=8 else '#397777'
        d.text((x+18,y+14),f"{spec['id']:02}   {spec['name']}",font=font(28),fill=accent)
        d.text((x+18,y+53),'PRESSURE: LIGHT TO FIRM',font=font(13),fill='#77817e')
        d.text((x+473,y+53),'TILT: UPRIGHT TO SIDE',font=font(13),fill='#77817e')
        swatch=Image.open(args.strokes/f"{spec['id']:02}.png").convert('RGB').crop((0,0,900,260))
        page.paste(swatch,(x+10,y+73))
        d.text((x+35,y+218),'SIDE / LIGHT',font=font(12),fill='#77817e')
        d.text((x+370,y+218),'SIDE / FIRM',font=font(12),fill='#77817e')
        d.text((x+700,y+218),'HATCHING',font=font(12),fill='#77817e')
        labels=['Light construction / clean hatching','Balanced lines / everyday sketching','Expressive taper / gesture drawing',
                'Soft edges / layered tonal studies','Dark graphite / broad planes','Fine detail / tilt disabled',
                'Rectangular edge / architectural shading','Broken grain / dry contours',
                'Powdery marks / large shadow masses','Dense pigment / squared edges',
                'Light touch / dark marks / pointy endings']
        d.text((x+20,y+339),labels[index],font=font(18),fill='#536361')
    d.text((45,footer),'Import Tilt_Sketch_Pencils.bundle in Krita. Search presets for TSP. Tilt requires a compatible pen and tablet.',
           font=font(21),fill='#526563')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    page.save(args.output)
    print(args.output)
    soft_touch_preview(args.strokes.parent/'11-taper.png',args.output.parent/'Soft_Touch_Preview.png')


def soft_touch_preview(strokes_path,output):
    """Show the real low-pressure strokes and their terminal shapes."""
    strokes=Image.open(strokes_path).convert('RGB')
    page=Image.new('RGB',(1280,1000),'#efeee8')
    d=ImageDraw.Draw(page)
    d.text((40,30),'11 / SOFT TOUCH',font=font(42),fill='#101010')
    d.text((40,91),'Dark with light pressure. A pointy finish as you ease off.',font=font(23),fill='#526563')
    d.rectangle((988,35,1024,71),fill='#101010')
    d.text((1037,43),'#101010',font=font(24),fill='#101010')
    labels=['20% PRESSURE / HELD STEADY TO SHOW THE FULL WIDTH',
            '20% PRESSURE / EASING OFF TO A POINT',
            '20% PRESSURE / TILTED, THEN EASING OFF']
    for index,(label,center) in enumerate(zip(labels,[90,210,340])):
        y=151+index*170
        d.text((42,y),label,font=font(18),fill='#526563')
        d.rounded_rectangle((32,y+30,1248,y+150),radius=12,fill='#fefefe')
        page.paste(strokes.crop((20,center-50,1080,center+50)),(70,y+40))
    d.text((40,677),'ENDINGS / 3x MAGNIFICATION',font=font(20),fill='#526563')
    for index,center in enumerate([90,210]):
        crop=strokes.crop((840,center-22,1020,center+22))
        page.paste(crop.resize((540,132),Image.Resampling.NEAREST),(40+index*620,718))
    d.text((40,866),'Constant pressure until release',font=font(18),fill='#526563')
    d.text((660,866),'Pressure reduced before release',font=font(18),fill='#526563')
    d.text((40,929),'Actual Krita rendering using simulated pen pressure. No physical tablet tested.',font=font(18),fill='#526563')
    d.text((40,959),'For a pointy end, ease off while moving; an abrupt stationary lift can still end bluntly.',font=font(18),fill='#526563')
    page.save(output)
    print(output)


if __name__=='__main__':
    main()
