"""One entry point for figure validation and Illustrator rebuilds.

Use the scientific-illustrator-agent virtualenv. --check creates only temporary
SVG files, compares them to the current recorded output directory, and removes
its temporary directory on exit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
SKILL=Path(os.environ.get('FPC_ILLUSTRATOR_SKILL',r'C:\Users\Liuxm\.zcode\skills\scientific-illustrator-agent'))

def run(*args):
    subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,check=True)

def current_output_dir():
    baseline=json.loads((ROOT/'data'/'reference_audit.json').read_text('utf-8'))
    return baseline.get('current_output_dir','optimized_v4')

def check():
    reference=ROOT/current_output_dir()
    names=['WPT_Exploded_Refined.svg','WPT_Geometry_Details.svg','components_registered.json',
           'TOP_COVERLAY_windows.json','BOTTOM_COVERLAY_windows.json']
    with tempfile.TemporaryDirectory(prefix='fpc_check_') as temp:
        out=Path(temp)/'rebuild'
        run(ROOT/'scripts/build_figure.py','--output-dir',out)
        checks={}
        for name in names:
            a=hashlib.sha256((out/name).read_bytes()).hexdigest()
            b=hashlib.sha256((reference/name).read_bytes()).hexdigest()
            if a!=b: raise RuntimeError(f'{reference.name} mismatch: '+name)
            checks[name]={'identical':True,'sha256':a}
        checks['reference']=reference.name
        return checks

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--update-baseline',action='store_true',
                        help='record the new figures as data/reference_audit.json (after a full build)')
    args=parser.parse_args()
    if args.check:
        if args.output_dir: parser.error('--check cannot be combined with --output-dir')
        print(json.dumps(check(),indent=2))
        return
    if args.output_dir is None: parser.error('Specify --check or --output-dir NEW_DIRECTORY')
    out=(ROOT/args.output_dir).resolve()
    if out.exists(): raise FileExistsError('Output directory already exists: '+str(out))
    importer=SKILL/'examples/progressive_svg.py'
    if not importer.is_file(): raise FileNotFoundError(importer)
    run(ROOT/'scripts/build_figure.py','--output-dir',out)
    for name,sub in [('WPT_Exploded_Refined','illustrator_main'),('WPT_Geometry_Details','illustrator_details')]:
        run(importer,'--source-svg',out/(name+'.svg'),'--output-dir',out/sub,'--mode','instant')
    run(ROOT/'scripts/export_illustrator.py','--output-dir',out)
    import pymupdf
    audits=[]
    for pdf in out.glob('*.pdf'):
        with pymupdf.open(pdf) as doc:
            raster=sum(len(p.get_images()) for p in doc)
            if len(doc)!=1 or raster: raise RuntimeError('Unexpected PDF content: '+str(pdf))
            audits.append(dict(file=pdf.name,pages=len(doc),raster_images=raster))
    (out/'pdf_audit.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
    if args.update_baseline:
        audit=json.loads((out/'geometry_audit.json').read_text('utf-8'))
        audit['current_output_dir']=out.name
        (ROOT/'data'/'reference_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
        print('baseline recorded:',out.name)
    print('Completed:',out)

if __name__=='__main__': main()
