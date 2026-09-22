"""Compose a compact, reference-style variant of the portrait exploded figure.

Differences from the portrait figure:

* the layer stations are much closer together, so the stack reads as one
  compact object with the layers overlapping (like the supplied reference);
* the artwork is uniformly reduced inside the composition so the labels keep a
  legible point size when the figure is exported at a single-column width;
* the labels are trimmed to two short lines per layer (name + thickness); the
  "derived windows" notes move to the footer.

Artwork path data is copied unchanged from the source; only station placement,
scale and text are new.

Usage:
    python build_compact_variant.py --source optimized_v10 --output-dir optimized_v10_compact
"""
from __future__ import annotations

import argparse
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)

ART = 0.62                 # artwork scale inside the composition
PITCH = 30.0               # pt between layer stations (~60 % overlap, reference-style)
X_CENTER = 130.0           # artwork centre x
FIRST_Y = 92.0             # first (top) layer station
LEADER_X0 = 250.0
LEADER_X1 = 272.0
LABEL_X = 284.0
NAME_SIZE = 12.0
SUB_SIZE = 12.0
FOOT_SIZE = 12.0
WIDTH = 436.0
EXPORT_WIDTH_MM = 90.0     # single-column paper width
PAGE_WIDTH = EXPORT_WIDTH_MM / 25.4 * 72
assert SUB_SIZE * PAGE_WIDTH / WIDTH >= 7.0, 'smallest text below 7 pt at this export width'

# Single-line labels keep the tight pitch readable (the reference figure does the
# same); thicknesses ride along in the same line and counts stay compact.
LABELS = {
    'TOP_COMPONENTS': 'Top components · 21',
    'TOP_COVERLAY': 'Coverlay · 12.5+15 um',
    'L1_TOP_COPPER': 'L1 · Top copper',
    'DIELECTRIC_1': 'PI film · 25 um',
    'L2_GND': 'L2 · Ground',
    'CORE': 'PI core · 50 um',
    'L3_POWER': 'L3 · Power',
    'DIELECTRIC_2': 'PI film · 25 um',
    'L4_BOTTOM_COPPER': 'L4 · Bottom copper',
    'BOTTOM_COVERLAY': 'Coverlay · 12.5+15 um',
    'BOTTOM_COMPONENTS': 'Bottom components · 11',
}


def el(name, attrs=None):
    return ET.Element('{' + NS + '}' + name, attrs or {})


def add_text(parent, x, y, value, size=15, weight='normal', color='#303238'):
    node = ET.SubElement(parent, '{' + NS + '}text',
                         {'x': str(x), 'y': str(y), 'font-family': 'Arial',
                          'font-size': str(size), 'font-weight': weight, 'fill': color})
    node.text = value
    return node


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default='optimized_v10')
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--pitch', type=float, default=PITCH, help='pt between layer stations')
    ap.add_argument('--art-scale', type=float, default=ART, help='artwork scale inside the composition')
    args = ap.parse_args()
    pitch, art = args.pitch, args.art_scale
    src = ROOT / args.source
    out = ROOT / args.output_dir
    out.mkdir(exist_ok=False)

    audit = json.loads((src / 'geometry_audit.json').read_text('utf-8'))
    comps = json.loads((src / 'components_registered.json').read_text('utf-8'))
    counts = {}
    for c in comps:
        counts[c['layer']] = counts.get(c['layer'], 0) + 1

    main_svg = ET.parse(src / 'WPT_Exploded_Refined.svg').getroot()
    groups = [g for g in main_svg if g.tag.endswith('}g')]
    stack = audit['stack_top_to_bottom']
    centers = audit['layer_centers_pt']
    last_y = FIRST_Y + (len(stack) - 1) * pitch
    NOTES = [
        f"4 copper / 3 PI / 2 coverlay / {len(comps)} components / 8 cut-outs",
        'Layer spacing and package heights are schematic.',
        'PI thicknesses nominal.',
        'Coverlay windows derived from pads (+0.1 mm).',
        'Full coverlay openings: see the detail sheet.',
    ]
    foot_y = last_y + 56.0
    height = foot_y + 20 + (len(NOTES) - 1) * 16 + 22

    root = el('svg', {'version': '1.1', 'width': f'{WIDTH}pt', 'height': f'{height}pt',
                      'viewBox': f'0 0 {WIDTH} {height}'})
    defs = main_svg.find('{' + NS + '}defs')
    if defs is not None:
        root.append(copy.deepcopy(defs))
    bg = el('g', {'id': 'BACKGROUND'})
    bg.append(el('rect', {'width': str(WIDTH), 'height': str(height), 'fill': 'white'}))
    root.append(bg)

    title = el('g', {'id': 'TITLE'})
    add_text(title, 24, 26, 'Four-layer receiver FPC', 13, 'bold')
    add_text(title, 24, 43, 'Exploded assembly', 12, '#777C80')
    root.append(title)

    geometry_checks = {}
    for g in groups:
        gid = g.get('id')
        if not gid or gid not in centers:
            continue
        i = stack.index(gid)
        y_new = FIRST_Y + i * pitch
        item = copy.deepcopy(g)
        item.set('transform', f'translate({X_CENTER} {y_new}) scale({art}) '
                              f'translate({-219} {-centers[gid]})')
        root.append(item)
        original_d = [e.get('d') for e in g.iter() if e.tag.endswith('}path')]
        copied_d = [e.get('d') for e in item.iter() if e.tag.endswith('}path')]
        assert original_d == copied_d
        geometry_checks[gid] = dict(path_data_unchanged=True, artwork_scale=art,
                                    station_y=y_new, source_center_pt=centers[gid])

    ann = el('g', {'id': 'ANNOTATIONS'})
    for gid in stack:
        i = stack.index(gid)
        y_new = FIRST_Y + i * pitch
        ann.append(el('path', {'d': f'M{LEADER_X0},{y_new:.1f} L{LEADER_X1},{y_new:.1f}',
                               'stroke': '#7D8387', 'stroke-width': '.6', 'fill': 'none'}))
        add_text(ann, LABEL_X, y_new + 4, LABELS[gid], NAME_SIZE)
    root.append(ann)

    foot = el('g', {'id': 'FIGURE_NOTES'})
    foot.append(el('path', {'d': f'M24,{foot_y - 16} L{WIDTH - 24},{foot_y - 16}',
                            'stroke': '#D9DCDD', 'stroke-width': '.6', 'fill': 'none'}))
    for i, line in enumerate(NOTES):
        add_text(foot, 24, foot_y + i * 16, line, FOOT_SIZE, 'normal',
                 '#51575A' if i == 0 else '#85898C')
    root.append(foot)

    ET.ElementTree(root).write(out / 'WPT_Exploded_Refined.svg', encoding='utf-8', xml_declaration=True)
    layout = dict(source=args.source, style='compact portrait (tight layer pitch)',
                  layer_order_top_to_bottom=stack,
                  viewbox=[WIDTH, round(height, 2)], export_width_mm=EXPORT_WIDTH_MM,
                  canvas_mm=[EXPORT_WIDTH_MM, round(EXPORT_WIDTH_MM * height / WIDTH, 2)],
                  layer_pitch_pt=pitch, artwork_scale=art,
                  label_size_pt=NAME_SIZE, sublabel_size_pt=SUB_SIZE,
                  minimum_font_pt=SUB_SIZE * PAGE_WIDTH / WIDTH,
                  geometry=geometry_checks,
                  notes='artwork path data copied unchanged; only station placement, scale and text are new')
    (out / 'layout_audit.json').write_text(json.dumps(layout, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in layout.items() if k != 'geometry'}, indent=2))
    print('wrote', out / 'WPT_Exploded_Refined.svg')


if __name__ == '__main__':
    main()
