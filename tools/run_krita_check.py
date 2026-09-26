#!/usr/bin/env python3
"""Load a bundle into an isolated Krita profile and test synthetic pen strokes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]


def check_pixels(output, catalog):
    report = json.loads((output/'runtime_report.json').read_text())
    assert len(report['presets'])==10
    for spec, result in zip(catalog,report['presets']):
        assert result['name']==spec['preset_name']
        assert abs(result['loaded_size']-spec['size'])<.01
        assert abs(result['opacity']-spec['opacity'])<.01
        assert abs(result['flow']-spec['flow'])<.01
        xml = ET.fromstring((output/f"{spec['id']:02}-loaded.xml").read_text())
        assert len(xml.findall('resources/resource'))==2, 'Krita failed to resolve embedded resources'
        image = np.array(Image.open(output/f"{spec['id']:02}-metrics.png").convert('L'))
        ink = 254-np.minimum(image,254)
        stats=[]
        for lo,hi in [(75,175),(325,425),(575,675),(825,925)]:
            sample=ink[20:180,lo:hi]
            assert sample.shape==(160,100)
            stats.append({'width':float(np.count_nonzero(sample>6,axis=0).mean()),
                          'ink':float(sample.sum(axis=0).mean()/255)})
        upright,tilted,rotated,light=stats
        assert upright['width']>0, spec['name']+' upright stroke is blank'
        assert light['ink']>0, spec['name']+' light pressure stroke is blank'
        assert upright['ink']>light['ink']*1.5, spec['name']+' pressure response failed'
        if spec['id']==6:
            assert abs(upright['width']-tilted['width'])<.6, 'Mechanical pencil changed width with tilt'
        else:
            assert tilted['width']>upright['width']*2, spec['name']+' did not widen with tilt'
            assert tilted['width']>rotated['width']*1.08, spec['name']+' did not rotate its flat contact'
        result['stroke_measurements']=dict(zip(['upright','tilted','tilted_rotated','light_pressure'],stats))
        print(f"PASS: {spec['name']} — upright {upright['width']:.1f}px, tilted {tilted['width']:.1f}px")
    report['method']='Krita Scratchpad rendered synthetic QTabletEvent pressure and X/Y tilt; no physical tablet tested.'
    report['passed']=True
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--krita',default='krita')
    parser.add_argument('--build-dir',type=Path,default=PROJECT/'dist')
    parser.add_argument('--output',type=Path,default=PROJECT/'build/krita-test')
    parser.add_argument('--python-home',help='Embedded Python prefix; use extracted AppImage/usr for an AppImage')
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    # A stale successful report must never make a failed runtime look successful.
    for filename in ['runtime_report.json','validation.json','log.txt']:
        (output/filename).unlink(missing_ok=True)
    build_dir=args.build_dir.resolve()
    with tempfile.TemporaryDirectory(prefix='tsp-krita-') as temporary:
        temp=Path(temporary)
        data=temp/'data/krita'
        plugin=data/'pykrita/penciltest'
        plugin.mkdir(parents=True)
        shutil.copy(PROJECT/'tools/krita_runtime_plugin.py',plugin/'__init__.py')
        (data/'pykrita/penciltest.desktop').write_text('''[Desktop Entry]
Type=Service
ServiceTypes=Krita/PythonPlugin
X-KDE-Library=penciltest
X-Python-2-Compatible=false
Name=Pencil Runtime Verification
Comment=Isolated build verification
''')
        (data/'bundles').mkdir()
        shutil.copy(build_dir/'Tilt_Sketch_Pencils.bundle',data/'bundles')
        (temp/'config').mkdir()
        (temp/'config/kritarc').write_text(f'''[General]
UseOpenGL=false
ResourceDirectory={data}/

[python]
enable_penciltest=true
''')
        env=os.environ.copy()
        for key in ['PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','LD_LIBRARY_PATH']:
            env.pop(key,None)
        env.update(XDG_DATA_HOME=str(temp/'data'),XDG_CONFIG_HOME=str(temp/'config'),
                   XDG_CACHE_HOME=str(temp/'cache'),QT_QPA_PLATFORM='offscreen',
                   TSP_BUILD_DIR=str(build_dir),TSP_TEST_OUTPUT=str(output))
        if args.python_home:
            env['PYTHONHOME']=args.python_home
        with (output/'krita.log').open('w') as log:
            proc=subprocess.run([args.krita,'--nosplash'],env=env,
                                stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if proc.returncode or not (output/'runtime_report.json').exists():
            details=(output/'log.txt').read_text() if (output/'log.txt').exists() else ''
            raise RuntimeError(f'Krita failed ({proc.returncode}). See {output}/krita.log\n{details}')
    check_pixels(output,json.loads((build_dir/'brush_catalog.json').read_text()))


if __name__=='__main__':
    main()
