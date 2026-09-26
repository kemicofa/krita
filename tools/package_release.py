#!/usr/bin/env python3
"""Package the validated bundle, guide, and genuine stroke preview for release."""
import hashlib
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
version=(ROOT/'VERSION').read_text().strip()
guide=(ROOT/'README.md').read_text().replace('(previews/Brush_Preview.png)','(Brush_Preview.png)')
guide=guide.replace('(previews/Icon_Preview.png)','(Icon_Preview.png)')
guide=guide.replace('(previews/Soft_Touch_Preview.png)','(Soft_Touch_Preview.png)')
guide=guide.replace('](LICENSE)','](LICENSE.txt)')
(DIST/'README.md').write_text(guide)
shutil.copy(ROOT/'LICENSE',DIST/'LICENSE.txt')
shutil.copy(ROOT/'build/krita-test/validation.json',DIST/'validation.json')
files=['Tilt_Sketch_Pencils.bundle','TSP_Graphite_Charcoal.gpl','Brush_Preview.png','Icon_Preview.png','Soft_Touch_Preview.png','README.md','LICENSE.txt','brush_catalog.json','validation.json']
with ZipFile(DIST/f'Tilt_Sketch_Pencils-{version}.zip','w',ZIP_DEFLATED) as z:
    for filename in files:
        z.write(DIST/filename,filename)
with ZipFile(DIST/f'Tilt_Sketch_Pencils_Icons-{version}.zip','w',ZIP_DEFLATED) as z:
    for image in sorted((DIST/'icons').glob('*.png')):
        z.write(image,'icons/'+image.name)
    z.write(ROOT/'assets/icons/prompts.json','prompts.json')
    z.write(ROOT/'LICENSE','LICENSE.txt')
checks=[]
checksum_files={name for name in files if Path(name).suffix in {'.bundle','.gpl','.png','.json'}}
checksum_files.update({f'Tilt_Sketch_Pencils-{version}.zip',f'Tilt_Sketch_Pencils_Icons-{version}.zip'})
for p in sorted(DIST.iterdir()):
    if p.name in checksum_files:
        checks.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}')
(DIST/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n')
print(DIST/f'Tilt_Sketch_Pencils-{version}.zip')
