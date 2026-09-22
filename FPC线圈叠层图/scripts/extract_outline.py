"""Extract the board outline and cutout contours from a Multi-Layer PDF.

The Multi-Layer export is the only one that carries the cutout boundaries
(the Board Outline Layer PDF shows just the outer edge). Contours are walked
from the exporter's segment soup, classified by size, and written as
outline_contours.json in PDF points. Winding is normalised: the outer contour
counter-clockwise, every cutout clockwise, so Illustrator treats them as holes
inside one compound path.

Usage:
    python extract_outline.py --src "inputs/板框/Multi-Layer.pdf" --out data/outline_contours.json
"""
from __future__ import annotations

import argparse
import collections
import json

import pymupdf

MIN_DIM = 5.0          # pt; smaller closed shapes are through-hole pads, drop them


def signed_area(pts):
    s = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i][:2]
        x2, y2 = pts[i + 1][:2]
        s += x1 * y2 - x2 * y1
    return s / 2


def key(p):
    return (round(p[0], 2), round(p[1], 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    doc = pymupdf.open(args.src)
    page = doc[0]
    segs = []
    for g in page.get_drawings():
        for it in g["items"]:
            if it[0] == "l":
                segs.append(((it[1].x, it[1].y), (it[2].x, it[2].y)))
    doc.close()

    adj = collections.defaultdict(list)
    for i, (a, b) in enumerate(segs):
        adj[key(a)].append(i)
        adj[key(b)].append(i)

    used, chains = set(), []
    for i in range(len(segs)):
        if i in used:
            continue
        used.add(i)
        a, b = segs[i]
        chain = [a, b]
        for direction in (1, -1):
            while True:
                cur = chain[-1] if direction == 1 else chain[0]
                nxt = None
                for j in adj[key(cur)]:
                    if j in used:
                        continue
                    p, q = segs[j]
                    nxt = q if key(p) == key(cur) else p
                    used.add(j)
                    break
                if nxt is None:
                    break
                if direction == 1:
                    chain.append(nxt)
                else:
                    chain.insert(0, nxt)
        chains.append(chain)

    contours = []
    for c in chains:
        pts = [(round(p[0], 3), round(p[1], 3)) for p in c]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if max(w, h) < MIN_DIM:
            continue                                   # via / pad circle
        area = abs(signed_area(pts))
        contours.append(dict(points=pts, w=round(w, 2), h=round(h, 2),
                             area_pt2=round(area, 1)))

    contours.sort(key=lambda c: -c["area_pt2"])
    outer, holes = contours[0], contours[1:]
    print(f"contours kept: {len(contours)}  (outer 1 + holes {len(holes)})")
    print(f"outer: bbox {outer['w']} x {outer['h']} pt, area {outer['area_pt2']} pt^2")
    for hc in holes:
        print(f"   hole: bbox {hc['w']} x {hc['h']} pt, area {hc['area_pt2']} pt^2")

    # normalise winding: outer CCW (positive), holes CW (negative) in PDF coords
    if signed_area(outer["points"]) < 0:
        outer["points"] = outer["points"][::-1]
    for hc in holes:
        if signed_area(hc["points"]) > 0:
            hc["points"] = hc["points"][::-1]

    total_pts = len(outer["points"]) + sum(len(h["points"]) for h in holes)
    print(f"total points: {total_pts} (outer {len(outer['points'])})")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dict(outer=outer, holes=holes), f, separators=(",", ":"))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
