#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Iterative fine-scan refinement of every constant-current boundary.

For each (VBP, IREF) combination that has a real PASS->FAIL crossing, the current
data locates it only to the resolution of the sweep that found it (1 kΩ for the
low-RB range, 10 kΩ above 200 kΩ). This script repeatedly

    narrow the window around the crossing -> run LTspice -> ingest -> re-locate

until every window is <= --target ohms (default 10 Ω).

Deck construction
-----------------
One deck per (VBP, IREF) combination, with IREF and VBP fixed via `.param` and
only RB swept as a `.step param RB list ...`. That matters: LTspice 26 REFUSES a
single-valued `.step` ("This results in only one step", exit code 1, no output),
so IREF/VBP must NOT be swept when only one value is wanted.
Batching all windows into one deck instead would simulate every RB value for all
30 combinations and cost ~25x more runs.

Stored round data lands in work/sweeps/ and is registered in work/manifest.json,
so the Excel pipeline picks it up with no code changes.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
REFINE = ROOT / "refine"
PROJECT = ROOT.parent
LTSPICE = Path(r"D:\Program Files\LTspice\LTspice.exe")
BASE_NET = ROOT / "restore" / "Draft2.net.original"
COMBINED = WORK / "parsed_combined.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest as ig                                    # noqa: E402
import config as CFG                                   # noqa: E402


def fmt_ohm_lt(v):
    """LTspice-style resistance literal."""
    r = round(v)
    if r >= 1e6 and r % 1e6 == 0:
        return f"{r/1e6:g}Meg"
    if r >= 1e3:
        s = f"{r/1e3:.6f}".rstrip("0").rstrip(".")
        return f"{s}k"
    return f"{r:g}"


def deck_body():
    """Circuit + .meas + .tran, taken verbatim from the authoritative netlist."""
    lines = BASE_NET.read_text(encoding="utf-8").splitlines()
    body = [l for l in lines
            if l.strip()
            and not l.startswith((".step", ".param R5SET", "* D:"))
            and l != ".end"]
    return body


def make_deck(body, vbp, iref_uA, rb_values):
    txt = ["* refine deck  VBP=%g V  IREF=%guA  RB %s..%s (%d pts, step %s)"
           % (vbp, iref_uA, fmt_ohm_lt(min(rb_values)), fmt_ohm_lt(max(rb_values)),
              len(rb_values),
              fmt_ohm_lt(rb_values[1] - rb_values[0]) if len(rb_values) > 1 else "-"),
           *body,
           f".param IREF={iref_uA}u",
           f".param VBP={vbp:g}",
           ".param R5SET=10k*(3.3/(IREF*3k)-1)",
           ".step param RB list " + " ".join(fmt_ohm_lt(v) for v in rb_values),
           ".end"]
    return "\n".join(txt) + "\n"


def boundaries(rows):
    """(VBP,IREF) -> (lastPASS_RB, firstFAIL_RB) using the stored dataset."""
    g, rbs = {}, sorted({r["rb"] for r in rows})
    for r in rows:
        g[(r["vbp"], round(r["iref"] * 1e6, 6), r["rb"])] = r
    # PASS is derived from IERR and the configured threshold, never from the
    # log's own 1.0 % PASS column
    ok = lambda r: CFG.passes(r["IERR"])                      # noqa: E731
    out = {}
    for v in sorted({r["vbp"] for r in rows}):
        for i in sorted({round(r["iref"] * 1e6, 6) for r in rows}):
            passr = [rb for rb in rbs if (v, i, rb) in g and ok(g[(v, i, rb)])]
            if not passr:
                continue                        # never passes: nothing to locate
            lastP = max(passr)
            failr = [rb for rb in rbs
                     if rb > lastP and (v, i, rb) in g and not ok(g[(v, i, rb)])]
            if not failr:
                continue                        # passes to the very top: no crossing yet
            out[(v, i)] = (lastP, min(failr))
    return out


def run_decks(jobs, parallel):
    """jobs: list of (deck_path, log_path, meta). Runs LTspice -b, returns results."""
    todo = list(jobs)
    running, results = [], []
    while todo or running:
        while todo and len(running) < parallel:
            deck, log, meta = todo.pop(0)
            for junk in (log, log.with_suffix(".raw"), log.with_suffix(".db"),
                         Path(str(log.with_suffix("")) + ".op.raw")):
                if junk.exists():
                    junk.unlink()
            p = subprocess.Popen([str(LTSPICE), "-b", deck.name],
                                 cwd=str(deck.parent),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            running.append((p, deck, log, meta, time.time()))
        time.sleep(0.4)
        for item in list(running):
            p, deck, log, meta, t0 = item
            if p.poll() is not None:
                running.remove(item)
                results.append((deck, log, meta, p.returncode, time.time() - t0))
        if time.time() - (running[0][4] if running else time.time()) > 600:
            for p, *_ in running:
                p.kill()
            sys.exit("deck timed out after 600s")
    return results


RB_STEP_RE = re.compile(r"^\.step\s+rb=(\S+)\s*$")


def parse_refine_log(path):
    """Parse a refine deck's log.

    These decks fix IREF/VBP via .param and step ONLY RB, so the log carries
    '.step rb=<value>' lines instead of the three-parameter form that
    ingest.parse_text expects. Step order == RB order, so zip them directly.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="latin-1")
    rbs = [float(m.group(1)) for m in
           (RB_STEP_RE.match(l) for l in text.splitlines()) if m]
    meas, cur = {}, None
    for line in text.splitlines():
        mh = ig.MEAS_HDR_RE.match(line)
        if mh:
            cur = mh.group(1).lower()
            meas[cur] = {}
            continue
        if cur is None or not line.strip():
            continue
        m = ig.NUMROW_RE.match(line)
        if not m:
            continue
        try:
            meas[cur][int(m.group(1))] = float(m.group(2).split()[0])
        except ValueError:
            meas[cur][int(m.group(1))] = None
    if not rbs:
        print("      no '.step rb=' lines in log")
        return None
    for nm in ("ibone", "vbone", "ierr", "pass"):
        if len(meas.get(nm, {})) != len(rbs):
            print(f"      '{nm}' rows {len(meas.get(nm, {}))} != {len(rbs)} steps")
            return None
    rows = []
    for k, rb in enumerate(rbs):
        i = k + 1
        p = meas["pass"].get(i)
        rows.append({"step": i, "rb": rb,
                     "IBONE": meas["ibone"].get(i), "VBONE": meas["vbone"].get(i),
                     "IERR": meas["ierr"].get(i),
                     "PASS": None if p is None else int(p)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=10.0,
                    help="stop when the PASS->FAIL window is <= this many ohms")
    ap.add_argument("--points", type=int, default=11,
                    help="sample points per window per round")
    ap.add_argument("--max-rounds", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=6)
    a = ap.parse_args()

    if not LTSPICE.exists():
        sys.exit(f"LTspice not found at {LTSPICE}")
    if not BASE_NET.exists():
        sys.exit(f"missing authoritative netlist {BASE_NET}")

    # each invocation gets its own deck folder so a later round cannot silently
    # overwrite the record of an earlier one (the same trap as the .log files)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    global REFINE
    REFINE = REFINE / f"decks_{stamp}"
    REFINE.mkdir(parents=True, exist_ok=True)
    body, man = deck_body(), ig.load_manifest()
    print(f"[start] decks -> {REFINE.relative_to(ROOT)}")
    rows = json.loads(COMBINED.read_text(encoding="utf-8"))
    print(f"[start] stored dataset: {len(rows)} rows, "
          f"{len({r['rb'] for r in rows})} RB values")
    print(f"[start] PASS criterion: IERR <= {CFG.IERR_MAX_PCT:g}%")
    print(f"[start] target window <= {a.target:g} Ω, {a.points} points/round, "
          f"rounds <= {a.max_rounds}")

    for rnd in range(1, a.max_rounds + 1):
        b = boundaries(rows)
        need = {k: v for k, v in b.items() if v[1] - v[0] > a.target}
        if not need:
            print(f"\n[round {rnd}] nothing left to refine — every crossing is "
                  f"within {a.target:g} Ω")
            break
        print(f"\n{'='*74}\n[round {rnd}] {len(need)} combination(s) above "
              f"{a.target:g} Ω")
        jobs, meta = [], {}
        for (v, i), (lo, hi) in sorted(need.items()):
            vals = sorted({round(lo + (hi - lo) * k / (a.points - 1))
                           for k in range(a.points)})
            name = f"r{rnd}_{str(v).replace('.','p')}V_{int(i)}uA"
            deck = REFINE / f"{name}.net"
            deck.write_text(make_deck(body, v, i, vals), encoding="utf-8")
            jobs.append((deck, deck.with_suffix(".log"), (v, i, vals)))
            print(f"  VBP={v:>4} V {i:>3.0f} µA : {lo/1000:.3f} … {hi/1000:.3f} kΩ "
                  f"-> step {(vals[1]-vals[0])/1000:.4f} kΩ ({len(vals)} pts)")
        t0 = time.time()
        res = run_decks(jobs, a.parallel)
        print(f"[round {rnd}] {len(res)} deck(s) finished in {time.time()-t0:.1f}s")
        new, bad = [], 0
        for deck, log, (v, i, vals), rc, dt in res:
            got = parse_refine_log(log)
            if got is None:
                bad += 1
                print(f"    !! {deck.name}: no usable log (rc={rc})")
            else:
                # these decks fix IREF/VBP via .param -> stamp them onto each row
                for r in got:
                    r["vbp"], r["iref"] = v, i / 1e6
                new.extend(got)
            # always drop the bulky simulator output
            for junk in (log.with_suffix(".raw"), log.with_suffix(".db"),
                         Path(str(log.with_suffix("")) + ".op.raw"),
                         Path(str(log) + ".raw")):
                if junk.exists():
                    junk.unlink()
        if bad:
            print(f"    {bad} deck(s) failed; keeping the rest")
        if not new:
            print("    no new data this round — stopping")
            break

        # validate and store the round
        problems, worst = ig.validate(new)
        print(f"[round {rnd}] {len(new)} new rows, RB 反算最大相对误差 {worst:.2e}"
              + (f", PROBLEMS: {problems}" if problems else ", OK"))
        sig, _ = ig.signature(new)
        if not sig:
            print("    empty signature -- not storing"); break
        jname = f"sweep_{sig}.json"
        (ig.SWDIR / jname).write_text(json.dumps(new), encoding="utf-8")
        desc = ig.describe(new)
        desc["directive_hint"] = [f"精细化扫描 第 {rnd} 轮：{len(need)} 个组合的临界窗口，"
                                  f"每窗口 {a.points} 点",
                                  f"RB {fmt_ohm_lt(desc['rb_min'])} … {fmt_ohm_lt(desc['rb_max'])}"
                                  f"（非等步长，逐窗口细分）"]
        entry = next((e for e in man["sweeps"] if e.get("sig") == sig), None)
        if entry:
            entry["ingested_at"] = datetime.now().isoformat(timespec="seconds")
            print(f"[round {rnd}] identical round already stored as sweep "
                  f"{entry['sweep']}; refreshed")
        else:
            nxt = max((e["sweep"] for e in man["sweeps"]), default=0) + 1
            # all windows in a round share one step: take the smallest gap
            _rb = sorted({r["rb"] for r in new})
            _gaps = [_rb[k+1] - _rb[k] for k in range(len(_rb)-1) if _rb[k+1] > _rb[k]]
            _step = min(_gaps) if _gaps else 0
            man["sweeps"].append({
                "sweep": nxt, "sig": sig,
                "log_tag": f"refine ({fmt_ohm_lt(_step)} 步长)" if _step else "refine",
                "log": "", "json": f"sweeps/{jname}",
                "ingested_at": datetime.now().isoformat(timespec="seconds"),
                "sha256": "", "source": "refine.py", "desc": desc,
                "note": (f"精细化扫描：{len(need)} 个临界窗口 × {a.points} 点，"
                         f"步长 {fmt_ohm_lt(_step)}")})
            print(f"[round {rnd}] stored as sweep {nxt}")
        ig.save_manifest(man)
        rows = ig.rebuild_combined(man)

    # ---- final report ----
    b = boundaries(rows)
    print(f"\n{'='*74}\n[final] 收敛后的临界窗口\n{'='*74}")
    print(f"{'VBP':>5} {'IREF':>5} | {'lastPASS':>12} {'firstFAIL':>12} "
          f"{'窗口':>9} | {'Rmax(kΩ)':>9} {'IERR@Rmax%':>10}")
    g = {(r["vbp"], round(r["iref"] * 1e6, 6), r["rb"]): r for r in rows}
    worst_w = 0
    for (v, i), (lo, hi) in sorted(b.items()):
        w = hi - lo
        worst_w = max(worst_w, w)
        print(f"{v:>5} {i:>5.0f} | {lo:>12,.0f} {hi:>12,.0f} {w:>9,.0f} | "
              f"{lo/1000:>9.3f} {g[(v,i,lo)]['IERR']:>10.4f}")
    skipped = [(v, i) for (v, i) in
               sorted({(r["vbp"], round(r["iref"] * 1e6, 6)) for r in rows})
               if (v, i) not in b]
    print(f"\n无临界区的组合（全程 FAIL，无可定界）: {len(skipped)} 个")
    for v, i in skipped:
        print(f"   VBP={v:g} V {i:.0f} µA")
    print(f"\n最大窗口 = {worst_w:,.0f} Ω  目标 {a.target:g} Ω  "
          f"→ {'达标' if worst_w <= a.target else '未达标（见上）'}")
    print("\n下一步:  python build_xlsx.py  &&  python verify_xlsx.py")


if __name__ == "__main__":
    main()
