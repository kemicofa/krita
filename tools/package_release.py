#!/usr/bin/env python3
"""Package the validated bundle, guide, and genuine stroke preview for release."""
import hashlib
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
version=(ROOT/'VERSION').read_text().strip()
shutil.copy(ROOT/'README.md',DIST/'README.md')
shutil.copy(ROOT/'LICENSE',DIST/'LICENSE.txt')
shutil.copy(ROOT/'build/krita-test/validation.json',DIST/'validation.json')
files=['Tilt_Sketch_Pencils.bundle','Brush_Preview.png','README.md','LICENSE.txt','brush_catalog.json','validation.json']
with ZipFile(DIST/f'Tilt_Sketch_Pencils-{version}.zip','w',ZIP_DEFLATED) as z:
    for filename in files:
        z.write(DIST/filename,filename)
checks=[]
for p in sorted(DIST.iterdir()):
    if p.suffix in {'.zip','.bundle','.png','.json'}:
        checks.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}')
(DIST/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n')
print(DIST/f'Tilt_Sketch_Pencils-{version}.zip')
