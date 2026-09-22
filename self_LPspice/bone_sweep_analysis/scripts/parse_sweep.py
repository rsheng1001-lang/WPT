#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic sweep parser + validator, and optional cross-check against an earlier
parsed sweep at an overlapping RB value.

Usage
-----
  python parse_sweep.py <log> <out.json> [--ref <earlier.json>] [--at-rb <ohms>]

  # parse the newest sweep and cross-check it against the previous one at 1 MΩ
  python parse_sweep.py ../Draft2_sweep.log ../work/parsed_raw_sweep3.json \
         --ref ../work/parsed_raw_sweep2.json --at-rb 1000000

Validation performed
--------------------
  * every .step line joined to its .meas results by step index
  * independent check: VBONE / IBONE must reproduce that step's RB (Ohm's law on
    R_BONE) -> proves the step<->measurement pairing is correct
  * PASS must equal (IERR <= 1)
  * grid completeness / duplicates / missing values
"""
import argparse
import json
import re
import sys
from pathlib import Path

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
        tok = m.group(2).split()[0]
        try:
            meas[cur][int(m.group(1))] = float(tok)
        except ValueError:
            meas[cur][int(m.group(1))] = None
    rows = []
    for i, (vbp, iref, rb) in enumerate(steps, start=1):
        get = lambda k: meas.get(k, {}).get(i)          # noqa: E731
        p = get("pass")
        rows.append({"step": i, "vbp": vbp, "iref": iref, "rb": rb,
                     "IBONE": get("ibone"), "VBONE": get("vbone"),
                     "IERR": get("ierr"),
                     "PASS": None if p is None else int(p)})
    return rows


def validate(rows, name):
    print(f"--- {name} ---")
    print(f"  行数              : {len(rows)}")
    miss = [r["step"] for r in rows
            if any(r[k] is None for k in ("IBONE", "VBONE", "IERR", "PASS"))]
    print(f"  缺失测量          : {len(miss)} {miss[:10]}")
    combos = {(r["vbp"], r["iref"], r["rb"]) for r in rows}
    print(f"  唯一组合 / 行数   : {len(combos)} / {len(rows)}")
    vbps = sorted({r["vbp"] for r in rows})
    irefs = sorted({r["iref"] for r in rows})
    rbs = sorted({r["rb"] for r in rows})
    print(f"  VBP               : {vbps}")
    print(f"  IREF              : {[round(i*1e6, 6) for i in irefs]} uA")
    print(f"  RB                : {rbs[0]:.0f} .. {rbs[-1]:.0f} Ohm, {len(rbs)} 点, "
          f"步长 {(rbs[1]-rbs[0]) if len(rbs) > 1 else 0:.0f}")
    worst = (0.0, None)
    for r in rows:
        if r["IBONE"] and r["VBONE"]:
            e = abs(r["VBONE"] / r["IBONE"] - r["rb"]) / r["rb"]
            if e > worst[0]:
                worst = (e, r["step"])
    print(f"  RB 反算最大误差   : {worst[0]:.3e} (step {worst[1]})")
    bad = [r["step"] for r in rows
           if r["IERR"] is not None and r["PASS"] != int(r["IERR"] <= 1.0)]
    print(f"  PASS 与 IERR 不一致: {len(bad)}")
    np_ = sum(1 for r in rows if r["PASS"] == 1)
    print(f"  PASS=1 / PASS=0   : {np_} / {len(rows)-np_}")
    return len(miss) == 0 and len(combos) == len(rows)


def crosscheck(refrows, rows, at_rb):
    d1 = {(r["vbp"], round(r["iref"] * 1e6, 6), r["rb"]): r for r in refrows}
    d2 = {(r["vbp"], round(r["iref"] * 1e6, 6), r["rb"]): r for r in rows}
    keys = sorted(k for k in d1 if k[2] == at_rb and k in d2)
    print("\n" + "=" * 72)
    print(f"重叠点交叉验证 @ RB = {at_rb/1000:.0f} kΩ —— 两次运行是否同一套电路")
    print("=" * 72)
    print(f"可对比组合数: {len(keys)}")
    if not keys:
        print("  （无重叠点，跳过）")
        return
    worst_i, worst_e, mism = 0.0, 0.0, []
    for k in keys:
        a, b = d1[k], d2[k]
        worst_i = max(worst_i, abs(a["IBONE"] - b["IBONE"]) / a["IBONE"])
        worst_e = max(worst_e, abs(a["IERR"] - b["IERR"]))
        if a["PASS"] != b["PASS"]:
            mism.append(k)
    print(f"IBONE 最大相对偏差 : {worst_i:.3e}")
    print(f"IERR  最大绝对偏差 : {worst_e:.3e} %pt")
    print(f"PASS 判定不一致数  : {len(mism)}")
    if worst_i == 0.0 and not mism:
        print("  → 逐位完全一致：两次运行是同一电路、同一模型")
    else:
        print("  → 存在差异，需检查电路或模型是否被改动")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("out")
    ap.add_argument("--ref")
    ap.add_argument("--at-rb", type=float)
    a = ap.parse_args()

    logp, outp = Path(a.log), Path(a.out)
    if not logp.exists():
        sys.exit(f"missing log: {logp}")
    rows = parse(logp)
    ok = validate(rows, logp.name)
    if not ok:
        sys.exit("VALIDATION FAILED — refusing to write output")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(rows), encoding="utf-8")
    print(f"\n[out] {outp}")

    if a.ref:
        refrows = json.loads(Path(a.ref).read_text(encoding="utf-8"))
        at = a.at_rb if a.at_rb else max(r["rb"] for r in refrows
                                         if any(x["rb"] == r["rb"] for x in rows))
        crosscheck(refrows, rows, at)


if __name__ == "__main__":
    main()
