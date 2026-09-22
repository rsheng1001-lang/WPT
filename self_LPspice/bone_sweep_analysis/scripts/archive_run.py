#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Archive a finished LTspice run -- deck, log, schematic AND waveform -- into
runs_archive/, so that re-running the same .asc cannot destroy the record.

Why this exists
---------------
Every sweep in this project runs from the same .asc in the project root, so each
run OVERWRITES <name>.log / .raw / .net / .op.raw / .db. Scan B's log and its
398 MB .raw were lost exactly that way; only its 2430 parsed rows survived in
work/sweeps/. ingest.py snapshots the LOG of every sweep it stores, but nothing
ever kept the waveforms or the decks. This script does.

What it does
------------
 1. finds runs in the project root -- files sharing a basename, one of
    .asc / .net / .log / .raw / .op.raw / .db
 2. skips a run that is already archived (same basename + same log sha256), one
    whose log is still being written (< --settle seconds), or one whose log is
    an INCOMPLETE sweep (the same completeness gate ingest.py uses)
 3. copies the small files (deck / log / op-point / db / schematic) and MOVES the
    bulky .raw by default -- --raw copy keeps it in the project root instead,
    --raw skip omits it
 4. checks whether the same-named .asc actually carries the directives of the
    archived .net. In this project it frequently does NOT: LTspice edits
    directives in memory, so a run leaves behind a .net that the saved .asc never
    matched. If another .asc in the project root does carry them, that schematic
    is archived too and labelled as the matching one.
 5. writes runs_archive/<stamp>_<name>_<sig>/meta.json, then rebuilds
    runs_archive/index.json and runs_archive/INDEX.md

Usage
-----
  python archive_run.py                  # archive every run not yet archived
  python archive_run.py --newest         # only the most recent one
  python archive_run.py Draft2_sweep     # one specific basename
  python archive_run.py --raw copy       # keep the .raw in the project root
  python archive_run.py --list           # show what is archived
  python archive_run.py --dry-run        # print the plan, touch nothing
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest as ig                                    # noqa: E402
import config as CFG                                   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent          # bone_sweep_analysis/
PROJECT = ROOT.parent                                  # self_LPspice/ (LTspice cwd)
ARCHIVE = PROJECT / "runs_archive"

# longest first: '.op.raw' must win over '.raw'
SUFFIXES = [".op.raw", ".asc", ".net", ".log", ".raw", ".db"]
ROLE = {".asc": "schematic", ".net": "deck", ".log": "log",
        ".op.raw": "oppoint", ".raw": "waveform", ".db": "db"}

ASC_TEXT_RE = re.compile(r"^TEXT\s+\S+\s+\S+\s+\S+\s+\S+\s+!(.*)$")
DIRECTIVE_RE = re.compile(r"^\.(step|param|tran|meas|dc|ac|op)\b")
WS_RE = re.compile(r"\s+")


# ------------------------------------------------------------------ helpers
def human(n):
    for u, s in ((1 << 30, "GB"), (1 << 20, "MB"), (1 << 10, "kB")):
        if n >= u:
            return f"{n/u:.1f} {s}"
    return f"{n} B"


def sha256_file(path, chunk=4 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def norm(line):
    return WS_RE.sub(" ", line.strip()).lower()


def net_directives(path):
    """Analysis directives (.step/.param/.tran/.meas/...) of a netlist."""
    out = set()
    for line in path.read_text(encoding="latin-1").splitlines():
        s = line.strip()
        if DIRECTIVE_RE.match(s):
            out.add(norm(s))
    return out


def asc_directives(path):
    """Analysis directives stored in an .asc as 'TEXT ... !<directive>' lines.

    LTspice packs a multi-line directive block into ONE TEXT line separated by a
    literal backslash-n.
    """
    out = set()
    for line in path.read_text(encoding="latin-1").splitlines():
        m = ASC_TEXT_RE.match(line)
        if not m:
            continue
        for part in m.group(1).split("\\n"):
            s = part.strip()
            if DIRECTIVE_RE.match(s):
                out.add(norm(s))
    return out


def find_runs(project):
    """basename -> {suffix: path}, for every basename that has a .log."""
    runs = {}
    for p in sorted(project.iterdir()):
        if not p.is_file():
            continue
        for suf in SUFFIXES:
            if p.name.endswith(suf) and len(p.name) > len(suf):
                runs.setdefault(p.name[:-len(suf)], {})[suf] = p
                break
    return {b: f for b, f in runs.items() if ".log" in f}


def pick_schematic(base, run, project):
    """(same-named .asc, matching .asc or None, same-named matches deck?)"""
    deck = run.get(".net")
    asc = run.get(".asc")
    if deck is None or not deck.exists():
        return asc, None, None
    want = net_directives(deck)
    verdict = asc_directives(asc) == want if asc and asc.exists() else None
    match = None
    if verdict is not True:
        for cand in sorted(project.glob("*.asc")):
            if asc is not None and cand.name == asc.name:
                continue
            if asc_directives(cand) == want:
                match = cand
                break
    return asc, match, verdict


def rb_range(sw):
    """RB span in LTspice notation (10k…200k / 1Meg…10Meg)."""
    if not sw or sw.get("rb_min") is None:
        return "—"
    return f"{ig.fmt_ohm(sw['rb_min'])}…{ig.fmt_ohm(sw['rb_max'])}"


# ------------------------------------------------------------- archive index
def load_index():
    f = ARCHIVE / "index.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"archive": str(ARCHIVE), "runs": []}


def rebuild_index():
    """Rebuild index.json + INDEX.md from the per-run meta.json files."""
    runs = []
    for d in sorted(ARCHIVE.iterdir()):
        meta = d / "meta.json"
        if d.is_dir() and meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            m["folder"] = d.name
            runs.append(m)
    runs.sort(key=lambda m: m["archived_at"])
    idx = {"archive": str(ARCHIVE), "updated": datetime.now().isoformat(timespec="seconds"),
           "runs": runs}
    (ARCHIVE / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1),
                                        encoding="utf-8")

    L = ["# runs_archive — 归档索引", "",
         "本文件由 `archive_run.py` 自动重建，不要手改。"
         "每一行对应一个子文件夹，文件夹里是那次运行的完整输出 + `meta.json`。", "",
         "| # | 文件夹 | 名称 | 运行时刻 | 行数 | RB 范围 | .raw | 入库 |",
         "|---|---|---|---|---|---|---|---|"]
    for k, m in enumerate(runs, 1):
        sw = m.get("sweep") or {}
        raw = next((f for f in m["files"] if f["role"] == "waveform"), None)
        rawtxt = (f"{human(raw['bytes'])} ({raw['action']})" if raw else "—")
        mi = sw.get("manifest_sweep")
        L.append("| {} | `{}` | {} | {} | {} | {} | {} | {} |".format(
            k, m["folder"], m["basename"],
            m.get("run_mtime", "?")[:16].replace("T", " "),
            sw.get("steps", "—"), rb_range(sw), rawtxt,
            f"sweep {mi}" if mi else ("未入库" if sw else "—")))
    L += ["", "`.raw` 的 action 是 `move` 表示波形已从工程根目录移入本文件夹"
          "（LTspice 下次运行会重新生成）；`copy` 表示原位置仍保留一份。", ""]
    (ARCHIVE / "INDEX.md").write_text("\n".join(L), encoding="utf-8")
    return idx


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="把 LTspice 一次运行的全部输出（含 .raw 波形）归档到 runs_archive/")
    ap.add_argument("name", nargs="?", help="只归档这个 basename（如 Draft2_sweep）")
    ap.add_argument("--newest", action="store_true", help="只归档最新的一次运行")
    ap.add_argument("--list", action="store_true", help="列出已归档的运行")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不动文件")
    ap.add_argument("--raw", choices=["move", "copy", "skip"], default="move",
                    help=".raw 波形的处理方式（默认 move：移入归档，工程根目录不再保留）")
    ap.add_argument("--settle", type=float, default=20.0,
                    help="日志静置多少秒才认为跑完了（默认 20）")
    ap.add_argument("--force", action="store_true",
                    help="跳过「已归档 / 未跑完」检查，强制归档")
    a = ap.parse_args()

    if a.list:
        idx = rebuild_index()
        if not idx["runs"]:
            print("归档区还是空的")
            return
        print(f"{'文件夹':<40} {'名称':<16} {'行数':>6} {'RB 范围':>18} {'.raw':>10}")
        for m in idx["runs"]:
            sw = m.get("sweep") or {}
            raw = next((f for f in m["files"] if f["role"] == "waveform"), None)
            print(f"{m['folder']:<40} {m['basename']:<16} {sw.get('steps', '—'):>6} "
                  f"{rb_range(sw):>18} {human(raw['bytes']) if raw else '—':>10}")
        return

    if not PROJECT.exists():
        sys.exit(f"工程目录不存在: {PROJECT}")
    ARCHIVE.mkdir(exist_ok=True)
    idx = load_index()
    have = {(m["basename"], m.get("log_sha256")) for m in idx["runs"]}
    man = ig.load_manifest()
    by_sig = {e["sig"]: e for e in man["sweeps"]}

    runs = find_runs(PROJECT)
    if a.name:
        if a.name not in runs:
            sys.exit(f"工程目录里没有名为 {a.name} 的运行（有: "
                     f"{', '.join(sorted(runs)) or '无'}）")
        runs = {a.name: runs[a.name]}
    if a.newest and runs:
        newest = max(runs, key=lambda b: runs[b][".log"].stat().st_mtime)
        runs = {newest: runs[newest]}
    if not runs:
        sys.exit(f"{PROJECT} 里没有找到任何 .log —— 没有可归档的运行")

    done, skipped = 0, []
    for base, run in sorted(runs.items()):
        log = run[".log"]
        age = time.time() - log.stat().st_mtime
        mt = datetime.fromtimestamp(log.stat().st_mtime).isoformat(timespec="seconds")
        print(f"\n=== {base} ===  ({log.name}, {human(log.stat().st_size)}, "
              f"mtime {mt}, {age:.0f}s ago)")

        if age < a.settle and not a.force:
            skipped.append((base, f"日志 {age:.0f}s 前还在写（< --settle {a.settle:g}s），"
                                  f"可能正在跑"))
            print(f"    skip: {skipped[-1][1]}")
            continue

        text = log.read_text(encoding="latin-1")
        rows, meas = ig.parse_text(text)
        nsteps = len(rows)
        if nsteps:
            ok, why = ig.completeness(text, nsteps, meas, a.settle)
            if not ok and not a.force:
                skipped.append((base, why))
                print(f"    skip: {why}")
                continue
            sig, _ = ig.signature(rows)
            desc = ig.describe(rows)
        else:
            sig, desc = None, None
            print("    提示: 日志里没有三参数 .step 展开 —— 不是整扫，按普通运行归档")
        log_sha = sha256_file(log)

        if (base, log_sha) in have and not a.force:
            skipped.append((base, "同样的日志已经归档过"))
            print(f"    skip: 同样的日志已经归档过 (sha256 {log_sha[:12]}…)")
            continue

        entry = by_sig.get(sig) if sig else None
        print(f"    sweep 签名 {sig or '—'}"
              + (f"，已入库 sweep {entry['sweep']}" if entry else
                 ("，尚未入库" if sig else ""))
              + (f"；日志 sha256 与入库记录{'一致' if entry and entry.get('sha256') == log_sha else '不一致'}"
                 if entry else ""))

        asc, match, verdict = pick_schematic(base, run, PROJECT)
        if verdict is False:
            print(f"    ⚠ 原理图指令与网表不一致：{asc.name} 不是产生这份日志的那一版")
            if match:
                print(f"      但 {match.name} 的指令与网表一致 -> 一并归档为匹配原理图")
            else:
                print("      工程目录里找不到匹配的原理图（那一版 .asc 从未存盘）")
        elif verdict is True:
            print(f"    原理图指令与网表一致：{asc.name}")

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tag = (sig[:8] if sig else log_sha[:8])
        folder = ARCHIVE / f"{stamp}_{base}_{tag}"

        plan = []
        for suf in SUFFIXES:
            p = run.get(suf)
            if p is None or not p.exists():
                continue
            if suf == ".raw" and a.raw == "skip":
                continue
            if suf == ".asc" and verdict is False and match is not None:
                pass                       # still archived, meta marks it mismatched
            action = "move" if (suf == ".raw" and a.raw == "move") else "copy"
            plan.append((p, suf, action, ROLE[suf]))
        if match is not None:
            plan.append((match, ".asc", "copy", "matching_schematic"))

        total = sum(p.stat().st_size for p, _s, act, _r in plan if act == "copy")
        moved = sum(p.stat().st_size for p, _s, act, _r in plan if act == "move")
        print(f"    归档 -> {folder.name}  复制 {human(total)}"
              + (f"，移动 {human(moved)}" if moved else "")
              + ("   [dry-run]" if a.dry_run else ""))
        if a.dry_run:
            for p, _s, act, role in plan:
                print(f"      {act:<4} {role:<18} {p.name}  {human(p.stat().st_size)}")
            continue

        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for p, suf, action, role in plan:
            dst = folder / p.name
            size = p.stat().st_size
            # hash before the move, while the bytes are still in place
            sha = sha256_file(p) if size < (1 << 31) else None
            try:
                if action == "move":
                    shutil.move(str(p), str(dst))
                else:
                    shutil.copyfile(p, dst)
            except OSError as e:
                print(f"      !! {p.name}: {e}")
                files.append({"name": p.name, "role": role, "bytes": size,
                              "sha256": sha, "action": "failed"})
                continue
            files.append({"name": p.name, "role": role, "bytes": size,
                          "sha256": sha, "action": action})
            print(f"      {action:<4} {role:<18} {p.name}  {human(size)}")

        meta = {
            "basename": base,
            "archived_at": datetime.now().isoformat(timespec="seconds"),
            "run_mtime": mt,
            "log_sha256": log_sha,
            "files": files,
            "sweep": None,
            "schematic": {
                "same_name": asc.name if asc and asc.exists() else None,
                "same_name_directives_match_deck": verdict,
                "matching_schematic": match.name if match else None,
                "note": ("指令级比对（.step/.param/.tran/.meas），非电路等价性证明"
                         if verdict is not None else "无网表可比对"),
            },
            "criterion_pct": CFG.IERR_MAX_PCT,
        }
        if desc:
            meta["sweep"] = {
                "signature": sig, "steps": desc["steps"],
                "rb_min": desc["rb_min"], "rb_max": desc["rb_max"],
                "rb_n": desc["rb_n"], "rb_step": desc["rb_step"],
                "vbp": desc["vbp"], "iref_uA": desc["iref_uA"],
                f"pass1_at_{CFG.IERR_MAX_PCT:g}pct":
                    desc[f"pass1_at_{CFG.IERR_MAX_PCT:g}pct"],
                "pass1_log1pct": desc["pass1_log1pct"],
                "manifest_sweep": entry["sweep"] if entry else None,
                "log_matches_manifest_sha256":
                    bool(entry) and entry.get("sha256") == log_sha,
                "directive_hint": desc["directive_hint"],
            }
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
        have.add((base, log_sha))
        done += 1

    if not a.dry_run:
        idx = rebuild_index()
        print(f"\n归档完成：{done} 个运行，归档区现有 {len(idx['runs'])} 条记录")
        print(f"索引: {ARCHIVE.relative_to(PROJECT)}/INDEX.md")
    else:
        print("\n[dry-run] 未改动任何文件")
    if skipped:
        print("\n未归档:")
        for b, why in skipped:
            print(f"  {b}: {why}")
    if not a.dry_run and done:
        print("\n提示: 换扫描参数前重跑本脚本即可；已归档的运行不会被重复归档。")


if __name__ == "__main__":
    main()
