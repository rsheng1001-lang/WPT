"""Extract copper geometry (polylines + filled pads) from LCEDA layer PDFs.

Rules, reconstructed to reproduce the project's historical geom.json exactly:

* every drawing carrying a fill becomes one closed polygon (page-background
  rectangle excepted); cubic Beziers are sampled at 16 points per curve;
* every drawing carrying a stroke also contributes its outline to the stroke
  pool: straight segments are chained endpoint-to-endpoint within one stroke
  width, stopping at any junction or free end; curve segments are sampled the
  same way (16 per cubic);
* a stroke whose PDF width is 0 (LCEDA "hairline" outlines of pad rings)
  falls back to 0.57 pt;
* points are rounded to 3 decimals; the polyline order is: chained open runs
  in chain order, then leftover closed loops.

Usage:
    python extract_geometry.py --out geom_new.json \
        L1_TOP "inputs/TOP/Top Layer.pdf" L2_GND "inputs/GND/GND.pdf" \
        L3_POWER "inputs/POWER/POWER.pdf" L4_BOTTOM "inputs/BUTTON/Bottom Layer.pdf"
    python extract_geometry.py --compare data/geom.json --out geom_check.json ...
"""
from __future__ import annotations

import argparse
import collections
import json

import pymupdf

CURVE_SAMPLES = 16          # points per cubic Bezier
HAIRLINE_FALLBACK = 0.57    # pt, for zero-width LCEDA outlines
ROUND = 3
KEY_DECIMALS = 3


def key(p, nd=KEY_DECIMALS):
    return (round(p[0], nd), round(p[1], nd))


def sample_cubic(p0, p1, p2, p3):
    pts = []
    for i in range(1, CURVE_SAMPLES + 1):
        t = i / CURVE_SAMPLES
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def outline_points(d):
    """Ordered outline of a drawing, straight from its items."""
    pts = []

    def push(p):
        if not pts or key(pts[-1]) != key(p):
            pts.append(p)

    for it in d["items"]:
        if it[0] == "l":
            push((it[1].x, it[1].y))
            push((it[2].x, it[2].y))
        elif it[0] == "c":
            push((it[1].x, it[1].y))
            for p in sample_cubic((it[1].x, it[1].y), (it[2].x, it[2].y),
                                  (it[3].x, it[3].y), (it[4].x, it[4].y)):
                push(p)
        elif it[0] == "re":
            r = it[1]
            for c in ((r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)):
                push(c)
        elif it[0] == "qu":
            q = it[1]
            push((q.ul.x, q.ul.y))
            push((q.ur.x, q.ur.y))
            push((q.lr.x, q.lr.y))
            push((q.ll.x, q.ll.y))
            push((q.ul.x, q.ul.y))
    return pts


def is_page_frame(d, page_rect):
    r = d["rect"]
    return (r.width >= page_rect.width - 1) and (r.height >= page_rect.height - 1) \
        and len(d["items"]) <= 2


def chain_segments(pool, nd=KEY_DECIMALS):
    """Chain segments into runs; stop at free ends, junctions and ambiguity.

    ``pool`` is a list of (a, b, width) in drawing order.  Segments only
    connect within one width; emission order follows first discovery.
    """
    adj = collections.defaultdict(list)
    for i, (a, b, _w) in enumerate(pool):
        adj[key(a, nd)].append(i)
        adj[key(b, nd)].append(i)

    used = set()
    chains = []

    def walk(i, reverse):
        used.add(i)
        w = pool[i][2]
        a, b = pool[i][0], pool[i][1]
        pts = [b, a] if reverse else [a, b]
        for direction in (1, -1):
            while True:
                cur = pts[-1] if direction == 1 else pts[0]
                cands = [j for j in adj[key(cur, nd)]
                         if j not in used and pool[j][2] == w]
                if len(cands) != 1:
                    break
                j = cands[0]
                p, q = pool[j][0], pool[j][1]
                used.add(j)
                nxt = q if key(p, nd) == key(cur, nd) else p
                if direction == 1:
                    pts.append(nxt)
                else:
                    pts.insert(0, nxt)
        return pts, w

    starts = []
    for i, (a, b, _w) in enumerate(pool):
        if len(adj[key(a, nd)]) == 1:
            starts.append((i, False))
        elif len(adj[key(b, nd)]) == 1:
            starts.append((i, True))
    for i, rev in starts:
        if i not in used:
            chains.append(walk(i, rev))
    for i in range(len(pool)):
        if i not in used:
            chains.append(walk(i, False))
    return chains


def extract_layer(pdf_path, nd=KEY_DECIMALS):
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    page_rect = page.rect
    fills = []
    pool = []

    for d in page.get_drawings():
        pts = outline_points(d)
        if d.get("fill") is not None and len(pts) >= 3 and not is_page_frame(d, page_rect):
            fills.append([(round(x, ROUND), round(y, ROUND)) for x, y in pts])
        if d.get("color") is not None and len(pts) >= 2:
            w = d.get("width") or 0.0
            w = round(w, ROUND) if w > 0 else HAIRLINE_FALLBACK
            for a, b in zip(pts, pts[1:]):
                pool.append((a, b, w))
    doc.close()

    polylines, widths = [], []
    for ch, w in chain_segments(pool, nd):
        polylines.append([(round(x, ROUND), round(y, ROUND)) for x, y in ch])
        widths.append(w)
    return dict(polylines=polylines, widths=widths, fills=fills)


def compare(new, old, layer):
    print(f"--- {layer} ---")
    for k in ("polylines", "fills"):
        print(f"  {k}: old={len(old[k])} new={len(new[k])}")
    if len(new["polylines"]) == len(old["polylines"]):
        dev = 0.0
        match = 0
        for np_, op_ in zip(new["polylines"], old["polylines"]):
            if len(np_) == len(op_):
                match += 1
                for (nx, ny), (ox, oy) in zip(np_, op_):
                    dev = max(dev, abs(nx - ox), abs(ny - oy))
            else:
                print(f"  point-count mismatch: new={len(np_)} old={len(op_)}")
        print(f"  polylines with equal point count: {match}/{len(old['polylines'])}, max coord dev={dev:.4f} pt")
    if len(new["fills"]) == len(old["fills"]):
        dev = 0.0
        match = 0
        for nf, of in zip(new["fills"], old["fills"]):
            if len(nf) == len(of):
                match += 1
                for (nx, ny), (ox, oy) in zip(nf, of):
                    dev = max(dev, abs(nx - ox), abs(ny - oy))
        print(f"  fills with equal point count: {match}/{len(old['fills'])}, max coord dev={dev:.4f} pt")
    wc_new = collections.Counter(new["widths"])
    wc_old = collections.Counter(old["widths"])
    if wc_new != wc_old:
        print(f"  width histogram new={dict(wc_new)} old={dict(wc_old)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare")
    ap.add_argument("--key-decimals", type=int, default=KEY_DECIMALS)
    ap.add_argument("layers", nargs="+", help="NAME pdf [NAME pdf ...]")
    args = ap.parse_args()

    pairs = list(zip(args.layers[0::2], args.layers[1::2]))
    geom = {}
    for name, path in pairs:
        geom[name] = extract_layer(path, args.key_decimals)
        print(f"{name}: polylines={len(geom[name]['polylines'])} fills={len(geom[name]['fills'])}")

    if args.compare:
        old = json.load(open(args.compare, encoding="utf-8"))
        for name, _ in pairs:
            if name in old:
                compare(geom[name], old[name], name)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(geom, f, separators=(",", ":"))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
