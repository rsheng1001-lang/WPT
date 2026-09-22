"""Preserve portrait v6 and compose a landscape paper figure from its vectors."""
from pathlib import Path
import copy
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import argparse

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--source',default='optimized_v6',help='directory holding the full portrait figure')
parser.add_argument('--output-dir',required=True)
args=parser.parse_args()
SRC=ROOT/args.source
OUT=ROOT/args.output_dir
OUT.mkdir(exist_ok=False)
(OUT/'portrait').mkdir()
(OUT/'landscape').mkdir()
NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)
def el(name,attrs=None): return ET.Element('{'+NS+'}'+name,attrs or {})
def addtext(parent,x,y,value,size=15,weight='normal',color='#303238'):
    n=ET.SubElement(parent,'{'+NS+'}text',{'x':str(x),'y':str(y),'font-family':'Arial','font-size':str(size),'font-weight':weight,'fill':color})
    n.text=value
    return n

portrait={}
for ext in ['ai','pdf','svg','png']:
    f='WPT_Exploded_Refined.'+ext
    shutil.copy2(SRC/f,OUT/'portrait'/f)
    a=hashlib.sha256((SRC/f).read_bytes()).hexdigest()
    b=hashlib.sha256((OUT/'portrait'/f).read_bytes()).hexdigest()
    assert a==b
    portrait[f]=a
main=ET.parse(SRC/'WPT_Exploded_Refined.svg').getroot()
detail=ET.parse(SRC/'WPT_Geometry_Details.svg').getroot()
audit=json.loads((SRC/'geometry_audit.json').read_text('utf-8'))
groups={g.get('id'):g for g in main if g.tag.endswith('}g')}
detailgroups={g.get('id'):g for g in detail if g.tag.endswith('}g')}
PAGE_WIDTH=180/25.4*72
r=el('svg',{'version':'1.1','width':'1000pt','height':'750pt','viewBox':'0 0 1000 750'})
defs=copy.deepcopy(main.find('{'+NS+'}defs'))
r.append(defs)
bg=el('g',{'id':'BACKGROUND'});bg.append(el('rect',{'width':'1000','height':'750','fill':'white'}));r.append(bg)
titles=el('g',{'id':'PANEL_TITLES'})
addtext(titles,20,28,'a',22,'bold');addtext(titles,48,28,'FPC layer architecture',18,'bold')
addtext(titles,520,28,'b',22,'bold');addtext(titles,550,28,'Top-side circuit detail',18,'bold')
addtext(titles,520,377,'c',22,'bold');addtext(titles,550,377,'Bottom-side circuit detail',18,'bold')
r.append(titles)
centers=[65,120,199,278,331,384,437,490,569,648,701]
scale=.65
stack=audit['stack_top_to_bottom']
geometry_checks={}
for name,cy in reversed(list(zip(stack,centers))):
    original=groups[name]
    g=el('g',{'id':name})
    item=copy.deepcopy(original)
    item.set('transform',f'translate(16 {cy-scale*audit["layer_centers_pt"][name]}) scale({scale})')
    g.append(item);r.append(g)
    original_d=[e.get('d') for e in original.iter() if e.tag.endswith('}path')]
    copied_d=[e.get('d') for e in item.iter() if e.tag.endswith('}path')]
    assert original_d==copied_d
    geometry_checks[name]=dict(path_data_unchanged=True,uniform_scale=scale,center_y=cy)
labels=['Top components','Coverlay','L1 · Top copper','PI film · 25 µm','L2 · Ground','PI core · 50 µm','L3 · Power','PI film · 25 µm','L4 · Bottom copper','Coverlay','Bottom components']
ann=el('g',{'id':'ANNOTATIONS'})
for name,cy,label in zip(stack,centers,labels):
    ann.append(el('path',{'d':f'M286,{cy} L309,{cy}','stroke':'#969C9E','stroke-width':'.65','fill':'none'}))
    addtext(ann,319,cy+5,label,15)
    if name.endswith('COVERLAY'): addtext(ann,319,cy+22,'PI 12.5 + adhesive 15 µm',14,color='#656B6F')
r.append(ann)

# Genuine orthographic detail from the same artwork; clip without deleting data.
DETAIL_SCALE=2.4
for tag,ox,cy,clip_y in [('L1_TOP',158,196,57),('L4_BOTTOM',450,548,409)]:
    clip=ET.SubElement(defs,'{'+NS+'}clipPath',{'id':'clip_'+tag,'clipPathUnits':'userSpaceOnUse'})
    clip.append(el('rect',{'x':'526','y':str(clip_y),'width':'446','height':'282'}))
    g=el('g',{'id':'DETAIL_'+tag})
    frame=el('g',{'clip-path':f'url(#clip_{tag})'})
    original=copy.deepcopy(detailgroups[tag])
    for child in list(original):
        if child.tag.endswith('}text'):original.remove(child)
    original.set('transform',f'translate({749-ox*DETAIL_SCALE} {cy-222*DETAIL_SCALE}) scale({DETAIL_SCALE})')
    frame.append(original);g.append(frame)
    g.append(el('rect',{'x':'526','y':str(clip_y),'width':'446','height':'282','fill':'none','stroke':'#D8DCDE','stroke-width':'.65'}))
    # Scale from native PDF pt -> orthographic plotting scale -> inset scale.
    bar_length=2*(72/25.4)*2.95*DETAIL_SCALE
    bar_y=clip_y+298
    g.append(el('path',{'d':f'M{962-bar_length},{bar_y} L962,{bar_y}','stroke':'#3D4448','stroke-width':'2','fill':'none'}))
    addtext(g,962-bar_length-40,bar_y+4,'2 mm',14,color='#50565A')
    r.append(g)
foot=el('g',{'id':'FIGURE_NOTES'})
addtext(foot,20,737,'Schematic spacing; nominal thicknesses.',14,color='#656B6F')
addtext(foot,520,737,'Derived coverlay windows; see caption.',14,color='#656B6F')
r.append(foot)
ET.ElementTree(r).write(OUT/'landscape/WPT_Exploded_Refined.svg',encoding='utf-8',xml_declaration=True)
caption='''Figure. Architecture and circuit layout of the four-layer receiver FPC. (a) Exploded assembly with four copper layers, three internal polyimide layers, two coverlays and 32 components (21 top, 11 bottom). (b,c) Enlarged central crops of the top- and bottom-side orthographic circuit views; these panels are independently magnified and are not to the same scale as panel a. Geometry and placement are inherited from the 2026-09-20 EDA exports. PI and adhesive thicknesses are nominal. Coverlay windows are derived from copper pad candidates expanded by 0.1 mm; contrast is reduced in panel a for clarity. Complete coverlay openings remain available in the geometry detail sheet. Layer spacing and package heights are schematic.\n'''
(OUT/'figure_caption.txt').write_text(caption,'utf-8')
(OUT/'layout_audit.json').write_text(json.dumps(dict(source=args.source,portrait_sha256=portrait,landscape_geometry=geometry_checks,
    landscape_viewbox=[1000,750],landscape_canvas_mm=[180,135],minimum_font_pt=14*PAGE_WIDTH/1000,
    detail_scale=DETAIL_SCALE,detail_scale_bar_mm=2,detail_scale_bar_viewbox_length=bar_length,
    detail_views='clipped orthographic source vectors; no geometry edits',reference_designators=False),indent=2),'utf-8')
print(OUT)
