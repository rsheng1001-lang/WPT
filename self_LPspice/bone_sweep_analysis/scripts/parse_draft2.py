#!/usr/bin/env python3
"""Parse LTspice Draft2.log (3-parameter sweep) into a tidy dataset + validation report."""
import re, json, math, sys
from pathlib import Path

# Paths are relative to this file so the folder can be moved as a unit:
#   <root>/bone_sweep_analysis/scripts/this_file.py  ->  root = .../bone_sweep_analysis
# The LTspice log lives next to the circuit, one level above root; pass a
# different log as argv[1] to re-run against another sweep.
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
WORK.mkdir(parents=True, exist_ok=True)
LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "Draft2.log"
OUT = WORK / "parsed_raw.json"

STEP_RE = re.compile(r"^\.step\s+(.*)$")
KV_RE = re.compile(r"(\w+)=(\S+)")
MEAS_HDR_RE = re.compile(r"^Measurement:\s*(\w+)\s*$", re.I)
NUMROW_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")

def to_float(tok):
    t = tok.strip()
    if t.lower() in ("failed", "fail"):
        return None
    try:
        return float(t)
    except ValueError:
        return None

def main():
    text = LOG.read_text(encoding="latin-1").splitlines()

    # ---------- 1. step parameter lines (in log order) ----------
    steps = []          # list of dict(iref, rb, vbp)
    for line in text:
        m = STEP_RE.match(line)
        if not m:
            continue
        kvs = dict(KV_RE.findall(m.group(1)))
        if not {"iref", "rb", "vbp"} <= set(kvs):
            continue
        steps.append({
            "iref": float(kvs["iref"]),
            "rb":   float(kvs["rb"]),
            "vbp":  float(kvs["vbp"]),
            "raw":  m.group(1),
        })
    print(f"[parse] step lines found: {len(steps)}")

    # ---------- 2. measurement tables ----------
    meas = {}           # name -> {step_index: [floats]}
    cur = None
    for i, line in enumerate(text):
        mh = MEAS_HDR_RE.match(line)
        if mh:
            cur = mh.group(1).lower()
            meas[cur] = {}
            continue
        if cur is None:
            continue
        if line.strip() == "":
            continue
        m = NUMROW_RE.match(line)
        if not m:
            continue
        idx = int(m.group(1))
        vals = [to_float(t) for t in m.group(2).split()]
        vals = [v for v in vals]
        if not vals:
            continue
        meas[cur][idx] = vals

    for k, v in meas.items():
        print(f"[parse] measurement '{k}': {len(v)} rows, "
              f"steps {min(v)}..{max(v)}")

    # ---------- 3. join ----------
    n = len(steps)
    rows = []
    for si, st in enumerate(steps, start=1):
        ib = meas.get("ibone",  {}).get(si)
        vb = meas.get("vbone",  {}).get(si)
        ie = meas.get("ierr",   {}).get(si)
        ps = meas.get("pass",   {}).get(si)
        rows.append({
            "step": si,
            "vbp": st["vbp"], "iref": st["iref"], "rb": st["rb"],
            "IBONE": ib[0] if ib else None,
            "VBONE": vb[0] if vb else None,
            "IERR":  ie[0] if ie else None,
            "PASS":  int(ps[0]) if ps and ps[0] is not None else None,
        })

    # ---------- 4. validation ----------
    print("\n===== VALIDATION =====")
    missing = [r["step"] for r in rows
               if any(r[k] is None for k in ("IBONE", "VBONE", "IERR", "PASS"))]
    print(f"rows with any missing measurement: {len(missing)} {missing[:20]}")

    # combos: 6 VBP x 5 IREF x 191 RB
    combos = {(r["vbp"], r["iref"], r["rb"]) for r in rows}
    print(f"unique (VBP,IREF,RB) combos: {len(combos)}  (rows={len(rows)})")
    print(f"duplicate combos: {len(rows) - len(combos)}")

    # cross-check 1: VBONE/IBONE should equal RB (Ohm's law on R_BONE)
    worst_r = (0.0, None)
    for r in rows:
        if r["IBONE"] and r["VBONE"]:
            rcalc = r["VBONE"] / r["IBONE"]
            err = abs(rcalc - r["rb"]) / r["rb"]
            if err > worst_r[0]:
                worst_r = (err, r)
    print(f"max RB reconstruction error: {worst_r[0]:.3e}  "
          f"(step {worst_r[1]['step']}: VBONE/IBONE={worst_r[1]['VBONE']/worst_r[1]['IBONE']:.3f} "
          f"vs RB={worst_r[1]['rb']:.0f})")

    # cross-check 2: IERR == 100*abs(IBONE-IREF)/IREF
    worst_i = (0.0, None)
    for r in rows:
        if r["IERR"] is None or r["IBONE"] is None:
            continue
        calc = 100 * abs(r["IBONE"] - r["iref"]) / r["iref"]
        d = abs(calc - r["IERR"])
        if d > worst_i[0]:
            worst_i = (d, r)
    print(f"max IERR formula deviation: {worst_i[0]:.3e} pct-pt  "
          f"(step {worst_i[1]['step']})")

    # cross-check 3: PASS == (IERR<=1)
    bad = [r["step"] for r in rows
           if r["IERR"] is not None and r["PASS"] != int(r["IERR"] <= 1.0)]
    print(f"rows where PASS != (IERR<=1): {len(bad)}")

    # pass / fail counts
    npass = sum(1 for r in rows if r["PASS"] == 1)
    print(f"PASS=1: {npass}   PASS=0: {len(rows)-npass}")

    # per (VBP,IREF) coverage
    vb_s = sorted({r["vbp"] for r in rows})
    ir_s = sorted({r["iref"] for r in rows})
    rb_s = sorted({r["rb"] for r in rows})
    print(f"VBP values ({len(vb_s)}): {vb_s}")
    print(f"IREF values ({len(ir_s)}): {[v*1e6 for v in ir_s]} uA")
    print(f"RB  values ({len(rb_s)}): {rb_s[0]:.0f} .. {rb_s[-1]:.0f} "

          f"step {rb_s[1]-rb_s[0]:.0f}")
    incomplete = []
    for v in vb_s:
        for i in ir_s:
            cnt = sum(1 for r in rows if r["vbp"] == v and r["iref"] == i)
            if cnt != len(rb_s):
                incomplete.append((v, i*1e6, cnt))
    print(f"incomplete (VBP,IREF) grids: {len(incomplete)} {incomplete[:10]}")

    OUT.write_text(json.dumps(rows), encoding="utf-8")
    print(f"\n[out] {OUT}")

if __name__ == "__main__":
    main()
