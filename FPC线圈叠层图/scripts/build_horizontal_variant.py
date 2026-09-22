"""Compose a horizontal (rotated 90 degrees) exploded layout from the portrait figure.

The full figure is a vertical stack: the 11 layers march top to bottom.  This
variant keeps the artwork untouched and rotates every layer group by -90
degrees about its own station, so the stack marches left to right while each
layer keeps exactly the tilt/rise relationship it has in the portrait version.
Text (title, per-layer labels, footer) is placed fresh and stays upright.

Usage:
    python build_horizontal_variant.py --source optimized_v10 --output-dir optimized_v10_horizontal
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)

# Publication figure at the usual double-column width.  Eleven columns at the
# portrait artwork scale would push the smallest text below 7 pt at 180 mm, so
# the artwork is uniformly reduced (ART) together with the column pitch while
# the text keeps its point size.
ART = 0.68             # artwork scale inside the composition
PITCH = 100.0 * ART    # pt between layer centres (portrait pitch, reduced)
X_FIRST = 47.0
REF_X = 219.0          # board centre x in the source projection

# After the -90 deg rotation the board length (board width x source SCALE) runs
# vertically, so each station needs half of it above and below the lane.
SOURCE_SCALE = 4.45    # build_figure.py SCALE, recorded in the source audit
BOARD_WIDTH_PT = 78.48
HALF_V = BOARD_WIDTH_PT * SOURCE_SCALE * ART / 2.0     # ~115 pt
TITLE_BAND = 62.0      # title text block above the first disc
LANE_Y = TITLE_BAND + HALF_V + 8.0
LABEL_SIZE = 12.0
SUBLABEL_SIZE = 11.0
LINE_LEAD = 14.0
FOOT_SIZE = 12.0
FOOT_NOTE_SIZE = 11.0
TICK_TOP = LANE_Y + HALF_V + 6.0
ROW_A_END = TICK_TOP + 14.0
ROW_B_END = ROW_A_END + 26.0
FOOT_Y = ROW_B_END + 62.0
X_LAST = X_FIRST + 10 * PITCH
WIDTH = X_LAST + X_FIRST + 20.0                        # ~794 pt
HEIGHT = FOOT_Y + 48.0                                 # ~447 pt
EXPORT_WIDTH_MM = 180.0
PAGE_WIDTH = EXPORT_WIDTH_MM / 25.4 * 72   # exported canvas width in pt
assert SUBLABEL_SIZE * PAGE_WIDTH / WIDTH >= 7.0, 'smallest text below 7 pt at this export width'

# Labels are pre-wrapped: at the 180 mm paper width a column is ~17 mm wide, so
# each line stays under eleven characters and the stack reads line by line.
LABELS = {
    'TOP_COMPONENTS': ('Top|components', '21 devices'),
    'TOP_COVERLAY': ('Coverlay', '12.5+15 um'),
    'L1_TOP_COPPER': ('L1 · Top|copper', 'Planar coil'),
    'DIELECTRIC_1': ('PI film', '25 um'),
    'L2_GND': ('L2 ·|Ground', 'routing'),
    'CORE': ('PI core', '50 um'),
    'L3_POWER': ('L3 ·|Power', 'routing'),
    'DIELECTRIC_2': ('PI film', '25 um'),
    'L4_BOTTOM_COPPER': ('L4 ·|Bottom|copper', 'Planar coil'),
    'BOTTOM_COVERLAY': ('Coverlay', '12.5+15 um'),
    'BOTTOM_COMPONENTS': ('Bottom|components', '11 devices'),
}


def el(name, attrs=None):
    return ET.Element('{' + NS + '}' + name, attrs or {})


def add_text(parent, x, y, value, size=15, weight='normal', color='#303238', anchor=None):
    attrs = {'x': str(x), 'y': str(y), 'font-family': 'Arial',
             'font-size': str(size), 'font-weight': weight, 'fill': color}
    if anchor:
        attrs['text-anchor'] = anchor
    node = ET.SubElement(parent, '{' + NS + '}text', attrs)
    node.text = value
    return node


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default='optimized_v10')
    ap.add_argument('--output-dir', required=True)
    args = ap.parse_args()
    src = ROOT / args.source
    out = ROOT / args.output_dir
    out.mkdir(exist_ok=False)

    audit = json.loads((src / 'geometry_audit.json').read_text('utf-8'))
    comps = json.loads((src / 'components_registered.json').read_text('utf-8'))
    counts = {}
    for c in comps:
        counts[c['layer']] = counts.get(c['layer'], 0) + 1

    main_svg = ET.parse(src / 'WPT_Exploded_Refined.svg').getroot()
    groups = {g.get('id'): g for g in main_svg if g.tag.endswith('}g')}
    stack = audit['stack_top_to_bottom']
    centers = audit['layer_centers_pt']

    root = el('svg', {'version': '1.1', 'width': f'{WIDTH}pt', 'height': f'{HEIGHT}pt',
                      'viewBox': f'0 0 {WIDTH} {HEIGHT}'})
    defs = main_svg.find('{' + NS + '}defs')
    if defs is not None:
        root.append(copy.deepcopy(defs))
    bg = el('g', {'id': 'BACKGROUND'})
    bg.append(el('rect', {'width': str(WIDTH), 'height': str(HEIGHT), 'fill': 'white'}))
    root.append(bg)

    title = el('g', {'id': 'TITLE'})
    add_text(title, 34, 34, 'Four-layer receiver FPC', 16, 'bold')
    add_text(title, 34, 55, 'Exploded assembly - horizontal arrangement', 11, '#777C80')
    root.append(title)

    # Draw order follows the source document (bottom-most layer first), so the
    # top components still end up in front of their neighbours.
    geometry_checks = {}
    for g in main_svg:
        gid = g.get('id')
        if not gid or gid not in centers:
            continue
        i = stack.index(gid)
        gx = X_FIRST + i * PITCH
        item = copy.deepcopy(g)
        item.tag = '{' + NS + '}g'
        item.set('transform',
                 f'translate({gx} {LANE_Y}) rotate(-90) scale({ART}) translate({-REF_X} {-centers[gid]})')
        root.append(item)
        original_d = [e.get('d') for e in g.iter() if e.tag.endswith('}path')]
        copied_d = [e.get('d') for e in item.iter() if e.tag.endswith('}path')]
        assert original_d == copied_d
        geometry_checks[gid] = dict(path_data_unchanged=True, rotation_deg=-90,
                                    artwork_scale=ART, column_x=gx, lane_y=LANE_Y,
                                    source_center_pt=centers[gid])

    # Two staggered label rows keep 11 columns readable at a 300 mm figure width.
    labels = el('g', {'id': 'LAYER_LABELS'})
    for gid in stack:
        i = stack.index(gid)
        gx = X_FIRST + i * PITCH
        row = i % 2                       # 0 = near row, 1 = far row
        name, sub = LABELS[gid]
        if gid.endswith('COMPONENTS'):
            sub = f"{counts.get(gid, 0)} devices"
        tick_end = ROW_A_END if row == 0 else ROW_B_END
        group = el('g', {'id': 'LABEL_' + gid})
        group.append(el('path', {'d': f'M{gx},{TICK_TOP:.1f} L{gx},{tick_end:.1f}',
                                 'stroke': '#C9CDCF', 'stroke-width': '.6', 'fill': 'none'}))
        y = tick_end + 12
        for line in name.split('|'):
            add_text(group, gx, y, line, LABEL_SIZE, 'normal', '#303238', 'middle')
            y += LINE_LEAD
        add_text(group, gx, y + 1, sub, SUBLABEL_SIZE, 'normal', '#82868A', 'middle')
        labels.append(group)
    root.append(labels)

    foot = el('g', {'id': 'FIGURE_NOTES'})
    summary = (f"4 copper / 3 internal PI / 2 coverlay / {len(comps)} components "
               f"({counts.get('TOP_COMPONENTS', 0)} top, {counts.get('BOTTOM_COMPONENTS', 0)} bottom) / 8 board cut-outs")
    root.append(foot)
    add_text(foot, 34, FOOT_Y, summary, FOOT_SIZE, 'normal', '#51575A')
    add_text(foot, 34, FOOT_Y + 19,
             'Layers run left to right, top side first. Layer spacing and package heights are schematic.',
             FOOT_NOTE_SIZE, 'normal', '#85898C')
    add_text(foot, 34, FOOT_Y + 35,
             'PI thicknesses nominal; coverlay windows derived from copper pads (+0.1 mm).',
             FOOT_NOTE_SIZE, 'normal', '#85898C')

    ET.ElementTree(root).write(out / 'WPT_Exploded_Refined.svg', encoding='utf-8', xml_declaration=True)
    layout = dict(source=args.source, style='horizontal (portrait rotated -90 degrees)',
                  layer_order_left_to_right=stack,
                  viewbox=[WIDTH, HEIGHT], export_width_mm=EXPORT_WIDTH_MM,
                  canvas_mm=[EXPORT_WIDTH_MM, round(EXPORT_WIDTH_MM * HEIGHT / WIDTH, 2)],
                  layer_pitch_pt=PITCH, lane_y_pt=LANE_Y,
                  label_size_pt=LABEL_SIZE, sublabel_size_pt=SUBLABEL_SIZE,
                  minimum_font_pt=min(SUBLABEL_SIZE, FOOT_NOTE_SIZE) * PAGE_WIDTH / WIDTH,
                  geometry=geometry_checks,
                  text_upright=True, label_rows=2,
                  notes='artwork path data copied unchanged; only station placement and text are new')
    (out / 'layout_audit.json').write_text(json.dumps(layout, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in layout.items() if k != 'geometry'}, indent=2))
    print('wrote', out / 'WPT_Exploded_Refined.svg')


if __name__ == '__main__':
    main()
