"""Refresh the placement-derived fields of component_templates.json.

The templates carry the per-package body size, height and kind (package
definitions that survive a board revision) plus placement-derived fields that
must follow the current PickAndPlace CSV:

    footprint, device, layer, side, board_axis, cathode, csv_rot, pins

`x`, `y` and `own_pads` are intentionally left as recorded template values;
build_figure.py re-fits the origin and re-derives each component's landing
pads from the copper geometry, so those stale numbers are never used.

Usage:
    python refresh_templates.py            # rewrites data/component_templates.json
    python refresh_templates.py --check    # report only, write nothing
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL_PATH = ROOT / "data" / "component_templates.json"
CSV_GLOB = "PickAndPlace*.csv"
PT_PER_MM = 72.0 / 25.4
SIDE_LAYER = {"T": "TOP_COMPONENTS", "B": "BOTTOM_COMPONENTS"}

# package length axis and body size (mm): which package axis carries the body
# length, real body (length, width), real height, drawing kind.
PACKAGE = {
    "C0201": dict(body=[0.6, 0.3], length_axis="x", height_mm=0.33, kind="chip"),
    "R0201": dict(body=[0.6, 0.3], length_axis="x", height_mm=0.33, kind="chip"),
    "C0402": dict(body=[1.0, 0.5], length_axis="x", height_mm=0.45, kind="chip"),
    "SOD-323_L1.6-W1.3-LS2.6-RD-1": dict(body=[1.6, 1.3], length_axis="x", height_mm=0.60, kind="diode"),
    "SOD-523_L1.2-W0.8-LS1.6-RD": dict(body=[1.2, 0.8], length_axis="x", height_mm=0.60, kind="diode"),
    "SOD-523_L1.2-W0.8-LS1.6-FD": dict(body=[1.2, 0.8], length_axis="x", height_mm=0.60, kind="diode"),
    "SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR": dict(body=[2.9, 1.3], length_axis="y", height_mm=1.10, kind="ic"),
    "SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR": dict(body=[3.0, 1.7], length_axis="y", height_mm=1.10, kind="ic"),
    "SOT-23-5_L2.9-W1.6-P0.95-LS2.8-BR": dict(body=[2.9, 1.6], length_axis="y", height_mm=1.10, kind="ic"),
    "SOT-323-5_L2.1-W1.3-P0.65-LS2.1-BL": dict(body=[2.1, 1.3], length_axis="y", height_mm=1.00, kind="ic"),
}


def num(s: str) -> float:
    return float(s.replace("mm", "").strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    templates = json.loads(TPL_PATH.read_text(encoding="utf-8"))
    by_ref = {c["ref"]: c for c in templates}
    csv_path = next((ROOT / "inputs").glob(CSV_GLOB))
    rows = list(csv.DictReader(open(csv_path, encoding="utf-16"), delimiter="\t"))

    changed = []
    for r in rows:
        ref = r["Designator"]
        if ref not in by_ref:
            raise KeyError(f"{ref} has no template entry")
        c = by_ref[ref]
        fp = r["Footprint"]
        if fp not in PACKAGE:
            raise KeyError(f"unknown footprint {fp} (ref {ref}) - add it to PACKAGE")
        pkg = PACKAGE[fp]
        theta = float(r["Rotation"])

        swap = (theta % 180) == 90
        length_axis = pkg["length_axis"]
        board_axis = ("y" if length_axis == "x" else "x") if swap else length_axis

        cathode = None
        if pkg["kind"] == "diode":
            # pin 1 = cathode; PDF-frame offset of the pin-1 pad from the centre
            ox = (num(r["Pad X"]) - num(r["Mid X"])) * PT_PER_MM
            oy = -(num(r["Pad Y"]) - num(r["Mid Y"])) * PT_PER_MM
            cathode = [round(ox, 6), round(oy, 6)]

        updates = dict(footprint=fp, device=r["Device"],
                       layer=SIDE_LAYER[r["Layer"]], side=r["Layer"],
                       body=list(pkg["body"]), board_axis=board_axis,
                       kind=pkg["kind"], pins=int(r["Pins"]),
                       cathode=cathode, csv_rot=theta, height_mm=pkg["height_mm"])
        for k, v in updates.items():
            if c.get(k) != v:
                changed.append((ref, k, c.get(k), v))
                c[k] = v

    print(f"refs in CSV: {len(rows)}; fields updated: {len(changed)}")
    for ref, k, old, new in changed:
        print(f"   {ref:<5} {k:<11} {str(old)[:42]:<44} -> {str(new)[:42]}")
    if args.check:
        print("check only, nothing written")
        return
    TPL_PATH.write_text(json.dumps(templates, indent=2), encoding="utf-8")
    print("wrote", TPL_PATH)


if __name__ == "__main__":
    main()
