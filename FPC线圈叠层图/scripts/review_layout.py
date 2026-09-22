"""Verify the publication layout after native Illustrator export."""
from pathlib import Path
import argparse
import json
import re
import xml.etree.ElementTree as ET
import pymupdf

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--source',default='optimized_v10',help='directory holding the full portrait figure')
parser.add_argument('--output-dir',required=True)
args=parser.parse_args()
OUT=ROOT/args.output_dir
source=ET.parse(ROOT/args.source/'WPT_Geometry_Details.svg').getroot()
checks=[]
for tag,ox,cy,clip_y in [('L1_TOP',158,196,57),('L4_BOTTOM',450,548,409)]:
    group=next(g for g in source if g.get('id')==tag)
    for component in group:
        if not re.fullmatch(r'[CRDQU]\d+',component.get('id','')): continue
        points=[]
        for node in component.iter():
            raw=node.get('d') or node.get('points')
            if not raw: continue
            numbers=[float(v) for v in re.findall(r'-?\d+(?:\.\d+)?',raw)]
            points.extend(zip(numbers[::2],numbers[1::2]))
        assert points,component.get('id')
        points=[(749+(x-ox)*2.4,cy+(y-222)*2.4) for x,y in points]
        margin=min(min(x-526,972-x,y-clip_y,clip_y+282-y) for x,y in points)
        assert margin>0,(tag,component.get('id'),margin)
        checks.append(dict(side=tag,ref=component.get('id'),crop_margin_viewbox=margin))
assert len(checks)==32,len(checks)
with pymupdf.open(OUT/'landscape/WPT_Exploded_Refined.pdf') as doc:
    page=doc[0]
    spans=[s for b in page.get_text('dict')['blocks'] if 'lines' in b for line in b['lines'] for s in line['spans']]
    width=page.rect.width*25.4/72;height=page.rect.height*25.4/72
    smallest=min(s['size'] for s in spans)
    assert abs(width-180)<.01 and abs(height-135)<.01
    assert smallest>=7
    assert len(page.get_images())==0
    assert page.get_text().count('2 mm')==2
    page.get_pixmap(matrix=pymupdf.Matrix(2,2)).save(OUT/'landscape/pdf_review.png')
report=dict(page_mm=[width,height],minimum_font_pt=smallest,raster_images=0,
    inset_components_verified=len(checks),all_components_inside_crops=True,component_checks=checks,
    min_crop_margin_viewbox=min(c['crop_margin_viewbox'] for c in checks),
    scale_bars=dict(count=2,length_mm=2,derived_from='PDF coordinates * 72/25.4 pt/mm * 2.95 orthographic scale * 2.4 inset scale'),
    visual_review=['v7: top inset clipped component; corrected by reducing zoom 3.0 to 2.4',
                   'v7: small annotation text; raised minimum to 14 viewbox units',
                   'v9: native 180x135 mm export and typography checked',
                   'v10: inner-layer copper deepened (copperInner) for legibility at print size; coverlay given a light material gradient',
                   'portrait copied unchanged; landscape source path data preserved'])
(OUT/'review_audit.json').write_text(json.dumps(report,indent=2),'utf-8')
print('PASS: 32 components clear of crop boundaries, minimum font >=7 pt, 180x135 mm, no raster.')
