#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recalculate the workbook with Excel (COM) and verify every formula result
against ground truth computed independently in Python. Then bake cached values."""
import json, sys, math
from pathlib import Path
import win32com.client as win32
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as CFG

ROOT = Path(__file__).resolve().parent.parent
LAST_ROW = 1 + len(json.loads(
    (Path(__file__).resolve().parent.parent / 'work' /
     'parsed_combined.json').read_text(encoding='utf-8')))
WORK = ROOT / "work"
XLSX = ROOT / "Draft2_BONE_sweep_analysis.xlsx"
GT = json.loads((WORK / "ground_truth.json").read_text(encoding="utf-8"))

VBPS = [3.3, 5.0, 8.0, 10.0, 12.0, 15.0]
IREF_UA = [10, 20, 50, 100, 200]
KEY_RB = [10000, 20000, 50000, 100000, 200000, 500000, 1000000, 10000000]
L = GT["layout"]
RM = L["rm"]
BD_HDR, BD_0 = L["bd_hdr"], L["bd_0"]
CA_HDR, CA_0, CA_BH, CA_B0 = L["ca_hdr"], L["ca_0"], L["ca_bh"], L["ca_b0"]
HEAT_0, STAT_0 = RM["HEAT_0"], RM["STAT_0"]
print(f"[layout] heatmap rows {HEAT_0}..{HEAT_0+5}, stat {STAT_0}..{STAT_0+5}, "
      f"params {RM['P_MIN']}..{RM['P_MIN']+9}, BD {BD_0}..{BD_0+29}, "
      f"CA {CA_0}..{CA_0+29} / {CA_B0}..{CA_B0+29}")
COMBOS = [(v, i) for v in VBPS for i in IREF_UA]      # v-major, i-minor

fails = []
checks = 0


def cmp_num(tag, got, want, tol=1e-6):
    global checks
    checks += 1
    if want is None:
        if got not in (None, ""):
            fails.append(f"{tag}: expected empty, got {got!r}")
        return
    if isinstance(got, str):
        fails.append(f"{tag}: expected {want}, got text {got!r}")
        return
    if got is None:
        fails.append(f"{tag}: expected {want}, got None")
        return
    if abs(got - want) > tol * max(1.0, abs(want)):
        fails.append(f"{tag}: expected {want!r}, got {got!r}")


def cmp_str(tag, got, want):
    global checks
    checks += 1
    g = "" if got is None else str(got).strip()
    if g != want.strip():
        fails.append(f"{tag}: expected {want!r}, got {g!r}")


xl = win32.DispatchEx("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
xl.ScreenUpdating = False
try:
    wb = xl.Workbooks.Open(str(XLSX))
    xl.CalculateFullRebuild()
    print("[calc] full rebuild done")

    def grid(sheet, r1, c1, r2, c2):
        v = wb.Worksheets(sheet).Range(
            wb.Worksheets(sheet).Cells(r1, c1), wb.Worksheets(sheet).Cells(r2, c2)
        ).Value
        if isinstance(v, tuple):
            return [list(row) if isinstance(row, tuple) else [row] for row in v]
        return [[v]]

    # ---------- Rmax_Summary main matrix (formulas) ----------
    g = grid("Rmax_Summary", RM["MAIN_0"], 2, RM["MAIN_0"] + 5, 6)
    for k, rr in enumerate(g):
        v = VBPS[k]
        for j, iu in enumerate(IREF_UA):
            cmp_str(f"Rmax_Summary!{chr(66+j)}{RM['MAIN_0']+k} ({v}V,{iu}uA)",
                    rr[j], GT["rmax_disp"][f"{v}|{iu}"])

    # ---------- Rmax_Summary heatmap (static numeric) ----------
    g = grid("Rmax_Summary", HEAT_0, 2, HEAT_0 + 5, 6)
    for k, rr in enumerate(g):
        v = VBPS[k]
        for j, iu in enumerate(IREF_UA):
            cmp_num(f"heatmap {v}V/{iu}uA", rr[j], GT["rmax_num"][f"{v}|{iu}"], 1e-9)

    # ---------- Rmax_Summary global params (formulas) ----------
    gp = grid("Rmax_Summary", RM["P_MIN"], 2, RM["P_MIN"] + 9, 2)
    p = GT["params"]
    for idx, key in [(0, "rb_min"), (1, "rb_max"), (2, "rows"),
                     (3, "n_at_max_pass"), (4, "n_fail_at_min"),
                     (5, "n_pass_rows"), (6, "n_fail_rows")]:
        row = [0, 1, 2, 6, 7, 8, 9][idx]
        cmp_num(f"params row{row}", gp[row][0], p[key])

    # ---------- Boundary_Detail (formulas) ----------
    g = grid("Boundary_Detail", BD_0, 3, BD_0 + 29, 12)
    for k, rr in enumerate(g):
        v, iu = COMBOS[k]
        lastP, firstF = GT["boundary"][f"{v}|{iu}"]
        if lastP is None:
            cmp_str(f"BD C{k} ({v},{iu})", rr[0], "N/A")
            cmp_str(f"BD D{k} ({v},{iu})", rr[1], "N/A (无临界区)")
            for cc in (2, 3, 4, 5):
                cmp_str(f"BD {chr(69+cc)}{k} ({v},{iu})", rr[cc], "N/A")
            cmp_num(f"BD K{k} ({v},{iu})", rr[8], None)
            cmp_num(f"BD L{k} ({v},{iu})", rr[9], None)
        else:
            cmp_num(f"BD C{k} ({v},{iu})", rr[0], lastP / 1000.0, 1e-9)
            if firstF is None:
                cmp_str(f"BD D{k} ({v},{iu})", rr[1], "无 (扫描上限内仍 PASS)")
                cmp_num(f"BD L{k} ({v},{iu})", rr[9], None)
            else:
                cmp_num(f"BD D{k} ({v},{iu})", rr[1], firstF / 1000.0, 1e-9)
                cmp_num(f"BD L{k} ({v},{iu})", rr[9], float(firstF), 1e-9)
            cmp_num(f"BD K{k} ({v},{iu})", rr[8], float(lastP), 1e-9)
    # verify Last/First currents + errors against raw data (second pass)
    RAW = {}
    x = wb.Worksheets("Raw_Data")
    vals = x.Range(x.Cells(2, 1), x.Cells(LAST_ROW, 9)).Value
    for row in vals:
        RAW[(row[1], row[2], row[3])] = row
    g = grid("Boundary_Detail", BD_0, 3, BD_0 + 29, 12)
    for k, rr in enumerate(g):
        v, iu = COMBOS[k]
        lastP, firstF = GT["boundary"][f"{v}|{iu}"]
        if lastP is not None:
            rw = RAW[(v, iu, lastP)]
            cmp_num(f"BD E{k} ({v},{iu})", rr[2], rw[5], 1e-8)      # IBONE uA
            cmp_num(f"BD G{k} ({v},{iu})", rr[4], rw[7], 1e-8)      # IERR
        if firstF is not None:
            rw = RAW[(v, iu, firstF)]
            cmp_num(f"BD F{k} ({v},{iu})", rr[3], rw[5], 1e-8)
            cmp_num(f"BD H{k} ({v},{iu})", rr[5], rw[7], 1e-8)

    # ---------- Current_Accuracy block A (formulas) ----------
    g = grid("Current_Accuracy", CA_0, 4, CA_0 + 29, 9)
    for k, rr in enumerate(g):
        v, iu = COMBOS[k]
        ib, ierr, vbone, pas = GT["acc_low"][f"{v}|{iu}"]
        cmp_num(f"CA D{k} ({v},{iu})", rr[0], round(ib, 6), 1e-9)
        cmp_num(f"CA E{k} ({v},{iu})", rr[1], ierr, 1e-8)
        cmp_str(f"CA F{k} ({v},{iu})", rr[2], "Yes" if pas == 1 else "No")
        cmp_num(f"CA G{k} ({v},{iu})", rr[3], vbone, 1e-8)
        cmp_num(f"CA H{k} ({v},{iu})", rr[4], 100 * abs(ib - iu) / iu, 1e-5)
        cmp_num(f"CA I{k} ({v},{iu})", rr[5], 0.0, 5e-4)

    # ---------- Current_Accuracy block B (formulas) ----------
    nk = len(KEY_RB)
    g = grid("Current_Accuracy", CA_B0, 3, CA_B0 + 29, 2 + nk + 1)
    for k, rr in enumerate(g):
        v, iu = COMBOS[k]
        want = GT["err_matrix"][f"{v}|{iu}"]
        for j in range(nk):
            cmp_num(f"CA-B {v}/{iu}/{KEY_RB[j]}", rr[j], want[j], 1e-8)
        cmp_num(f"CA-B npass {v}/{iu}", rr[nk], GT["npass"][f"{v}|{iu}"], 1e-9)

    # ---------- Chart_Source (-1% limits) ----------
    g = grid("Chart_Source", 3, 2, 4, 6)
    _lim = 1 - CFG.IERR_MAX_PCT / 100
    for j, iu in enumerate(IREF_UA):
        cmp_num(f"ChartSource -{CFG.IERR_MAX_PCT:g}% {iu}uA",
                g[0][j], iu * _lim, 1e-9)
        cmp_num(f"ChartSource -{CFG.IERR_MAX_PCT:g}% {iu}uA (r4)",
                g[1][j], iu * _lim, 1e-9)

    # ---------- structural checks ----------
    ws = wb.Worksheets("Raw_Data")
    n = ws.UsedRange.Rows.Count
    cmp_num("Raw_Data rows", n, LAST_ROW, 1e-9)
    cmp_num("Raw_Data filter", ws.AutoFilter.Range.Rows.Count, LAST_ROW, 1e-9)
    print(f"[check] Raw_Data used rows={n}, autofilter={ws.AutoFilter.Range.Address}")
    # spot-check raw values
    g = grid("Raw_Data", 1, 1, 4, 9)
    cmp_str("Raw hdr A1", g[0][0], "Step")
    cmp_str("Raw hdr E1", g[0][4], "RB_kOhm")
    cmp_str("Raw hdr I1", g[0][8], "PASS")

    # charts
    for sh in ("Charts", "Charts_I_vs_R"):
        w = wb.Worksheets(sh)
        cnt = w.ChartObjects().Count
        print(f"[check] {sh}: {cnt} chart object(s)")
        if sh == "Charts":
            cmp_num("Charts count", cnt, 1, 1e-9)
            co = w.ChartObjects(1).Chart
            t = co.ChartTitle.Text
            print(f"[check] Charts title: {t!r}")
            print(f"[check] axis1: {co.Axes(1).AxisTitle.Text!r}")
            print(f"[check] axis2: {co.Axes(2).AxisTitle.Text!r}")
            ns = co.SeriesCollection().Count
            # chart 1: the target-current series, plus -- only when some point is
            # censored -- a lower-bound overlay AND the scan-limit reference line
            cmp_num("Charts series count", ns,
                    len(IREF_UA) + (2 if GT["censored"] else 0), 1e-9)
            for k in range(1, ns + 1):
                print(f"    series{k}: {co.SeriesCollection(k).Name!r} "
                      f"pts={co.SeriesCollection(k).Points().Count}")
        else:
            cmp_num("Charts_I_vs_R count", cnt, 6, 1e-9)
            for k in range(1, cnt + 1):
                co = w.ChartObjects(k).Chart
                print(f"    chart{k} series={co.SeriesCollection().Count} "
                      f"title={co.ChartTitle.Text.splitlines()[0]!r}")
    # conditional formatting survived?
    for sh, rng in (("Raw_Data", f"A2:I{LAST_ROW}"),
                    ("Rmax_Summary", f"B{HEAT_0}:F{HEAT_0+5}"),
                    ("Current_Accuracy", f"C{CA_B0}:G{CA_B0+29}"),
                    ("Charts", "O4:S9"),
                    ("Boundary_Detail", f"J{BD_0}:J{BD_0+29}")):
        w = wb.Worksheets(sh)
        ncf = w.Range(rng).FormatConditions.Count
        print(f"[check] CF on {sh}!{rng} = {ncf}")
        if ncf == 0:
            fails.append(f"conditional formatting missing on {sh}!{rng}")
    print(f"[check] named ranges: {wb.Names.Count}")

    # ---------------- report -----------------
    print("\n" + "=" * 70)
    print(f"VERIFICATION: {checks - len(fails)}/{checks} checks passed")
    if fails:
        print(f"FAILURES ({len(fails)}):")
        for f in fails[:40]:
            print("  x", f)
    else:
        print("ALL CHECKS PASSED")
    print("=" * 70)

    # export charts as PNG for visual inspection
    outdir = ROOT / "charts"
    outdir.mkdir(exist_ok=True)
    for sh in ("Charts", "Charts_I_vs_R"):
        w = wb.Worksheets(sh)
        for k in range(1, w.ChartObjects().Count + 1):
            fp = str(outdir / f"{sh}_{k}.png")
            w.ChartObjects(k).Chart.Export(fp, "PNG")
            print(f"[png] {fp}")

    wb.Save()
    print("[saved] cached formula values baked in")
    wb.Close(SaveChanges=False)

    # ---- reopen the DELIVERED file: Excel round-trip must not have dropped anything
    print("\n--- post-save structural re-check of the delivered file ---")
    wb2 = xl.Workbooks.Open(str(XLSX))
    for sh, rng, want in (("Raw_Data", f"A2:K{LAST_ROW}", 2),
                          ("Rmax_Summary", f"B{HEAT_0}:F{HEAT_0+5}", 1),
                          ("Current_Accuracy", f"C{CA_B0}:G{CA_B0+29}", 2),
                          ("Charts", "O4:S9", 3),
                          ("Boundary_Detail", f"J{BD_0}:J{BD_0+29}", 3)):
        n = wb2.Worksheets(sh).Range(rng).FormatConditions.Count
        cmp_num(f"post-save CF {sh}", n, want, 1e-9)
        print(f"[post] CF {sh}!{rng} = {n}")
    w = wb2.Worksheets("Raw_Data")
    cmp_str("post-save autofilter", w.AutoFilter.Range.Address, f"$A$1:$K${LAST_ROW}")
    cmp_num("post-save filter rows", w.AutoFilter.Range.Rows.Count, LAST_ROW, 1e-9)
    fr = {sh: wb2.Worksheets(sh).Range("A2").Row for sh in ("Raw_Data",)}
    print("[post] freeze panes Raw_Data:",
          wb2.Worksheets("Raw_Data").Cells(2, 1).Row,
          "| FreezePanes:", wb2.Windows(1).FreezePanes,
          "| SplitRow:", wb2.Windows(1).SplitRow)
    print("[post] number format D2/E2/F2/H2:",
          wb2.Worksheets("Raw_Data").Range("D2").NumberFormat,
          wb2.Worksheets("Raw_Data").Range("E2").NumberFormat,
          wb2.Worksheets("Raw_Data").Range("F2").NumberFormat,
          wb2.Worksheets("Raw_Data").Range("H2").NumberFormat)
    # cached values present without recalculation?
    v1 = wb2.Worksheets("Rmax_Summary").Range("C8").Value
    cmp_str("post-save cached Rmax C8", v1, GT["rmax_disp"]["5.0|20"])
    print("[post] cached value Rmax_Summary!C8 =", repr(v1))
    # expectation comes from ground truth: whether 3.3 V / 10 µA has a boundary
    # depends on the configured threshold, so never hardcode "N/A" here
    _b = GT["boundary"]["3.3|10"][0]
    v2 = wb2.Worksheets("Boundary_Detail").Range("C5").Value
    if _b is None:
        cmp_str("post-save cached BD C5 (3.3V/10uA)", v2, "N/A")
    else:
        cmp_num("post-save cached BD C5 (3.3V/10uA)", v2, _b / 1000.0, 1e-9)
    v2b = wb2.Worksheets("Boundary_Detail").Range("C6").Value
    cmp_num("post-save cached BD C6 (3.3V/20uA)",
            v2b, GT["boundary"]["3.3|20"][0] / 1000.0, 1e-9)
    print("[post] cached Boundary_Detail!C5/C6 =", repr(v2), repr(v2b))
    v3 = wb2.Worksheets("Current_Accuracy").Range("D6").Value
    cmp_num("post-save cached CA D6", v3, GT["acc_low"]["3.3|10"][0], 1e-6)
    print("[post] cached value Current_Accuracy!D6 =", repr(v3))
    print("[post] chart objects:",
          wb2.Worksheets("Charts").ChartObjects().Count,
          wb2.Worksheets("Charts_I_vs_R").ChartObjects().Count)
    print("[post] named ranges:", wb2.Names.Count)
    wb2.Close(SaveChanges=False)
    print("\n" + "=" * 70)
    print(f"FINAL: {checks - len(fails)}/{checks} checks passed")
    if fails:
        print(f"FAILURES ({len(fails)}):")
        for f in fails[:30]:
            print("  x", f)
    else:
        print("ALL CHECKS PASSED (incl. post-save structural re-check)")
    print("=" * 70)
finally:
    xl.Quit()
sys.exit(1 if fails else 0)
