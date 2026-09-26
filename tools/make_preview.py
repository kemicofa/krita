#!/usr/bin/env python3
"""Lay out actual Krita-rendered strokes, without simulating brush behavior."""
import argparse
import json
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
    page=Image.new('RGB',(1920,2260),'#efeee8')
    d=ImageDraw.Draw(page)
    d.rectangle((0,0,1919,18),fill='#397777')
    d.text((44,46),'TILT SKETCH PENCILS',font=font(54),fill='#253b3c')
    d.text((46,118),'10 original Krita brushes  /  graphite, charcoal & Conte',font=font(26),fill='#526563')
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
                'Powdery marks / large shadow masses','Dense pigment / squared edges']
        d.text((x+20,y+339),labels[index],font=font(18),fill='#536361')
    d.text((45,2195),'Import Tilt_Sketch_Pencils.bundle in Krita. Search presets for TSP. Tilt requires a compatible pen and tablet.',
           font=font(21),fill='#526563')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    page.save(args.output)
    print(args.output)


if __name__=='__main__':
    main()
