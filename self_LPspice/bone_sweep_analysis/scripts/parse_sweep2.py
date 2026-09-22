#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse the SECOND (extended-load) sweep and cross-check it against the first one
at their overlapping operating point (RB = 200 kΩ).

Sweep 1 : Draft2.log        RB =  10k ..  200k step  1k  (191 pts)   5730 runs
Sweep 2 : Draft2_sweep.log  RB = 200k .. 1000k step 10k  ( 81 pts)   2430 runs

The two decks differ ONLY in the RB .step line, so the RB=200 kΩ measurements
must agree if the reconstructed schematic really is the original circuit.

Writes work/parsed_raw_sweep2.json (leaves work/parsed_raw.json untouched).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
WORK.mkdir(parents=True, exist_ok=True)

STEP_RE = re.compile(r"^\.step\s+(.*)$")
KV_RE = re.compile(r"(\w+)=(\S+)")
MEAS_HDR_RE = re.compile(r"^Measurement:\s*(\w+)\s*$", re.I)
NUMROW_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")


def parse(logpath: Path):
    text = logpath.read_text(encoding="latin-1").splitlines()
    steps = []
    for line in text:
        m = STEP_RE.match(line)
        if not m:
            continue
        kvs = dict(KV_RE.findall(m.group(1)))
        if not {"iref", "rb", "vbp"} <= set(kvs):
            continue
        steps.append((float(kvs["vbp"]), float(kvs["iref"]), float(kvs["rb"])))
    meas, cur = {}, None
    for line in text:
        mh = MEAS_HDR_RE.match(line)
        if mh:
            cur = mh.group(1).lower()
            meas[cur] = {}
            continue
        if cur is None or line.strip() == "":
            continue
        m = NUMROW_RE.match(line)
        if not m:
            continue
        toks = [t.strip() for t in m.group(2).split()]
        try:
            meas[cur][int(m.group(1))] = float(toks[0])
        except ValueError:
            meas[cur][int(m.group(1))] = None
    rows = []
    for i, (vbp, iref, rb) in enumerate(steps, start=1):
        rows.append({
            "step": i, "vbp": vbp, "iref": iref, "rb": rb,
            "IBONE": meas.get("ibone", {}).get(i),
            "VBONE": meas.get("vbone", {}).get(i),
            "IERR": meas.get("ierr", {}).get(i),
            "PASS": (None if meas.get("pass", {}).get(i) is None
                     else int(meas.get("pass", {})[i])),
        })
    return rows


def validate(rows, name):
    print(f"--- {name} ---")
    print(f"  行数            : {len(rows)}")
    miss = [r["step"] for r in rows
            if any(r[k] is None for k in ("IBONE", "VBONE", "IERR", "PASS"))]
    print(f"  缺失测量        : {len(miss)}")
    combos = {(r["vbp"], r["iref"], r["rb"]) for r in rows}
    print(f"  唯一组合 / 行数 : {len(combos)} / {len(rows)}")
    vbps = sorted({r["vbp"] for r in rows})
    irefs = sorted({r["iref"] for r in rows})
    rbs = sorted({r["rb"] for r in rows})
    print(f"  VBP  : {vbps}")
    print(f"  IREF : {[round(i*1e6, 6) for i in irefs]} uA")
    print(f"  RB   : {rbs[0]:.0f} .. {rbs[-1]:.0f} Ohm, {len(rbs)} 点, 步长 "
          f"{(rbs[1]-rbs[0]) if len(rbs) > 1 else 0:.0f}")
    # independent check: VBONE/IBONE must reproduce that step's RB
    worst = (0.0, None)
    for r in rows:
        if r["IBONE"] and r["VBONE"]:
            err = abs(r["VBONE"] / r["IBONE"] - r["rb"]) / r["rb"]
            if err > worst[0]:
                worst = (err, r["step"])
    print(f"  RB 反算最大误差 : {worst[0]:.3e} (step {worst[1]})")
    bad = [r["step"] for r in rows
           if r["IERR"] is not None and r["PASS"] != int(r["IERR"] <= 1.0)]
    print(f"  PASS 与 IERR 不一致: {len(bad)}")
    np_ = sum(1 for r in rows if r["PASS"] == 1)
    print(f"  PASS=1: {np_}   PASS=0: {len(rows)-np_}")
    return all(len(m) == 0 for m in
               [[x for x in (1,) if a is None] for a in
                [r["IBONE"] for r in rows]]) and len(miss) == 0


def main():
    log1 = ROOT.parent / "Draft2.log"
    log2 = ROOT.parent / "Draft2_sweep.log"
    for p in (log1, log2):
        if not p.exists():
            sys.exit(f"missing: {p}")

    rows1 = parse(log1)
    rows2 = parse(log2)
    validate(rows1, log1.name)
    print()
    validate(rows2, log2.name)

    # ---------- overlap cross-check at RB = 200 kΩ ----------
    print("\n" + "=" * 72)
    print("重叠点交叉验证 @ RB = 200 kΩ —— 检验重建模型是否与原电路同一套")
    print("=" * 72)
    d1 = {(r["vbp"], round(r["iref"] * 1e6, 6), r["rb"]): r for r in rows1}
    d2 = {(r["vbp"], round(r["iref"] * 1e6, 6), r["rb"]): r for r in rows2}
    keys = sorted(k for k in d1 if k[2] == 200000 and k in d2)
    print(f"可对比组合数: {len(keys)}  (期望 30 = 6 VBP x 5 IREF)")
    print(f"{'VBP':>5} {'IREF':>5} | {'IBONE_1':>12} {'IBONE_2':>12} {'Δrel':>10} "
          f"| {'IERR_1':>9} {'IERR_2':>9} | PASS")
    worst_i, worst_e, mism = (0.0, None), (0.0, None), []
    for k in keys:
        a, b = d1[k], d2[k]
        rel = abs(a["IBONE"] - b["IBONE"]) / a["IBONE"]
        de = abs(a["IERR"] - b["IERR"])
        if rel > worst_i[0]:
            worst_i = (rel, k)
        if de > worst_e[0]:
            worst_e = (de, k)
        if a["PASS"] != b["PASS"]:
            mism.append(k)
        print(f"{k[0]:>5} {k[1]:>5.0f} | {a['IBONE']*1e6:>12.6f} "
              f"{b['IBONE']*1e6:>12.6f} {rel:>10.2e} | {a['IERR']:>9.4f} "
              f"{b['IERR']:>9.4f} | {a['PASS']}{b['PASS']}"
              + ("   <== PASS 不一致" if a["PASS"] != b["PASS"] else ""))
    print(f"\nIBONE 最大相对偏差 : {worst_i[0]:.3e}  @ {worst_i[1]}")
    print(f"IERR  最大绝对偏差 : {worst_e[0]:.3e} %pt  @ {worst_e[1]}")
    print(f"PASS 判定不一致数  : {len(mism)} {mism if mism else ''}")

    (WORK / "parsed_raw_sweep2.json").write_text(
        json.dumps(rows2), encoding="utf-8")
    print(f"\n[out] {WORK/'parsed_raw_sweep2.json'}")


if __name__ == "__main__":
    main()
