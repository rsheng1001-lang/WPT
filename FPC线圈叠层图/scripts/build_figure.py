"""Reference-inspired, editable SVG artwork for the Illustrator skill.

Run with the scientific-illustrator-agent virtualenv. Original outputs are kept.
Copper strokes are buffered BEFORE projection, preserving actual line widths.
"""
from pathlib import Path
import csv
import json
import math
import argparse
import hashlib
from html import escape
from collections import Counter
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union
from shapely import make_valid
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'data'
parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', required=True)
ARGS = parser.parse_args()
ARGS.coverlay = True
ARGS.visual_v4 = True
FIGURE_VERSION = 'v6'
OUT = ROOT / ARGS.output_dir
OUT.mkdir(parents=True, exist_ok=False)
GEOM = json.loads((BUILD / 'geom.json').read_text('utf-8'))
RAW = json.loads((BUILD / 'outline_contours.json').read_text('utf-8'))
OLD = json.loads((BUILD / 'component_templates.json').read_text('utf-8'))
MM = 72 / 25.4
ROWS = list(csv.DictReader(next((ROOT/'inputs').glob('PickAndPlace*.csv')).open(encoding='utf-16'), delimiter='\t'))

def polygons(g):
    if g.geom_type == 'Polygon':
        yield g
    elif hasattr(g, 'geoms'):
        for child in g.geoms:
            yield from polygons(child)

def clean(points):
    # The EDA contour walk traverses some edges twice; make_valid recovers
    # their enclosed area without interpreting double winding as a filled hole.
    return unary_union(list(polygons(make_valid(Polygon(points)))))

BOARD = clean(RAW['outer']['points'])
HOLES = [clean(h['points']) for h in RAW['holes']]
BOARD = BOARD.difference(unary_union(HOLES))
assert len(HOLES) == 8 and BOARD.is_valid

def pads(tag):
    result = []
    for points in GEOM[tag]['fills']:
        x0,y0,x1,y1 = Polygon(points).bounds
        w,h = x1-x0,y1-y0
        if len(points)<=5 and .30 <= min(w,h) and max(w,h)<=5:
            result.append(dict(x=(x0+x1)/2,y=(y0+y1)/2,w=w,h=h))
    return result

PADS = {s:pads(t) for s,t in [('T','L1_TOP'),('B','L4_BOTTOM')]}
def num(s): return float(s.replace('mm',''))

# Independently fit the translated y-flipped CSV against equal-sized chip pads.
votes = Counter()
pairs = {'T':[], 'B':[]}
for side, ps in PADS.items():
    for i,a in enumerate(ps):
        for b in ps[i+1:]:
            dx,dy=abs(a['x']-b['x']),abs(a['y']-b['y'])
            if min(dx,dy)>.05 or not 1.0<max(dx,dy)<2.7: continue
            if abs(a['w']-b['w'])>.05 or abs(a['h']-b['h'])>.05: continue
            pairs[side].append(((a['x']+b['x'])/2,(a['y']+b['y'])/2))
for r in ROWS:
    if r['Footprint'] not in ('C0201','R0201','C0402'): continue
    for x,y in pairs[r['Layer']]:
        votes[(round((x-num(r['Mid X'])*MM)/.05),round((y+num(r['Mid Y'])*MM)/.05))]+=1
(bx,by),nv=votes.most_common(1)[0]
origin0=(bx*.05,by*.05)
fits=[]
for r in ROWS:
    if r['Footprint'] not in ('C0201','R0201','C0402'): continue
    dx,dy=num(r['Mid X'])*MM,-num(r['Mid Y'])*MM
    px,py=min(pairs[r['Layer']],key=lambda p:math.hypot(p[0]-dx-origin0[0],p[1]-dy-origin0[1]))
    if math.hypot(px-dx-origin0[0],py-dy-origin0[1])<.15: fits.append((px-dx,py-dy))
ORIGIN=tuple(sum(p[k] for p in fits)/len(fits) for k in (0,1))
COMPS=[]
oldmap={c['ref']:c for c in OLD}
for r in ROWS:
    c=dict(oldmap[r['Designator']])
    c['x']=ORIGIN[0]+num(r['Mid X'])*MM
    c['y']=ORIGIN[1]-num(r['Mid Y'])*MM
    near=sorted(PADS[r['Layer']],key=lambda p:math.hypot(p['x']-c['x'],p['y']-c['y']))[:int(r['Pins'])]
    c['own_pads']=[dict(x=p['x']-c['x'],y=p['y']-c['y'],w=p['w'],h=p['h']) for p in near]
    COMPS.append(c)
(OUT/'components_registered.json').write_text(json.dumps(COMPS,indent=2),'utf-8')

COPPERS={}
for tag,d in GEOM.items():
    pieces=[LineString(p).buffer(w/2,quad_segs=8) for p,w in zip(d['polylines'],d['widths']) if len(p)>1]
    pieces += [clean(p) for p in d['fills'] if len(p)>2]
    COPPERS[tag]=unary_union(pieces)

COVERLAYS = {}
COVERLAY_AUDIT = {}
if ARGS.coverlay:
    for name, tag in [('TOP_COVERLAY','L1_TOP'),('BOTTOM_COVERLAY','L4_BOTTOM')]:
        candidates=[]
        excluded_vias=0
        for points in GEOM[tag]['fills']:
            g=clean(points)
            if g.is_empty: continue
            x0,y0,x1,y1=g.bounds
            w,h=x1-x0,y1-y0
            # Through vias are tented by the coverlay, so they get no window.
            # Boards shipped so far use 1.56-1.73 pt round markers; pad windows
            # are rectangles or curved pads, never this small and square.
            if len(points)>=30 and abs(w-h)<.08 and 1.4<w<2.0:
                excluded_vias+=1
                continue
            if g.intersects(BOARD): candidates.append(g)
        windows=unary_union([g.buffer(.1*MM,quad_segs=12) for g in candidates]).intersection(BOARD)
        film=BOARD.difference(windows)
        assert film.is_valid and not film.is_empty
        assert film.intersection(windows).area<1e-7
        assert film.union(windows).symmetric_difference(BOARD).area<1e-7
        COVERLAYS[name]=film
        COVERLAY_AUDIT[name]=dict(source=tag,pad_candidates=len(candidates),excluded_via_markers=excluded_vias,
            merged_window_regions=len(list(polygons(windows))),expansion_mm=.1,derived=True,
            nominal_pi_um=12.5,nominal_adhesive_um=15,opacity=1.0,
            window_area_mm2=windows.area/MM**2,remaining_film_area_mm2=film.area/MM**2,
            valid=True,window_overlap_area_mm2=film.intersection(windows).area/MM**2)
        (OUT/(name+'_windows.json')).write_text(json.dumps(dict(source=tag,derived=True,expansion_mm=.1,
            geometry=windows.__geo_interface__),indent=2),'utf-8')

def pathdata(g,tf):
    result=[]
    for p in polygons(g):
        p=orient(p,sign=1)
        for ring in [p.exterior,*p.interiors]:
            pts=[tf(x,y) for x,y in ring.coords]
            result.append('M'+' L'.join(f'{x:.3f},{y:.3f}' for x,y in pts)+' Z')
    return ' '.join(result)

def path(g,tf,fill,stroke='none',sw=.3,extra=''):
    return f'<path d="{pathdata(g,tf)}" fill="{fill}" fill-rule="evenodd" stroke="{stroke}" stroke-width="{sw}" {extra}/>'

def text(x,y,value,size=13,color='#303238',weight='normal'):
    return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(value)}</text>'

def line(x,y,xx,yy,col='#A0A2A5',sw=.65):
    return f'<path d="M{x},{y} L{xx},{yy}" fill="none" stroke="{col}" stroke-width="{sw}"/>'

DEFS='''<defs>
<linearGradient id="copper" x1="0" y1="0" x2="0.3" y2="1"><stop offset="0" stop-color="#A57548"/><stop offset="0.43" stop-color="#DEC29C"/><stop offset="1" stop-color="#A16D3E"/></linearGradient>
<linearGradient id="copperInner" x1="0" y1="0" x2="0.3" y2="1"><stop offset="0" stop-color="#8B5D32"/><stop offset="0.43" stop-color="#C9A87E"/><stop offset="1" stop-color="#875729"/></linearGradient>
<linearGradient id="coverlay" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#EDE7D3"/><stop offset="1" stop-color="#DCD2B2"/></linearGradient>
<linearGradient id="film" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F7F1CF"/><stop offset="1" stop-color="#E7D99C"/></linearGradient>
<linearGradient id="core" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F1E6B5"/><stop offset="1" stop-color="#DCC986"/></linearGradient>
<linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F6F5F1"/><stop offset="0.55" stop-color="#B8BCC0"/><stop offset="1" stop-color="#7E858B"/></linearGradient>
<linearGradient id="ceramic" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E8DECB"/><stop offset="1" stop-color="#BDB09A"/></linearGradient>
<linearGradient id="package" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#575C60"/><stop offset="1" stop-color="#292E32"/></linearGradient>
</defs>'''

def header(w,h):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}pt" height="{h}pt" viewBox="0 0 {w} {h}">{DEFS}'

def component(c,tf,scale):
    x,y=c['x'],c['y']
    a,b=[v*MM for v in c['body']]
    w,h=(a,b) if c['board_axis']=='x' else (b,a)
    body=box(x-w/2,y-h/2,x+w/2,y+h/2)
    rise=c['height_mm']*MM*scale*.19
    top=lambda u,v:(tf(u,v)[0],tf(u,v)[1]-rise)
    out=[]
    # Pin geometry follows measured pads rather than fixed guessed lead rows.
    if c['kind']=='ic':
        for p in c['own_pads']:
            px,py=x+p['x'],y+p['y']
            if abs(p['x'])>w/2:
                lead=box(min(px,x+math.copysign(w*.45,p['x'])),py-min(p['h'],.75)/2,max(px,x+math.copysign(w*.45,p['x'])),py+min(p['h'],.75)/2)
            else:
                lead=box(px-min(p['w'],.75)/2,min(py,y+math.copysign(h*.45,p['y'])),px+min(p['w'],.75)/2,max(py,y+math.copysign(h*.45,p['y'])))
            out.append(path(lead,tf,'url(#metal)','#81878C',.22))
    # Low front wall gives depth without hiding adjoining packages.
    pts=[tf(x-w/2,y+h/2),tf(x+w/2,y+h/2),top(x+w/2,y+h/2),top(x-w/2,y+h/2)]
    out.append('<polygon points="'+' '.join(f'{u:.3f},{v:.3f}' for u,v in pts)+'" fill="#73716B"/>')
    fill='url(#ceramic)' if c['ref'].startswith('C') else 'url(#package)'
    out.append(path(body,top,fill,'#666B6D',.25))
    if c['kind']!='ic':
        if c['board_axis']=='x':
            caps=[box(x-w/2,y-h/2,x-w*.29,y+h/2),box(x+w*.29,y-h/2,x+w/2,y+h/2)]
        else:
            caps=[box(x-w/2,y-h/2,x+w/2,y-h*.29),box(x-w/2,y+h*.29,x+w/2,y+h/2)]
        out.extend(path(p,top,'url(#metal)') for p in caps)
    if c['kind']=='diode' and c['cathode']:
        dx,dy=c['cathode']
        if c['board_axis']=='x':
            k=x+math.copysign(w*.19,dx)
            stripe=box(k-w*.04,y-h/2,k+w*.04,y+h/2)
        else:
            k=y+math.copysign(h*.19,dy)
            stripe=box(x-w/2,k-h*.04,x+w/2,k+h*.04)
        out.append(path(stripe,top,'#DBDFDF'))
    return '<g id="'+c['ref']+'">'+''.join(out)+'</g>'

TOP_N=sum(1 for c in COMPS if c['layer']=='TOP_COMPONENTS')
BOT_N=sum(1 for c in COMPS if c['layer']=='BOTTOM_COMPONENTS')
CAP_N=sum(1 for c in COMPS if c['ref'].startswith('C'))
RES_N=sum(1 for c in COMPS if c['ref'].startswith('R'))
DIO_N=sum(1 for c in COMPS if c['kind']=='diode')
TRA_N=sum(1 for c in COMPS if c['ref'].startswith('Q'))
IC_N=sum(1 for c in COMPS if c['ref'].startswith('U'))
def plural(n,word): return f'{n} {word}'+('' if n==1 else 's')
INVENTORY=(f'{plural(CAP_N,"capacitor")} · {plural(RES_N,"resistor")} · '
           f'{plural(DIO_N,"diode")} · {plural(TRA_N,"transistor")} · '
           f'{IC_N} U-designated devices')

STACK=[('TOP_COMPONENTS',None,75,'Top components',f'{TOP_N} placed devices'),
       ('L1_TOP_COPPER','L1_TOP',142,'L1 · Top copper','Planar coil + interconnects'),
       ('DIELECTRIC_1',None,215,'Polyimide film','25 µm nominal'),
       ('L2_GND','L2_GND',286,'L2 · Ground copper','Actual central routing'),
       ('CORE',None,357,'Polyimide core','50 µm nominal'),
       ('L3_POWER','L3_POWER',428,'L3 · Power copper','Actual central routing'),
       ('DIELECTRIC_2',None,499,'Polyimide film','25 µm nominal'),
       ('L4_BOTTOM_COPPER','L4_BOTTOM',572,'L4 · Bottom copper','Planar coil + interconnects'),
       ('BOTTOM_COMPONENTS',None,639,'Bottom components',f'{BOT_N} placed devices')]
if ARGS.coverlay:
    STACK=[(n,t,y+(142 if n=='BOTTOM_COMPONENTS' else 71 if n!='TOP_COMPONENTS' else 0),l,s) for n,t,y,l,s in STACK]
    STACK.insert(1,('TOP_COVERLAY',None,146,'Coverlay PI','12.5+15um nominal'))
    STACK.insert(-1,('BOTTOM_COVERLAY',None,710,'Coverlay PI','12.5+15um nominal'))
    assert [s[0] for s in STACK][0:3]==['TOP_COMPONENTS','TOP_COVERLAY','L1_TOP_COPPER']
    assert [s[0] for s in STACK][-3:]==['L4_BOTTOM_COPPER','BOTTOM_COVERLAY','BOTTOM_COMPONENTS']
if ARGS.visual_v4:
    STACK=[(n,t,85+i*102,l,s) for i,(n,t,y,l,s) in enumerate(STACK)]
SCALE=4.45
TILT=.32
CX,CY=ORIGIN
def projection(y0):
    return lambda x,y:(219+(x-CX)*SCALE-.13*(y-CY)*SCALE,y0+(y-CY)*SCALE*TILT)

HEIGHT=910 if ARGS.coverlay else 745
if ARGS.visual_v4: HEIGHT=1236
parts=[header(690,HEIGHT),f'<g id="BACKGROUND"><rect width="690" height="{HEIGHT}" fill="white"/></g>']
parts.append('<g id="TITLE">'+text(34,28,'Four-layer receiver FPC',15,weight='bold')+text(34,47,'Exploded assembly',10,'#777C80')+'</g>')
for name,tag,y0,label,sub in reversed(STACK):
    tf=projection(y0)
    group=[]
    if tag:
        # Inner layers carry little copper and read faint at reduced sizes;
        # a slightly deeper copper keeps their routing legible next to L1/L4.
        copper_fill='url(#copperInner)' if tag in ('L2_GND','L3_POWER') else 'url(#copper)'
        group.append(path(COPPERS[tag],tf,copper_fill))
    elif name in COVERLAYS:
        film=COVERLAYS[name]
        if ARGS.visual_v4:
            # A presentation-only pale backing lowers window contrast. The
            # original perforated film path and saved window geometry are exact.
            group.append('<g id="'+name+'_WINDOW_VISUAL_TINT">'+path(BOARD,tf,'#F6F4EB')+'</g>')
            group.append(path(film,tf,'url(#coverlay)',extra='opacity="1"'))
            # Outline only board/cut-outs, not every small pad window.
            group.append(path(BOARD,tf,'none','#CBC3A8',.35))
        else:
            group.append(path(film,lambda x,y:(tf(x,y)[0],tf(x,y)[1]+1.1),'#A89048',extra='opacity="1"'))
            group.append(path(film,tf,'#C9B36F','#AE9753',.35,extra='opacity="1"'))
    elif 'COMPONENTS' in name:
        for c in sorted((c for c in COMPS if c['layer']==name),key=lambda c:c['y']):
            group.append(component(c,tf,SCALE))
    else:
        thickness=2.0 if name=='CORE' else 1.0
        group.append(path(BOARD,lambda x,y:(tf(x,y)[0],tf(x,y)[1]+thickness),'#CCB779'))
        group.append(path(BOARD,tf,'url(#core)' if name=='CORE' else 'url(#film)','#C6B77E',.45))
    parts.append(f'<g id="{name}">'+''.join(group)+'</g>')
ann=[]
for name,tag,y0,label,sub in STACK:
    # Leaders begin near each actual layer, not at one arbitrary common edge.
    start=322 if 'COMPONENTS' in name else (306 if tag in ('L2_GND','L3_POWER') else 404)
    if ARGS.visual_v4: start=416
    ann.append(line(start,y0,444,y0,'#7D8387',.6))
    ann.append(text(456,y0+4,label,14))
    ann.append(text(456,y0+21,sub,9,'#82868A'))
    if name in COVERLAYS:
        ann.append(text(456,y0+35,'Pad windows: derived (+0.1 mm)',9,'#82868A'))
        if ARGS.visual_v4:
            ann.append(text(456,y0+48,'Full openings in detail view',8,'#929697'))
FOOTER=HEIGHT-(76 if ARGS.coverlay else 54)
ann.append(line(34,FOOTER,656,FOOTER,'#D9DCDD',.6))
summary=f'4 copper / 3 internal PI / 2 coverlay / {len(COMPS)} components / {len(HOLES)} board cut-outs' if ARGS.coverlay else '4 copper layers  /  3 PI layers  /  41 components  /  8 cut-outs'
ann.append(text(34,FOOTER+20,summary,10,'#51575A'))
ann.append(text(34,FOOTER+38,'Layer separation and package heights are schematic. PI thicknesses follow the existing design brief.',8,'#85898C'))
if ARGS.coverlay:
    foot='Coverlay windows: derived (+0.1 mm); contrast softened here. Complete openings in detail view.' if ARGS.visual_v4 else 'Coverlay windows: derived from copper pads with 0.1 mm expansion; not a fabrication mask.'
    ann.append(text(34,FOOTER+55,foot,8,'#85898C'))
parts.append('<g id="ANNOTATIONS">'+''.join(ann)+'</g></svg>')
(OUT/'WPT_Exploded_Refined.svg').write_text(''.join(parts),'utf-8')

# A separate companion sheet expands detail without crowding the main figure.
DETAIL_HEIGHT=890 if ARGS.visual_v4 else 540
p=[header(900,DETAIL_HEIGHT),f'<g id="BACKGROUND"><rect width="900" height="{DETAIL_HEIGHT}" fill="white"/></g>']
p.append('<g id="HEAD">'+text(30,30,'Receiver FPC · geometry and component detail',17,weight='bold')+text(30,51,'Orthographic views from the supplied EDA exports and placement file',10,'#777C80')+'</g>')
views=[('Top copper + components','L1_TOP','TOP_COMPONENTS',158),('Bottom copper + components','L4_BOTTOM','BOTTOM_COMPONENTS',450),('Board outline + cut-outs',None,None,742)]
for title,tag,side,ox in views:
    tf=lambda x,y,ox=ox:(ox+(x-CX)*2.95,222+(y-CY)*2.95)
    group=[text(ox-126,88,title,12,weight='bold'),path(BOARD,tf,'#FBF7E5','#D0C593',.6)]
    if tag:
        group.append(path(COPPERS[tag],tf,'#BB9064'))
        for c in sorted((c for c in COMPS if c['layer']==side),key=lambda c:c['y']):group.append(component(c,tf,2.95))
    else:
        group.append(text(ox-120,370,'8 cut-outs; outline taken from Multi-Layer export',9,'#757B7F'))
    p.append('<g id="'+(tag or 'OUTLINE')+'">'+''.join(group)+'</g>')
if ARGS.visual_v4:
    for name,ox,title in [('TOP_COVERLAY',235,'Top coverlay · full derived openings'),('BOTTOM_COVERLAY',665,'Bottom coverlay · full derived openings')]:
        tf=lambda x,y,ox=ox:(ox+(x-CX)*3.25,562+(y-CY)*3.25)
        p.append('<g id="'+name+'_DETAIL">'+text(ox-170,414,title,13,weight='bold')+
            path(COVERLAYS[name],tf,'#E6DFC7','#A99E7D',.45)+
            text(ox-170,725,'Pad expansion: 0.1 mm · derived · nominal PI 12.5+15um',9,'#737A7E')+'</g>')
dy=350 if ARGS.visual_v4 else 0
p.append('<g id="NOTES">'+line(30,400+dy,870,400+dy,'#D9DCDD')+text(30,428+dy,'Placement inventory',12,weight='bold')+text(30,450+dy,INVENTORY,11)+text(30,476+dy,'Body sizes follow package definitions; positions and rotations follow the placement CSV.',10,'#737A7E')+text(30,496+dy,'Existing FPC stack only; no outer encapsulation, as confirmed by the designer.',10,'#737A7E')+text(30,516+dy,'Copper line widths are projected as filled outlines, keeping coil gaps visible at oblique viewing angles.',10,'#737A7E')+'</g></svg>')
(OUT/'WPT_Geometry_Details.svg').write_text(''.join(p),'utf-8')
audit=dict(origin_pt=ORIGIN,registration_votes=nv,chip_pairs_matched=len(fits),chip_fit_max_error_mm=max(math.dist(p,ORIGIN) for p in fits)/MM,
           old_origin_pt=[38.85,38.85],old_to_new_shift_mm=[(v-38.85)/MM for v in ORIGIN],components=len(COMPS),cutouts=len(HOLES),tilt=TILT,scale=SCALE,
           copper_layers={k:dict(polylines=len(v['polylines']),fills=len(v['fills'])) for k,v in GEOM.items()})
if ARGS.coverlay:
    audit.update(coverlay=COVERLAY_AUDIT,stack_top_to_bottom=[s[0] for s in STACK],reference_designators_drawn=False,
                 outline_source='data/outline_contours.json',coverlay_color='#C9B36F')
if ARGS.visual_v4:
    names=['components_registered.json','TOP_COVERLAY_windows.json','BOTTOM_COVERLAY_windows.json']
    hashes={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in names}
    baseline=json.loads((BUILD/'reference_audit.json').read_text('utf-8'))
    recorded=(baseline.get('data_comparison') or {}).get(FIGURE_VERSION)
    if recorded:
        for n in names:
            assert recorded[n]['sha256']==hashes[n], f'Unexpected data change: {n}'
        assert audit['coverlay']==baseline['coverlay'], 'coverlay audit changed'
        assert audit['copper_layers']==baseline['copper_layers'], 'copper audit changed'
        checks={n:dict(previous_sha256=recorded[n]['sha256'],sha256=hashes[n],identical=True) for n in names}
        print(f'baseline check: {FIGURE_VERSION} data identical to the recorded baseline')
    else:
        checks={n:dict(sha256=hashes[n],baseline='recorded from this build') for n in names}
        print(f'baseline check: no recorded baseline for {FIGURE_VERSION}; recording this build')
    audit.update(figure_version=FIGURE_VERSION,data_comparison=checks,
        coverlay_color='url(#coverlay) gradient #EDE7D3->#DCD2B2',
        copper_fill='url(#copper) #A57548->#DEC29C->#A16D3E',
        inner_copper_fill='url(#copperInner) #8B5D32->#C9A87E->#875729 (L2/L3 legibility)',
        layer_pitch_pt=102,layer_centers_pt={s[0]:s[2] for s in STACK},
        visual_window_backing_color='#F6F4EB',main_window_treatment='exact film geometry with removable low-contrast visual backing; no window-edge strokes',
        detail_window_treatment='complete true cut-outs, no backing')
(OUT/'geometry_audit.json').write_text(json.dumps(audit,indent=2),'utf-8')
print(json.dumps(audit,indent=2))
