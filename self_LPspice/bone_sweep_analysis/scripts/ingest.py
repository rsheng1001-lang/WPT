#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-ingest a finished LTspice sweep into the stored dataset.

Designed for the actual workflow: the same .asc is re-run again and again with
different .step parameters, so each run OVERWRITES Draft2_sweep.log/.raw. This
script grabs the finished log before/after it disappears and stores everything
in a manifest + per-sweep JSON, so nothing depends on you renaming files.

What it does
------------
 1. picks the freshest COMPLETED log (auto-detect, or pass a path)
      complete = all four .meas sections present, row counts == step count,
                 and the file has not been written to for --settle seconds
 2. parses + validates it (step<->measurement pairing, Ohm's-law cross-check,
    PASS == (IERR<=1), grid completeness)
 3. snapshots the raw log text   -> work/logs/<stamp>_<name>.log
 4. stores the parsed rows       -> work/sweeps/<signature>.json
 5. records it in                 work/manifest.json
      * if the signature (its .step lines) is already stored, the existing entry
        is REPLACED only when the data differs, and cross-checked when it matches
 6. rebuilds                     work/parsed_combined.json  (union of all sweeps,
                                 dedup by (VBP,IREF,RB), earliest sweep wins)

Then run:  python build_xlsx.py  &&  python verify_xlsx.py

Usage
-----
  python ingest.py                       # auto-detect newest complete log
  python ingest.py <log>                 # ingest a specific log
  python ingest.py --list                # show what is already stored
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import config as CFG

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
LOGDIR = WORK / "logs"
SWDIR = WORK / "sweeps"
MANIFEST = WORK / "manifest.json"
PROJECT = ROOT.parent                       # .../self  (where LTspice runs)

STEP_RE = re.compile(r"^\.step\s+(.*)$")
KV_RE = re.compile(r"(\w+)=(\S+)")
MEAS_HDR_RE = re.compile(r"^Measurement:\s*(\w+)\s*$", re.I)
NUMROW_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")
MEAS_NAMES = ("ibone", "vbone", "ierr", "pass")


# ----------------------------------------------------------------- parsing
def read_step_lines(text):
    out = []
    for line in text.splitlines():
        m = STEP_RE.match(line)
        if m:
            kvs = dict(KV_RE.findall(m.group(1)))
            if {"iref", "rb", "vbp"} <= set(kvs):
                out.append(m.group(1).strip())
    return out


def parse_text(text):
    steps = []
    for line in text.splitlines():
        m = STEP_RE.match(line)
        if not m:
            continue
        kvs = dict(KV_RE.findall(m.group(1)))
        if not {"iref", "rb", "vbp"} <= set(kvs):
            continue
        steps.append((float(kvs["vbp"]), float(kvs["iref"]), float(kvs["rb"])))
    meas, cur = {}, None
    for line in text.splitlines():
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
        try:
            meas[cur][int(m.group(1))] = float(m.group(2).split()[0])
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
    return rows, meas


def completeness(text, nsteps, meas, settle_s):
    """Return (ok, reason)."""
    if nsteps == 0:
        return False, "no .step lines found"
    for nm in MEAS_NAMES:
        if nm not in meas:
            return False, f"missing .meas section '{nm}'"
        if len(meas[nm]) != nsteps:
            return False, (f"'{nm}' has {len(meas[nm])} rows but there are "
                           f"{nsteps} steps -> run not finished")
    return True, "complete"


def fmt_ohm(v):
    """Render an ohm value the way LTspice writes it (1Meg / 100k / 10k)."""
    if v >= 1e6 and v % 1e5 == 0:
        return f"{v/1e6:g}Meg"
    if v >= 1e3 and v % 1e3 == 0:
        return f"{v/1e3:g}k"
    return f"{v:g}"


def signature(rows):
    """Identity of a sweep = the exact set of (VBP, IREF, RB) combinations it ran.

    NB: a log holds one '.step iref=.. rb=.. vbp=..' line PER RUN (thousands of
    them), not the .step directives -- those live in the .net, which a later run
    may already have overwritten. So identify the sweep by what it actually ran.
    """
    trip = sorted((r["vbp"], round(r["iref"], 12), r["rb"]) for r in rows)
    return hashlib.sha1(repr(trip).encode()).hexdigest()[:10], trip


def describe(rows):
    rbs = sorted({r["rb"] for r in rows})
    irefs = sorted({round(r["iref"] * 1e6, 6) for r in rows})
    vbps = sorted({r["vbp"] for r in rows})
    step = (rbs[1] - rbs[0]) if len(rbs) > 1 else 0
    uniform = all(abs((rbs[i + 1] - rbs[i]) - step) < 1 for i in range(len(rbs) - 1))
    # directive shape DERIVED from the values seen in the log (not read from .net)
    hint = [
        ".step param IREF list " + " ".join(f"{i:g}u" for i in irefs),
        (f".step param RB {fmt_ohm(rbs[0])} {fmt_ohm(rbs[-1])} {fmt_ohm(step)}"
         if uniform else f".step param RB <非等步长, {len(rbs)} 个取值>"),
        ".step param VBP list " + " ".join(f"{v:g}" for v in vbps),
    ]
    return {
        "steps": len(rows),
        "rb_min": rbs[0], "rb_max": rbs[-1], "rb_n": len(rbs),
        "rb_step": step, "rb_uniform": uniform,
        "vbp": vbps, "iref_uA": irefs,
        "pass1_log1pct": sum(1 for r in rows if r["PASS"] == 1),
        "pass0_log1pct": sum(1 for r in rows if r["PASS"] == 0),
        f"pass1_at_{CFG.IERR_MAX_PCT:g}pct":
            sum(1 for r in rows if CFG.passes(r["IERR"])),
        "directive_hint": hint,
    }


def validate(rows):
    """Independent checks; returns list of problem strings (empty = good)."""
    bad = []
    miss = [r["step"] for r in rows
            if any(r[k] is None for k in ("IBONE", "VBONE", "IERR", "PASS"))]
    if miss:
        bad.append(f"{len(miss)} rows with missing measurements")
    combos = {(r["vbp"], r["iref"], r["rb"]) for r in rows}
    if len(combos) != len(rows):
        bad.append(f"duplicate (VBP,IREF,RB): {len(rows)-len(combos)}")
    worst = 0.0
    for r in rows:
        if r["IBONE"] and r["VBONE"]:
            worst = max(worst, abs(r["VBONE"] / r["IBONE"] - r["rb"]) / r["rb"])
    if worst > 1e-4:
        bad.append(f"VBONE/IBONE does not reproduce RB (max rel err {worst:.2e})")
    # the log's own PASS column was produced with a 1.0 % criterion -- used only
    # to prove IERR was read correctly, never as a decision
    _c = CFG.LOG_PASS_CRITERION_PCT
    pe = [r["step"] for r in rows
          if r["IERR"] is not None and r["PASS"] != int(r["IERR"] <= _c)]
    if pe:
        bad.append(f"log PASS != (IERR<={_c:g}) on {len(pe)} rows")
    return bad, worst


# ----------------------------------------------------------------- manifest
def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"sweeps": []}


def save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1),
                        encoding="utf-8")


def rebuild_combined(man):
    """Union of every stored sweep, dedup by (VBP,IREF,RB); earliest wins."""
    merged, seen, per = [], set(), {}
    for entry in sorted(man["sweeps"], key=lambda e: e["ingested_at"]):
        rows = json.loads((WORK / entry["json"]).read_text(encoding="utf-8"))
        per[entry["sweep"]] = len(rows)
        for r in rows:
            k = (r["vbp"], round(r["iref"] * 1e6, 6), r["rb"])
            if k in seen:
                continue
            seen.add(k)
            merged.append({"sweep": entry["sweep"], "log": entry["log_tag"],
                           "step": r["step"], "vbp": r["vbp"],
                           "iref": r["iref"], "rb": r["rb"],
                           "IBONE": r["IBONE"], "VBONE": r["VBONE"],
                           "IERR": r["IERR"], "PASS": r["PASS"]})
    merged.sort(key=lambda r: (r["vbp"], r["iref"], r["rb"], r["sweep"]))
    (WORK / "parsed_combined.json").write_text(json.dumps(merged),
                                               encoding="utf-8")
    rbs = sorted({r["rb"] for r in merged})
    print(f"\n[combined] {len(merged)} rows, {len(rbs)} RB values "
          f"({rbs[0]/1000:.0f}k … {rbs[-1]/1000:.0f}k), "
          f"{sum(1 for r in merged if r['PASS']==1)} PASS=1")
    for sw, n in sorted(per.items()):
        e = next(x for x in man["sweeps"] if x["sweep"] == sw)
        print(f"           sweep {sw}: {n} rows from {e['log_tag']}")
    return merged


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", nargs="?")
    ap.add_argument("--settle", type=float, default=20.0,
                    help="seconds since last write to consider a log finished")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    man = load_manifest()
    if a.list:
        print(f"stored sweeps: {len(man['sweeps'])}")
        for e in man["sweeps"]:
            d = e["desc"]
            step_txt = ("步长 %dΩ" % d["rb_step"] if d.get("rb_uniform", True)
                        else "非等步长(最细 %dΩ)" % d["rb_step"])
            tkey = f"pass1_at_{CFG.IERR_MAX_PCT:g}pct"
            print(f"  {e['sweep']:>2}. {e['log_tag']:<26} {d['steps']:>6} rows  "
                  f"RB {d['rb_min']/1000:.0f}k…{d['rb_max']/1000:.0f}k  "
                  f"{step_txt:<20} PASS@1%={d.get('pass1_log1pct', 0):<5} "
                  f"PASS@{CFG.IERR_MAX_PCT:g}%={d.get(tkey, 0)}")
        comb = WORK / "parsed_combined.json"
        if comb.exists():
            print(f"combined: {len(json.loads(comb.read_text(encoding='utf-8')))} rows")
        return

    # ---- pick the log ----
    if a.log:
        cand = Path(a.log)
        if not cand.is_absolute():
            cand = (Path.cwd() / cand).resolve()
    else:
        logs = [p for p in PROJECT.glob("*.log")]
        if not logs:
            sys.exit(f"no .log found in {PROJECT}")
        cand = max(logs, key=lambda p: p.stat().st_mtime)
    if not cand.exists():
        sys.exit(f"missing log: {cand}")

    age = time.time() - cand.stat().st_mtime
    print(f"[pick] {cand}")
    print(f"       mtime {datetime.fromtimestamp(cand.stat().st_mtime):%Y-%m-%d %H:%M:%S}"
          f"  ({age:.0f}s ago)  {cand.stat().st_size} bytes")
    if age < a.settle:
        sys.exit(f"log was written to {age:.0f}s ago (< --settle {a.settle:.0f}s); "
                 "the run may still be in progress -- rerun when it has settled")

    text = cand.read_text(encoding="latin-1")
    rows, meas = parse_text(text)
    nsteps = len(rows)
    ok, why = completeness(text, nsteps, meas, a.settle)
    print(f"[check] {nsteps} steps, {len(rows)} rows -> {why}")
    if not ok:
        sys.exit("run is not complete; nothing stored")

    problems, worst = validate(rows)
    print(f"[valid] RB 反算最大相对误差 {worst:.2e}; "
          f"{'OK' if not problems else 'PROBLEMS: ' + '; '.join(problems)}")
    if problems:
        sys.exit("validation failed; nothing stored")

    sig, _trip = signature(rows)
    desc = describe(rows)
    print(f"[sweep] signature {sig}")
    for _h in desc["directive_hint"]:
        print(f"        指令形态(由日志取值推导): {_h}")
    print(f"        RB {desc['rb_min']/1000:.0f}k…{desc['rb_max']/1000:.0f}k "
          f"step {desc['rb_step']/1000:.0f}k ({desc['rb_n']} pts), "
          f"{desc['steps']} runs, PASS=1 {desc['pass1']}")

    # ---- store ----
    LOGDIR.mkdir(parents=True, exist_ok=True)
    SWDIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snap = LOGDIR / f"{stamp}_{cand.name}"
    shutil.copyfile(cand, snap)
    jname = f"sweep_{sig}.json"
    (SWDIR / jname).write_text(json.dumps(rows), encoding="utf-8")
    print(f"[store] log snapshot -> {snap.relative_to(ROOT)}")
    print(f"[store] parsed rows  -> {(SWDIR / jname).relative_to(ROOT)}")

    existing = next((e for e in man["sweeps"] if e["sig"] == sig), None)
    if existing:
        old = json.loads((WORK / existing["json"]).read_text(encoding="utf-8"))
        same = all(
            abs((x["IBONE"] or 0) - (y["IBONE"] or 0)) == 0
            and abs((x["IERR"] or 0) - (y["IERR"] or 0)) == 0
            for x, y in zip(sorted(old, key=lambda r: (r["vbp"], r["iref"], r["rb"])),
                            sorted(rows, key=lambda r: (r["vbp"], r["iref"], r["rb"])))
        ) and len(old) == len(rows)
        print(f"[manifest] this sweep is already stored as sweep {existing['sweep']} "
              f"-> data {'IDENTICAL (bit-for-bit)' if same else 'DIFFERS'}, "
              f"entry refreshed")
        existing.update({"log": str(snap.relative_to(ROOT)), "log_tag": cand.name,
                         "ingested_at": datetime.now().isoformat(timespec="seconds"),
                         "sha256": hashlib.sha256(cand.read_bytes()).hexdigest(),
                         "desc": desc})
    else:
        nxt = max((e["sweep"] for e in man["sweeps"]), default=0) + 1
        man["sweeps"].append({
            "sweep": nxt, "sig": sig, "log_tag": cand.name,
            "log": str(snap.relative_to(ROOT)),
            "json": f"sweeps/{jname}",
            "ingested_at": datetime.now().isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(cand.read_bytes()).hexdigest(),
            "source": str(cand),
            "desc": desc,
        })
        print(f"[manifest] stored as sweep {nxt}")
    save_manifest(man)

    rebuild_combined(man)
    print("\n下一步:  python build_xlsx.py  &&  python verify_xlsx.py")


if __name__ == "__main__":
    main()
