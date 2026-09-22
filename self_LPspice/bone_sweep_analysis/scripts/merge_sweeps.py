#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge the two sweeps into one dataset for the workbook.

  Sweep 1 : Draft2.log        RB =   10k ..  200k step  1k   (191 pts, 1 kΩ 分辨)
  Sweep 2 : Draft2_sweep.log  RB =  200k .. 1000k step 10k   ( 81 pts, 10 kΩ 分辨)

They overlap at RB = 200 kΩ only, where the two logs agree bit-for-bit
(verified: max relative deviation 0.00e+00 on IBONE and IERR). The duplicate row
is kept once, from sweep 1.

Output: work/parsed_combined.json   (rows sorted by VBP -> IREF -> RB, each
row tagged with its sweep number and source log name)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"

# (sweep id, source log name, parsed json)
#   A: RB   10k ..  200k step  1k  -> parsed_raw.json
#   B: RB  200k .. 1000k step 10k  -> parsed_raw_sweep2.json
#   C: RB    1M ..   10M step 100k -> parsed_raw_sweep3.json
# NB: B's raw log was overwritten by the C run, so parsed_raw_sweep2.json is now
# the only surviving record of sweep B.
LOGS = [(1, "Draft2.log", WORK / "parsed_raw.json"),
        (2, "Draft2_sweep.log (RB 200k-1000k)", WORK / "parsed_raw_sweep2.json"),
        (3, "Draft2_sweep.log (RB 1M-10M)", WORK / "parsed_raw_sweep3.json")]


def main():
    merged, seen = [], {}
    per_sweep = {}
    for sweep, logname, path in LOGS:
        rows = json.loads(path.read_text(encoding="utf-8"))
        per_sweep[sweep] = len(rows)
        for r in rows:
            k = (r["vbp"], round(r["iref"] * 1e6, 6), r["rb"])
            if k in seen:
                continue          # overlap row: keep the first (sweep 1)
            seen[k] = True
            merged.append({
                "sweep": sweep, "log": logname, "step": r["step"],
                "vbp": r["vbp"], "iref": r["iref"], "rb": r["rb"],
                "IBONE": r["IBONE"], "VBONE": r["VBONE"],
                "IERR": r["IERR"], "PASS": r["PASS"],
            })

    # sort: VBP -> IREF -> RB, and within an identical key keep sweep 1 first
    merged.sort(key=lambda r: (r["vbp"], r["iref"], r["rb"], r["sweep"]))

    rbs = sorted({r["rb"] for r in merged})
    print(f"sweep1 rows      : {per_sweep[1]}")
    print(f"sweep2 rows      : {per_sweep[2]}")
    print(f"overlap deduped  : {sum(per_sweep.values()) - len(merged)}")
    print(f"combined rows    : {len(merged)}")
    print(f"unique (V,I,R)   : {len({(r['vbp'], r['iref'], r['rb']) for r in merged})}")
    print(f"RB values        : {len(rbs)}  ({rbs[0]:.0f} .. {rbs[-1]:.0f} Ohm)")
    grp = {}
    for r in merged:
        grp.setdefault((r["vbp"], round(r["iref"] * 1e6, 6)), 0)
        grp[(r["vbp"], round(r["iref"] * 1e6, 6))] += 1
    print(f"group size       : {sorted(set(grp.values()))}  (per VBP x IREF)")
    miss = [r for r in merged if any(r[k] is None for k in
                                     ("IBONE", "VBONE", "IERR", "PASS"))]
    print(f"rows with missing: {len(miss)}")
    np_ = sum(1 for r in merged if r["PASS"] == 1)
    print(f"PASS=1 / PASS=0  : {np_} / {len(merged) - np_}")
    for sw, logname, path in LOGS:
        rs = sorted({r["rb"] for r in merged if r["sweep"] == sw})
        if rs:
            print(f"  sweep {sw}: RB {rs[0]/1000:.0f}k .. {rs[-1]/1000:.0f}k, "
                  f"{len(rs)} pts, step {(rs[1]-rs[0])/1000 if len(rs)>1 else 0:.0f}k, "
                  f"{sum(1 for r in merged if r['sweep']==sw)} rows")

    (WORK / "parsed_combined.json").write_text(
        json.dumps(merged), encoding="utf-8")
    print(f"\n[out] {WORK/'parsed_combined.json'}")


if __name__ == "__main__":
    main()
