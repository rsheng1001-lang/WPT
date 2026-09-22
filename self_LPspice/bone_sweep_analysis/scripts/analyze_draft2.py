#!/usr/bin/env python3
"""Analyse parsed sweep: Rmax matrix, boundary region, 10uA base-error case."""
import json
from pathlib import Path
from collections import defaultdict

WORK = Path(__file__).resolve().parent.parent / "work"
rows = json.loads((WORK / "parsed_raw.json").read_text(encoding="utf-8"))

VBPS  = sorted({r["vbp"] for r in rows})
IREFs = sorted({r["iref"] for r in rows})
RBS   = sorted({r["rb"] for r in rows})

g = defaultdict(dict)          # (vbp,iref) -> {rb: row}
for r in rows:
    g[(r["vbp"], r["iref"])][r["rb"]] = r

print("=" * 78)
print("Rmax / boundary per (VBP, IREF)")
print("=" * 78)
hdr = f"{'VBP':>5} {'IREF_uA':>8} {'nPASS':>5} {'minRB_P':>8} {'Rmax_k':>8} " \
      f"{'lastP':>7} {'1stF':>7} {'mono?':>6}  note"
print(hdr)
summary = {}
boundary = {}
for v in VBPS:
    for i in IREFs:
        d = g[(v, i)]
        pas = sorted(rb for rb, r in d.items() if r["PASS"] == 1)
        fal = sorted(rb for rb, r in d.items() if r["PASS"] == 0)
        # monotonicity: does PASS ever return to 1 after a 0?
        seq = [d[rb]["PASS"] for rb in RBS]
        nonmono = any(seq[k] == 0 and 1 in seq[k+1:] for k in range(len(seq)))
        lastP = max(pas) if pas else None
        firstF = min([rb for rb in fal if lastP is not None and rb > lastP],
                     default=None)
        at_max = d[RBS[-1]]["PASS"] == 1
        min_fails = d[RBS[0]]["PASS"] == 0
        if not pas:
            note = f"BASE-ERROR: IERR@minRB={d[RBS[0]]['IERR']:.3f}% -> all FAIL"
        elif at_max:
            note = f"HIT SCAN LIMIT (IERR@{RBS[-1]/1000:.0f}k={d[RBS[-1]]['IERR']:.3f}%)"
        elif min_fails:
            note = f"fails at minRB too (IERR@10k={d[RBS[0]]['IERR']:.3f}%)"
        else:
            note = ""
        summary[(v, i)] = dict(rmax=lastP, at_max=at_max, npass=len(pas),
                               firstF=firstF, base_err_only=(not pas))
        boundary[(v, i)] = dict(lastP=lastP, firstF=firstF, nonmono=nonmono,
                                min_fails=min_fails)
        print(f"{v:>5} {i*1e6:>8.0f} {len(pas):>5} "
              f"{(f'{min(pas)/1000:.0f}' if pas else '-'):>8} "
              f"{(f'{lastP/1000:.0f}' if lastP else 'N/A'):>8} "
              f"{(f'{lastP/1000:.0f}' if lastP else '-'):>7} "
              f"{(f'{firstF/1000:.0f}' if firstF else '-'):>7} "
              f"{('YES' if nonmono else 'no'):>6}  {note}")

print("\n" + "=" * 78)
print("10 uA detail (base error check)")
print("=" * 78)
print(f"{'VBP':>5} {'IERR@10k%':>10} {'IERR@50k%':>10} {'IERR@100k%':>11} "
      f"{'IERR@200k%':>11} {'IBONE@10k_uA':>13}")
for v in VBPS:
    d = g[(v, 10e-6)]
    print(f"{v:>5} {d[10000]['IERR']:>10.4f} {d[50000]['IERR']:>10.4f} "
          f"{d[100000]['IERR']:>11.4f} {d[200000]['IERR']:>11.4f} "
          f"{d[10000]['IBONE']*1e6:>13.6f}")

print("\n" + "=" * 78)
print("IERR monotonic in RB within each (VBP,IREF)?")
print("=" * 78)
for v in VBPS:
    nonmono_pts = []
    for i in IREFs:
        d = g[(v, i)]
        ser = [d[rb]["IERR"] for rb in RBS]
        drops = [RBS[k+1]/1000 for k in range(len(ser)-1) if ser[k+1] < ser[k] - 1e-9]
        if drops:
            nonmono_pts.append((i*1e6, len(drops), drops[:5]))
    print(f"VBP={v}: " + ("all monotonic increasing" if not nonmono_pts
                          else str(nonmono_pts)))

print("\n" + "=" * 78)
print("Rmax matrix (kOhm)  rows=VBP cols=IREF")
print("=" * 78)
print(f"{'VBP':>5} " + "".join(f"{i*1e6:>14.0f}" for i in IREFs))
for v in VBPS:
    cells = []
    for i in IREFs:
        s = summary[(v, i)]
        if s["base_err_only"]:
            cells.append(f"{'N/A':>14}")
        elif s["at_max"]:
            cells.append(f"{'>=' + str(int(RBS[-1]/1000)):>14}")
        else:
            cells.append(f"{s['rmax']/1000:>14.0f}")
    print(f"{v:>5} " + "".join(cells))

print("\n" + "=" * 78)
print("Boundary region (for refinement sweep)")
print("=" * 78)
for v in VBPS:
    for i in IREFs:
        b = boundary[(v, i)]
        if b["lastP"] is None:
            print(f"VBP={v:>5} IREF={i*1e6:>3.0f}uA : no PASS anywhere "
                  f"(IERR@10k={g[(v,i)][10000]['IERR']:.4f}%)")
        elif b["firstF"] is None:
            print(f"VBP={v:>5} IREF={i*1e6:>3.0f}uA : PASS up to scan limit "
                  f"{b['lastP']/1000:.0f}k, no FAIL found")
        else:
            lp = g[(v, i)][b["lastP"]]; ff = g[(v, i)][b["firstF"]]
            print(f"VBP={v:>5} IREF={i*1e6:>3.0f}uA : "
                  f"{b['lastP']/1000:.0f}k PASS(I={lp['IBONE']*1e6:.4f}uA, "
                  f"err={lp['IERR']:.4f}%) -> {b['firstF']/1000:.0f}k FAIL"
                  f"(I={ff['IBONE']*1e6:.4f}uA, err={ff['IERR']:.4f}%)"
                  + ("   [NON-MONOTONIC]" if b["nonmono"] else ""))

print("\n" + "=" * 78)
print("Overall IERR range & near-threshold rows (|IERR-1|<0.05)")
print("=" * 78)
allerr = [r["IERR"] for r in rows]
print(f"IERR min={min(allerr):.4f}%  max={max(allerr):.4f}%")
near = [r for r in rows if abs(r["IERR"] - 1.0) < 0.05]
print(f"rows with |IERR-1%|<0.05: {len(near)}")
for r in sorted(near, key=lambda r: r["IERR"])[:15]:
    print(f"   step {r['step']:>5} VBP={r['vbp']:>4} IREF={r['iref']*1e6:>5.0f}uA "
          f"RB={r['rb']/1000:>5.0f}k  IERR={r['IERR']:.5f}%  PASS={r['PASS']}")

# ---- per (VBP,IREF) stats: low-load accuracy (min RB) ----
print("\n" + "=" * 78)
print("Low-load accuracy (@RB=10k) and headroom-limited worst case")
print("=" * 78)
print(f"{'VBP':>5} {'IREF':>6} {'Iact@10k_uA':>12} {'err@10k_%':>10} "
      f"{'Iact@200k_uA':>13} {'err@200k_%':>11} {'Vbone@200k':>11}")
for v in VBPS:
    for i in IREFs:
        d = g[(v, i)]
        print(f"{v:>5} {i*1e6:>6.0f} {d[10000]['IBONE']*1e6:>12.6f} "
              f"{d[10000]['IERR']:>10.4f} {d[200000]['IBONE']*1e6:>13.6f} "
              f"{d[200000]['IERR']:>11.4f} {d[200000]['VBONE']:>11.5f}")
