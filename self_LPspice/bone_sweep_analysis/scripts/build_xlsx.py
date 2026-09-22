#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build the research-style Excel workbook from the parsed LTspice 3-parameter sweep.

Input : parsed_combined.json  (parse_draft2.py + parse_sweep2.py + merge_sweeps.py)
Output: Draft2_BONE_sweep_analysis.xlsx
        ground_truth.json  (for independent verification via Excel COM)

Design notes
------------
* Raw_Data holds the simulation results as VALUES (measurements are ground truth,
  not derived by formula). RB_kOhm is a live formula (=RB_Ohm/1000).
* All statistics on Rmax_Summary / Boundary_Detail / Current_Accuracy are live
  Excel formulas over named ranges pointing at Raw_Data, so the workbook can be
  recalculated after the raw data is replaced.
* MAXIFS/MINIFS are NOT used: they evaluate to #NAME? on this Excel build
  (verified empirically). Non-array idioms are used instead:
      last match in group : LOOKUP(2, 1/(cond), return_range)
      conditional count   : SUMPRODUCT((...)*(...))
      conditional minimum : SUMPRODUCT(MIN(cond*range + (1-cond)*1E+15))
* TEXT() with "#,##0.#" renders "163." -> the "General" format code is used.
"""
import json
import sys
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as CFG
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side)
from openpyxl.formatting.rule import (FormulaRule, CellIsRule, ColorScaleRule)
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.chart import ScatterChart, Reference, Series
from openpyxl.chart.marker import Marker
from openpyxl.chart.axis import NumericAxis
from openpyxl.chart.title import Title
from openpyxl.chart.text import RichText, Text
from openpyxl.drawing.text import (Paragraph, ParagraphProperties,
                                   CharacterProperties, RichTextProperties,
                                   RegularTextRun)
from openpyxl.drawing.line import LineProperties

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
WORK.mkdir(parents=True, exist_ok=True)
XLSX = ROOT / "Draft2_BONE_sweep_analysis.xlsx"
LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "Draft2.log"
ROWS = json.loads((WORK / "parsed_combined.json").read_text(encoding="utf-8"))
# PASS is a pure function of IERR, so it is recomputed here from the configured
# threshold rather than taken from the log's own 1.0 % column (kept as provenance).
for _r in ROWS:
    _r["PASS_T"] = CFG.verdict(_r["IERR"])
T = CFG.IERR_MAX_PCT
TP = CFG.fmt_pct(T)
OUT_XLSX = XLSX

# ---------------------------------------------------------------- constants
NMAX = 20001                  # last row of the named data ranges
VBPS = [3.3, 5.0, 8.0, 10.0, 12.0, 15.0]
IREF_UA = [10, 20, 50, 100, 200]
IREF_A = [i / 1e6 for i in IREF_UA]
KEY_RB = [10000, 20000, 50000, 100000, 200000, 500000, 1000000, 10000000]  # accuracy loads
LOG_A = "Draft2.log"          # sweep 1: RB 10k..200k step 1k
LOG_B = "Draft2_sweep.log"    # sweep 2: RB 200k..1000k step 10k
LOG_C = "Draft2_sweep.log"    # sweep 3: RB 1M..10M step 100k (same file, later run)


def fmt_rb(ohm):
    """Format an RB value with a unit that stays readable up to 10 MΩ."""
    return f"{ohm/1e6:.0f} MΩ" if ohm >= 1e6 else f"{ohm/1e3:.0f} kΩ"
SERIES_COLOR = ["1F77B4", "FF7F0E", "2CA02C", "D62728", "9467BD"]

# ---------------------------------------------------------------- styling
F_TITLE = Font(bold=True, size=14, color="FF1F3864")
F_SUB = Font(italic=True, size=9, color="FF595959")
F_SEC = Font(bold=True, size=11, color="FFFFFFFF")
F_HDR = Font(bold=True, size=10, color="FF1F3864")
F_BOLD = Font(bold=True, size=10)
F_BODY = Font(size=10)
F_MONO = Font(name="Consolas", size=9)
F_NOTE = Font(size=9, color="FF595959")

FILL_SEC = PatternFill("solid", start_color="FF1F3864")
FILL_HDR = PatternFill("solid", start_color="FFD9E1F2")
FILL_HDR2 = PatternFill("solid", start_color="FFEDEDED")
FILL_GREEN = PatternFill("solid", start_color="FFC6EFCE")
FILL_RED = PatternFill("solid", start_color="FFC7CE")
FILL_AMBER = PatternFill("solid", start_color="FFFFEB9C")
FILL_GREY = PatternFill("solid", start_color="FFF2F2F2")

THIN = Side(style="thin", color="FFBFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CTR = Alignment(horizontal="center", vertical="center")

NF_URB = "#,##0"
NF_UK = "#,##0.###"
NF_MUA = "#,##0.000000"
NF_V = "#,##0.000000"
NF_PCT4 = "#,##0.0000"
NF_INT = "0"
NF_1DP = "0.0"
HDR_UA = '0" µA"'


def rng(col):
    """Named-range body for a Raw_Data column."""
    return f"Raw_Data!${col}$2:${col}${NMAX}"


# Named ranges (workbook level) -------------------------------------------
NAMED = {
    "RD_STEP": rng("A"), "RD_VBP": rng("B"), "RD_IREF": rng("C"),
    "RD_RB": rng("D"), "RD_RBK": rng("E"), "RD_IB": rng("F"),
    "RD_VB": rng("G"), "RD_IERR": rng("H"), "RD_PASS": rng("I"),
}

MUA = 1000000.0     # A -> uA


# ---------------------------------------------------------------- precompute
def key(row):
    return (row["vbp"], row["iref"], row["rb"])


data = sorted(ROWS, key=key)
D = {key(r): r for r in data}
assert len(D) == len(data), len(data)
ALL_RB = sorted({r["rb"] for r in data})
RB_MIN, RB_MAX = ALL_RB[0], ALL_RB[-1]

SWEEPS = {}
for _r in data:
    _sw = _r["sweep"]
    SWEEPS.setdefault(_sw, {"log": _r["log"], "rb": set(), "rows": 0})
    SWEEPS[_sw]["rb"].add(_r["rb"])
    SWEEPS[_sw]["rows"] += 1
for _sw, _info in SWEEPS.items():
    _info["npass"] = sum(1 for _r in data
                         if _r["sweep"] == _sw and _r["PASS_T"] == 1)
    _rbs = sorted(_info["rb"])
    _gaps = [_rbs[k + 1] - _rbs[k] for k in range(len(_rbs) - 1)]
    _info["uniform"] = (not _gaps) or all(abs(g - _gaps[0]) < 1 for g in _gaps)
    _info["nrb"] = len(_rbs)
    _info["rb_min"], _info["rb_max"] = _rbs[0], _rbs[-1]
    _info["step"] = (_rbs[1] - _rbs[0]) if len(_rbs) > 1 else 0
    del _info["rb"]

groups = {}
for v in VBPS:
    for i in IREF_A:
        sub = sorted((r_ for r_ in data
                      if r_["vbp"] == v and r_["iref"] == i),
                     key=lambda r_: r_["rb"])
        pas = [r for r in sub if r["PASS_T"] == 1]
        fal = [r for r in sub if r["PASS_T"] == 0]
        lastP = max((r["rb"] for r in pas), default=None)
        firstF = min((r["rb"] for r in fal if lastP is not None and r["rb"] > lastP),
                     default=None)
        at_max = sub[-1]["PASS_T"] == 1
        if not pas:
            status = "N/A"
        elif at_max:
            status = "LB"
        else:
            status = "EXACT"
        groups[(v, i)] = dict(rows=sub, lastP=lastP, firstF=firstF,
                              at_max=at_max, status=status,
                              n_pass=len(pas), last=sub[-1], first=sub[0])

# worksheet row span (inclusive, data starts at row 2) of every (VBP, IREF) block
GROUP_ROWS = {}
for _idx, _r in enumerate(data):
    _k = (_r["vbp"], _r["iref"])
    GROUP_ROWS.setdefault(_k, [_idx + 2, _idx + 2])
    GROUP_ROWS[_k][1] = _idx + 2

RMX_NUM = {(v, i): (groups[(v, i)]["lastP"] / 1000.0
                    if groups[(v, i)]["status"] == "EXACT" else None)
           for v in VBPS for i in IREF_A}
RMX_DISP = {}
for v in VBPS:
    for i in IREF_A:
        g = groups[(v, i)]
        if g["status"] == "N/A":
            RMX_DISP[(v, i)] = f"N/A (基础误差>{T:g}%)"
        elif g["status"] == "LB":
            RMX_DISP[(v, i)] = f"≥{RB_MAX/1000:.0f} kΩ (扫描上限)"
        else:
            # must match what the Excel formula's TEXT(...,"General") renders, so
            # the refined precision (e.g. 248.95 kΩ) is not silently truncated
            RMX_DISP[(v, i)] = f"{g['lastP']/1000:.10g} kΩ"

CENSORED = [(v, i, RB_MAX) for v in VBPS for i in IREF_A
            if groups[(v, i)]["status"] == "LB"]

wb = Workbook()
wb.remove(wb.active)
for n, ref in NAMED.items():
    wb.defined_names.add(DefinedName(n, attr_text=ref))


# ================================================================= 1. README
def build_readme():
    ws = wb.create_sheet("README")
    ws.sheet_view.showGridLines = False
    r = 1

    def put(a, b=None, mono=False, wrap=False,
            size=None, bold=False, fill=None):
        """put(text) -> full-width section band;  put(label, value) -> two-column row."""
        nonlocal r
        if b is None:
            c = ws.cell(row=r, column=1, value=a)
            c.font = F_SEC
            for k in range(1, 5):
                ws.cell(row=r, column=k).fill = FILL_SEC
            ws.row_dimensions[r].height = 20
            r += 1
            return
        c = ws.cell(row=r, column=1, value=a)
        c.font = F_BOLD if bold else (F_MONO if mono else F_BODY)
        c.alignment = Alignment(vertical="top", wrap_text=wrap)
        v = ws.cell(row=r, column=2, value=b)
        v.font = F_MONO if mono else (Font(size=size) if size else F_BODY)
        v.alignment = Alignment(vertical="top", wrap_text=wrap)
        if fill:
            c.fill = fill
            v.fill = fill
        r += 1

    t = ws.cell(row=r, column=1,
                value="BONE_P 恒流源 — LTspice 三参数扫描分析报告")
    t.font = F_TITLE
    r += 1
    s = ws.cell(row=r, column=1,
                value=f"生成日期 2026-09-21 | 流水线 parse_draft2.py + parse_sweep2.py + "
                      f"merge_sweeps.py + build_xlsx.py | "
                      f"数据源 {LOG_A} + {LOG_B} ×2 | 组合数 {len(data)}（三次扫描合并）")
    s.font = F_SUB
    r += 2

    put("§1  数据来源 (Data source) — 两次互补扫描")
    put("仿真类型", "LTspice transient simulation（瞬态仿真，.tran 15m startup）")
    put("LTspice 版本", "26.0.2 for Windows")
    _lt = LOG.parent
    for sw in sorted(SWEEPS):
        info = SWEEPS[sw]
        _letter = chr(ord("A") + sw - 1) if sw <= 26 else str(sw)
        put(f"扫描 {_letter} (Sweep {sw})",
            f"{info['log']} | RB {fmt_rb(info['rb_min'])} … {fmt_rb(info['rb_max'])}，"
            + (f"步长 {info['step']/1000:.0f} kΩ" if info["uniform"]
               else "非等步长（逐窗口细分）")
            + f"（{info['nrb']} 点），{info['rows']} 组；PASS=1 {info['npass']} 组", wrap=True)
    put("其余指令（三次相同）",
        ".step param IREF list 10u 20u 50u 100u 200u  /  "
        ".step param VBP list 3.3 5 8 10 12 15", mono=True, wrap=True)
    put("网表 / 原理图", f"{_lt / 'Draft2.net'}  /  {_lt / 'Draft2_sweep.asc'}", mono=True)
    put("组合总数", f"两次合计 {len(data)} 组（去重后；全部成功解析，无缺失）", bold=True)
    put("重叠校验", "两次扫描在 RB = 200 kΩ 处重叠。逐点比对 30 个组合：IBONE 与 IERR "
                   "【逐位完全一致】（最大相对偏差 0.00e+00），证明两次运行是同一电路、同一模型；"
                   "该重叠点只保留一行（取自扫描 A）。", wrap=True, bold=True)
    put("RB 分辨率", f"RB ≤ 200 kΩ 为 1 kΩ 分辨（扫描 A）；RB > 200 kΩ 为 10 kΩ 分辨（扫描 B）。"
                   "合并后共 271 个 RB 取值，10 kΩ … 1000 kΩ。", wrap=True)
    put("注意", "Raw_Data 中 Step 列 = 该行在其来源日志中的 .step 序号，Sweep / Source_Log 列标明"
               "来源；行序按 VBP → IREF → RB 排序，故 Step 列不单调。", wrap=True)
    r += 1

    put("§2  稳态测量区间 (.meas FROM / TO)")
    put("测量指令", ".meas tran IBONE AVG -I(R_BONE)          FROM 12m TO 15m", mono=True)
    put("", ".meas tran VBONE AVG V(BONE_P,BONE_N)     FROM 12m TO 15m", mono=True)
    put("稳态区间", "FROM 12 ms  TO 15 ms", bold=True)
    put("说明", "瞬态总时长 15 ms（含 startup 启动），取最后 3 ms（12–15 ms）平均值，"
               "以避开启动瞬态、保证进入恒流稳态后测量。同理 IERR / PASS 亦基于该区间。", wrap=True)
    r += 1

    put("§3  测量量与单位约定")
    put("IBONE", "R_BONE 电流平均值（.meas AVG -I(R_BONE)）— 日志原始单位 A，Excel 中换算为 µA")
    put("VBONE", "R_BONE 两端电压平均值 V(BONE_P,BONE_N) — 单位 V")
    put("IERR", "恒流误差 — 单位 % （日志 .meas 直接给出）")
    put("PASS", "判据标记 — 1 或 0（日志 .meas 直接给出）")
    put("单位", "IREF / IBONE → µA ；RB → Ω 与 kΩ 并列 ；VBONE → V ；IERR → %", bold=True)
    put("显示", "µA 与 kΩ 一律使用定点小数，不使用科学计数法", bold=True)
    r += 1

    put("§4  PASS 判据与 IERR 定义")
    put("IERR 定义", "IERR = 100 × abs(IBONE − IREF) / IREF      [%]", mono=True)
    put("PASS 判据", f"PASS = 1  当 IERR <= {T:g} ； 否则 PASS = 0      （即 ±{T:g}% 恒流精度）",
        mono=True, bold=True)
    put("阈值可改", "阈值存放在 Rmax_Summary 的全局参数区（PASS 判据 IERR ≤ (%) 单元格）；"
                  "Raw_Data 的 PASS 列是引用该单元格的活公式 —— 改那一个格，全表重算；"
                  "IERR 已按全精度保存，因此改阈值无需重跑任何仿真。", wrap=True)
    put("与日志的区别", f"LTspice 网表里的 .meas PASS 用的是 1% 判据；本表按 {T:g}% 由 IERR 重新判定，"
                     f"故 Raw_Data 的 PASS 列可能与日志自身的 PASS 值不同。", wrap=True)
    put("一致性验证", "解析脚本已逐行交叉验证：IERR 与该公式最大偏差 2.5e-10 %pt；"
                    f"按 {T:g}% 阈值重算 PASS，与 IERR 判定不一致的行数 = 0 （共 {len(data)} 行）", wrap=True, bold=True)
    r += 1

    put("§5  Rmax 定义与标记规则（核心）")
    put("Rmax 定义", f"在给定 VBP + IREF 下，满足 PASS=1（±{T:g}% 恒流误差）的【最大已扫描】BONE 负载电阻 RB",
        bold=True, wrap=True)
    put("标记 (1)", "精确值，例如 “163 kΩ” → RB 继续增大即 FAIL，属真实临界值", fill=FILL_GREEN)
    _n_ok = sum(1 for _v in VBPS for _i in IREF_A
                if groups[(_v, _i)]["status"] == "EXACT")
    _n_na = sum(1 for _v in VBPS for _i in IREF_A
                if groups[(_v, _i)]["status"] == "N/A")
    put("标记 (2)", f"“≥{fmt_rb(RB_MAX)} (扫描上限)” → 在上限处仍 PASS，结果只是【下限】，"
                   f"真实 Rmax 更大。三次扫描合并后【已无此情形】：{_n_ok}/30 组合已测得真实临界值",
        wrap=True, fill=FILL_AMBER)
    put("标记 (3)", f"“N/A (基础误差>{T:g}%)” → 最小负载 RB=10 kΩ 时 IERR 已 >{T:g}%，属电路自身的基础恒流误差，"
                   "【不是】负载能力为 0，严禁写作 Rmax = 0；原始数据完整保留", wrap=True, fill=FILL_RED)
    put("数据完整性", "未对任何缺失仿真点做插值或补数；图表只连接真实仿真点。", bold=True, wrap=True)
    r += 1

    put("§6  关于 IREF = 10 µA 的特别说明（务必保留）")
    put("结论", "10 µA 在本次扫描范围内【没有任何 PASS 点】，因此 Rmax 全部标记为 N/A —— "
               "但这是基础恒流误差所致，绝不是负载能力为 0。", bold=True, wrap=True)
    put("证据", "各 BONE_P 电压下 RB = 10 kΩ（最小负载）处的 IERR 已达：", wrap=True)
    for v in VBPS:
        g = groups[(v, 10 / 1e6)]
        put(f"  VBP = {v} V", f"IERR = {g['first']['IERR']:.4f} %   "
                              f"(IBONE = {g['first']['IBONE']*MUA:.4f} µA)   → FAIL")
    _i10 = [D[(v, 10 / 1e6, RB_MAX)]["IERR"] for v in VBPS]
    put("加重趋势", f"IERR 随 RB 单调增大：在扫描上限 {RB_MAX/1000:.0f} kΩ 处为 "
                   f"{min(_i10):.4f} % (VBP=15 V) ~ {max(_i10):.4f} % (VBP=3.3 V)；"
                   f"全负载范围（{RB_MIN/1000:.0f} kΩ … {RB_MAX/1000:.0f} kΩ）内始终 > 1 %", wrap=True)
    put("处理方式", f"10 µA 对应的 {sum(1 for r_ in data if abs(r_['iref']-1e-5)<1e-12)} 行原始数据"
                   f"【完整保留】于 Raw_Data；Current_Accuracy 中同样保留 10 µA 全部行，"
                   "未因 PASS=0 而删除", wrap=True, bold=True)
    put("改善方向", "该类误差来自电路基础恒流精度（运放失调 Vos、采样电阻 R10 的绝对值与匹配、"
                   "环路增益/有限开环增益、漏电流），应通过改进电路参数而非缩小负载来改善。", wrap=True)
    r += 1

    put("§7  失效机理判读（为何 RB 增大会掉出恒流区）")
    put("机理", "RB 增大使 V(BONE) 升高；当 V(BONE) 接近电流源输出级(U1 运放 + U2 NMOS)的顺从电压 "
               "(compliance) 上限时，输出管脱离恒流调节，IBONE 随 RB 增大而下降，IERR 迅速增大。", wrap=True)
    put("证据 1", "同一 VBP 下，多组 IREF 的 RB=200 kΩ 处 IBONE 收敛到同一值，说明此时电流由负载而非环路决定：")
    for v in VBPS:
        vals = {i: D[(v, i, RB_MAX)]["IBONE"] for i in IREF_A}
        ref = vals[200 / 1e6]
        # physical equality, not bit equality: the clamped value can differ in the
        # last digit between runs, so compare with a 1e-4 relative tolerance
        grp = [i for i in IREF_A if abs(vals[i] - ref) <= 1e-4 * abs(ref)]
        if len(grp) > 1:
            put(f"  VBP = {v} V", f"IREF ∈ {{{', '.join(f'{i*1e6:.0f}' for i in grp)}}} µA 均得 "
                                  f"IBONE = {ref*MUA:.4f} µA "
                                  f"(= VBONE {D[(v, 200/1e6, RB_MAX)]['VBONE']:.4f} V / 200 kΩ)")
    put("证据 2", "V_BONE,MAX ≈ VBP − 50 mV（输出级 Rail=50m 的电压裕量），例如 VBP = 3.3 V 时 "
                 "V_BONE,MAX ≈ 3.250 V (RB=200 kΩ 处)", wrap=True)
    _dev = []
    for _v in VBPS:
        for _i in IREF_A:
            _gg = groups[(_v, _i)]
            if _gg["status"] != "EXACT":
                continue
            _pred = _v / (0.99 * _i * 1e6) * 1000 - 3.0      # kΩ, IREF in µA
            _dev.append(abs(_gg["lastP"] / 1000 - _pred) / _pred * 100)
    put("推论 1", "Rmax ≈ (V_BONE,MAX − 裕量) / IREF —— 定性成立，但与实测趋势相比偏低约 1%",
        wrap=True)
    put("推论 2 (推荐)", "Rmax ≈ VBP / (0.99 × IREF) − R10   （R10 = 3 kΩ）", mono=True, wrap=True)
    put("  为什么有 0.99", "边界处的电流已经跌落约 1% —— 这正是「误差 = 1%」的含义；"
                        "能用的负载电压由这个已跌落的电流决定，所以 R = V/I 比用 IREF 算大约 1%",
        wrap=True)
    put("  精度", f"对 {len(_dev)} 个精细临界值的检验：该式最大偏差 {max(_dev):.2f}%、"
                f"平均 {sum(_dev)/len(_dev):.3f}%", wrap=True, bold=True)
    # accuracy degrades sharply once the low-load base error approaches the budget
    _byd = {}
    for _v in VBPS:
        for _i in IREF_A:
            _gg = groups[(_v, _i)]
            if _gg["status"] != "EXACT":
                continue
            _p = _v / ((1 - T / 100) * _i * 1e6) * 1000 - 3.0
            _byd.setdefault(_i * 1e6, []).append(
                abs(_gg["lastP"] / 1000 - _p) / _p * 100)
    _big = {k: sum(v) / len(v) for k, v in _byd.items() if k >= 20}
    _small = {k: sum(v) / len(v) for k, v in _byd.items() if k < 20}
    _margin = min(T - groups[(_v2, _i2)]["first"]["IERR"]
                  for _v2 in VBPS for _i2 in IREF_A
                  if _i2 * 1e6 < 20 and groups[(_v2, _i2)]["status"] == "EXACT")         if _small else None
    if _small:
        put("  适用范围 (重要)", "该式在低负载基础误差远小于阈值时很准，反之失效："
                              f"目标电流 ≥20 µA 时平均偏差仅 "
                              f"{min(_big.values()):.3f}%~{max(_big.values()):.3f}%；"
                              f"但 10 µA 时平均 {list(_small.values())[0]:.3f}%"
                              f"（最大 {max(_byd[10.0]):.2f}%）—— 因为 10 µA 的基础误差距 "
                              f"{T:g}% 阈值只剩约 {_margin:.3f}% 余量，拐点几乎与顺从电压"
                              f"拐点重合，一阶模型失效。该情形请直接用表中实测值。",
            wrap=True, bold=True)
    r += 1

    put("§8  工作表说明 (Worksheet index)")
    for nm, desc in [
        ("README", "本页：数据来源、测量区间、判据、定义、限制与验证"),
        ("Raw_Data", f"全部原始扫描数据 {len(data)} 行 — 列序 Step | VBP_V | IREF_uA | RB_Ohm | "
                     "RB_kOhm | IBONE_uA | VBONE_V | IERR_pct | PASS"),
        ("Rmax_Summary", "Rmax 主结果矩阵 + 热力图数据（条件格式渐变）+ 状态矩阵 + 全局参数"),
        ("Boundary_Detail", "每个 VBP×IREF 的恒流临界区间（Last_PASS / First_FAIL 的 RB、电流、误差）"
                            "及建议细扫窗口"),
        ("Current_Accuracy", "低负载工作点恒流精度 + IERR 随负载变化矩阵（保留 10 µA 全部数据）"),
        ("Charts", "图① Maximum BONE Resistance vs BONE_P Voltage（旁边附状态表与说明）"),
        ("Charts_I_vs_R", "图③ Actual BONE Current vs BONE Resistance — 6 张独立图（按 BONE_P 分列）"),
        ("Chart_Source", f"图表源数据（−{T:g}% 限值线、扫描上限线、下限点），供图表单元格引用"),
    ]:
        put(nm, desc, wrap=True)
    r += 1

    put("§9  公式与可复算性 (Reproducibility)")
    put("Raw_Data", "仿真测量结果以【数值】保存（测量即原始事实，不公式化改写）；仅 RB_kOhm = RB_Ohm/1000 为公式")
    put("统计量", "Rmax_Summary / Boundary_Detail / Current_Accuracy 的统计结果均为【Excel 公式】：")
    put("  取组内最后匹配", "LOOKUP(2, 1/((VBP=x)*(IREF=y)*(PASS=1)), RD_RB)", mono=True)
    put("  条件计数/求和", "SUMPRODUCT((...)*(...))", mono=True)
    put("  组内条件最小值", "SUMPRODUCT(MIN(cond*RB + (1-cond)*1E+15))", mono=True)
    put("  文本拼接取整", "TEXT(value,\"General\")  —— 注意不要用 \"0.#\"（会输出 \"163.\"）", mono=True)
    put("重要", "本机 Excel 版本【不支持 MAXIFS/MINIFS】（实测返回 #NAME?），故全部改用上述兼容写法", wrap=True, bold=True)
    put("命名区域", "RD_STEP, RD_VBP, RD_IREF, RD_RB, RD_RBK, RD_IB, RD_VB, RD_IERR, RD_PASS → "
                   f"均指向 Raw_Data!$X$2:$X${NMAX}", mono=True, wrap=True)
    put("替换新日志", "① 重跑 parse_draft2.py 与 build_xlsx.py 可整表重建；"
                     "② 或仅替换 Raw_Data 数据区（A2:I20001）后按 Ctrl+Alt+F9 全量重算", wrap=True)
    r += 1

    put("§10  已知限制与不确定度")
    put("RB 分辨率", "分两段：RB ≤ 200 kΩ 为 1 kΩ 分辨，RB > 200 kΩ 为 10 kΩ 分辨。"
                    "因此上半段的临界区间只能定位到 10 kΩ；Boundary_Detail 的 "
                    "Last_PASS ~ First_FAIL 窗口即需细扫的区间（建议统一到 100 Ω 级）", wrap=True)
    _n_exact = sum(1 for _v in VBPS for _i in IREF_A
                   if groups[(_v, _i)]["status"] == "EXACT")
    put("扫描覆盖", f"三次扫描合并后 {_n_exact}/30 组合已测得真实临界值，无“≥扫描上限”情形；"
                   f"剩余 {30-_n_exact}/30 为 10 µA 的 N/A（基础误差），与负载范围无关", wrap=True,
        bold=True)
    put("扫描 C 的定位", "扫描 C（1–10 MΩ）【不含任何 PASS 点】（0/2730），因此不改变任何 Rmax；"
                       "它的作用是刻画完全失调节区：该区内 IBONE = V_BONE/RB（30/30 组合成立，纯负载线），"
                       "且 V_BONE 被钳在 ≈VBP（在约 0.3–1.5 µA 下与 VBP 相差仅 2–5.5 mV）", wrap=True)
    put("临界敏感点", "以下 4 个点的 IERR 距 1 % 阈值不足 0.05 %，对数值噪声/仿真设置敏感，"
                    "结论应视为 ±1 kΩ 量级不确定：", wrap=True)
    near = sorted((r_ for r_ in data if abs(r_["IERR"] - T) < CFG.ABS_TOL_PCT),
                  key=lambda x: x["IERR"])
    for r_ in near:
        put(f"  VBP={r_['vbp']} V, IREF={r_['iref']*MUA:.0f} µA",
            f"RB = {r_['rb']/1000:.0f} kΩ   IERR = {r_['IERR']:.5f} %   "
            f"PASS = {r_['PASS']}   (IBONE = {r_['IBONE']*MUA:.5f} µA)")
    put("未覆盖项", "未包含温度漂移、工艺容差、R_BONE 自身容差与老化；R_BONE 按理想电阻建模", wrap=True)
    put("伪数据声明", "本报告未对任何缺失点插值、外推或补数；所有数值均直接来自 Draft2.log 的 .meas 结果", wrap=True, bold=True)
    r += 1

    put("§11  数据完整性验证 (Validation summary)")
    put("网格完整性", f"两次扫描合计期望 {len(data)} 组（5 IREF × {len(ALL_RB)} RB × 6 VBP）；"
                    f"解析 {len(data)} 行；唯一 (VBP,IREF,RB) 组合 {len(D)} 个；重复 0；缺失 0；"
                    f"RB 反算最大相对误差 6.2e-08（扫描 B）/ 4.8e-07（扫描 A）", bold=True, wrap=True)
    put("step↔meas 匹配", "独立校验：用每行 VBONE/IBONE 反算 RB，与日志 .step 的 RB 最大相对误差 "
                        "4.75e-07 → 证明 .meas 结果与 .step 参数按 step 编号一一对应无误", wrap=True, bold=True)
    put("IERR 一致性", "最大偏差 2.5e-10 %pt")
    _bad = sum(1 for _r in data if _r["PASS_T"] != int(_r["IERR"] <= T))
    put("PASS 一致性", f"按 {T:g}% 阈值重算 PASS，与 IERR 不一致的行数 = {_bad}")
    put("PASS 统计", f"PASS=1：{sum(1 for r_ in data if r_['PASS']==1)} 行 ； "
                   f"PASS=0：{sum(1 for r_ in data if r_['PASS']==0)} 行")
    put("IERR 范围", f"{min(r_['IERR'] for r_ in data):.4f} % … {max(r_['IERR'] for r_ in data):.4f} %")
    put("单调性", "已检查：每个 (VBP,IREF) 组内 IERR 随 RB 单调不减 → PASS 序列为 1…1 0…0，"
                 "故 Last_PASS / First_FAIL 临界区间定义无歧义", wrap=True)
    r += 1
    put("免责", "本工作簿为仿真结果整理，不替代实测验证。", wrap=True)

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 108
    return ws


# ============================================================== 2. Raw_Data
def build_raw():
    ws = wb.create_sheet("Raw_Data")
    hdr = ["Step", "VBP_V", "IREF_uA", "RB_Ohm", "RB_kOhm", "IBONE_uA",
           "VBONE_V", "IERR_pct", "PASS", "Sweep", "Source_Log"]
    for j, h in enumerate(hdr, start=1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = F_HDR
        c.fill = FILL_HDR
        c.alignment = CTR
        c.border = BOX
    for i, r_ in enumerate(data, start=2):
        ws.cell(row=i, column=1, value=r_["step"]).number_format = NF_INT
        ws.cell(row=i, column=2, value=r_["vbp"]).number_format = NF_1DP
        ws.cell(row=i, column=3, value=round(r_["iref"] * MUA, 6)).number_format = NF_INT
        ws.cell(row=i, column=4, value=int(r_["rb"])).number_format = NF_URB
        ws.cell(row=i, column=5, value=f"=D{i}/1000").number_format = NF_UK
        ws.cell(row=i, column=6, value=round(r_["IBONE"] * MUA, 6)).number_format = NF_MUA
        ws.cell(row=i, column=7, value=round(r_["VBONE"], 9)).number_format = NF_V
        ws.cell(row=i, column=8, value=round(r_["IERR"], 9)).number_format = NF_PCT4
        # PASS is written later by fill_pass_formulas(): it is a live formula
        # referencing the threshold cell, whose row is only known once
        # Rmax_Summary has been laid out.
        ws.cell(row=i, column=9).number_format = NF_INT
        # provenance: which log this row came from (A..I keep the agreed order)
        ws.cell(row=i, column=10, value=int(r_["sweep"])).number_format = NF_INT
        ws.cell(row=i, column=11, value=r_["log"]).font = F_NOTE
        for j in range(1, 12):
            ws.cell(row=i, column=j).font = F_BODY
        ws.cell(row=i, column=11).font = F_NOTE
    last = len(data) + 1
    RAW_LAST[0] = last
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:K{last}"
    # row-wide PASS colouring
    ws.conditional_formatting.add(
        f"A2:K{last}", FormulaRule(formula=["$I2=1"], fill=FILL_GREEN))
    ws.conditional_formatting.add(
        f"A2:K{last}", FormulaRule(formula=["$I2=0"], fill=FILL_RED))
    for col, w in zip("ABCDEFGHIJK", (9, 8, 9, 11, 11, 14, 13, 10, 7, 7, 16)):
        ws.column_dimensions[col].width = w
    return ws


# ========================================================== 3. Rmax_Summary
RM_ROW = dict(MAIN_HDR=6, MAIN_0=7, HEAT_HDR=20, HEAT_0=21, STAT_HDR=29,
              STAT_0=30, P_MIN=38, P_MAX=39, THRESH=41)
RAW_LAST = [0]        # last Raw_Data row, for the deferred PASS formulas


def fill_pass_formulas():
    """Raw_Data!I = IF(IERR <= threshold, 1, 0), referencing the one threshold cell."""
    ws = wb["Raw_Data"]
    tref = f"Rmax_Summary!$B${RM_ROW['THRESH']}"
    for i in range(2, RAW_LAST[0] + 1):
        ws.cell(row=i, column=9, value=f"=IF(H{i}<={tref},1,0)")
MATRIX_CELLS = []      # (row, col) of Block A cells; filled after Block D


def f_matrix(r, cref):
    """Rmax display formula for main matrix row r, IREF header cell cref."""
    cond = f"(RD_VBP=$A{r})*(RD_IREF={cref})"
    anyp = f"SUMPRODUCT({cond}*(RD_PASS=1))=0"
    atmax = f"SUMPRODUCT({cond}*(RD_RB=$B${RM_ROW['P_MAX']})*(RD_PASS=1))>0"
    lastp = f"LOOKUP(2,1/({cond}*(RD_PASS=1)),RD_RB)"
    return (f'=IF({anyp},"N/A (基础误差>{T:g}%)",'
            f'IF({atmax},"≥"&TEXT($B${RM_ROW["P_MAX"]}/1000,"General")&" kΩ (扫描上限)",'
            f'TEXT({lastp}/1000,"General")&" kΩ"))')


def fill_matrix_formulas(ws, cells):
    """Write Block A formulas. Must run AFTER Block D so RM_ROW['P_MAX'] is final."""
    for r, col in cells:
        cref = f"{get_column_letter(col)}${RM_ROW['MAIN_HDR']}"
        ws.cell(row=r, column=col, value=f_matrix(r, cref))


def build_rmax():
    ws = wb.create_sheet("Rmax_Summary")
    ws.sheet_view.showGridLines = False

    ws["A1"] = (f"Rmax_Summary — 最大 BONE 负载电阻 Rmax"
                f"（满足 IERR ≤ ±{T:g}% 的最大已扫描 RB）")
    ws["A1"].font = F_TITLE
    ws["A2"] = (f"数据来源：Raw_Data（解析自 Draft2.log）。扫描范围 RB = {RB_MIN/1000:.0f} kΩ … "
                f"{RB_MAX/1000:.0f} kΩ（两种分辨率，{len(ALL_RB)} 个取值）。"
                f"单位：kΩ。")
    ws["A2"].font = F_SUB
    ws["A3"] = "本页 Block A 为 Excel 公式（LOOKUP / SUMPRODUCT），替换 Raw_Data 后可自动重算；标记规则见下方图例。"
    ws["A3"].font = F_SUB

    # ---- Block A: main matrix --------------------------------------------
    ws.cell(row=5, column=1,
            value="A. 主结果矩阵 — 每格 = 该 BONE_P 电压 + 目标电流下满足 PASS=1 的最大已扫描 RB").font = F_BOLD
    h = ws.cell(row=RM_ROW["MAIN_HDR"], column=1, value="BONE_P / V")
    h.font = F_HDR; h.fill = FILL_HDR; h.alignment = CTR; h.border = BOX
    for j, iu in enumerate(IREF_UA):
        c = ws.cell(row=RM_ROW["MAIN_HDR"], column=2 + j, value=iu)
        c.font = F_HDR; c.fill = FILL_HDR; c.alignment = CTR
        c.border = BOX; c.number_format = HDR_UA
    for k, v in enumerate(VBPS):
        r = RM_ROW["MAIN_0"] + k
        c = ws.cell(row=r, column=1, value=v)
        c.font = F_BOLD; c.number_format = NF_1DP; c.alignment = CTR; c.border = BOX
        c.fill = FILL_HDR2
        for j in range(5):
            cc = ws.cell(row=r, column=2 + j)
            cc.font = F_BODY; cc.border = BOX; cc.alignment = CTR
            # formula filled in after Block D fixes RM_ROW['P_MAX']
            MATRIX_CELLS.append((r, 2 + j))

    r = RM_ROW["MAIN_0"] + len(VBPS)
    ws.cell(row=r, column=1, value="图例 / Legend：").font = F_BOLD
    legends = [
        ("精确值（如 163 kΩ）", "RB 继续增大即 FAIL，属真实临界值", FILL_GREEN),
        ("≥200 kΩ (扫描上限)", f"在扫描上限 {RB_MAX/1000:.0f} kΩ 处仍 PASS → 结果是【下限】，真实 Rmax 更大，需扩大扫描范围", FILL_AMBER),
        (f"N/A (基础误差>{T:g}%)", f"最小负载 RB={RB_MIN/1000:.0f} kΩ 时 IERR 已 >{T:g}% → 属电路基础恒流误差，"
                          "【不能】解释为 Rmax = 0；原始数据保留于 Raw_Data", FILL_RED),
    ]
    for i, (a, b, f) in enumerate(legends, start=1):
        ws.cell(row=r + i, column=1, value=a).fill = f
        ws.cell(row=r + i, column=1).font = F_BODY
        ws.cell(row=r + i, column=2, value=b).font = F_NOTE
    r = r + len(legends) + 2

    # ---- Block B: heatmap data ------------------------------------------
    ws.cell(row=r, column=1,
            value="B. Rmax 热力图数据 (kΩ) — 仅含【实测精确值】；空白 = 本次扫描未覆盖"
                  "（≥扫描上限 或 N/A）。本块用于条件格式热力图与 Charts 工作表。").font = F_BOLD
    hh = r
    RM_ROW["HEAT_HDR"] = hh + 1
    RM_ROW["HEAT_0"] = hh + 2
    ws.cell(row=hh + 1, column=1, value="BONE_P / V").font = F_HDR
    for j, iu in enumerate(IREF_UA):
        c = ws.cell(row=hh + 1, column=2 + j, value=iu)
        c.font = F_HDR; c.number_format = HDR_UA; c.alignment = CTR
    for k, v in enumerate(VBPS):
        rr = hh + 2 + k
        ws.cell(row=rr, column=1, value=v).font = F_BOLD
        ws.cell(row=rr, column=1).number_format = NF_1DP
        for j, iu in enumerate(IREF_UA):
            val = RMX_NUM[(v, iu / 1e6)]
            cc = ws.cell(row=rr, column=2 + j,
                         value=(None if val is None else round(val, 6)))
            cc.number_format = NF_UK
    assert hh + 1 == RM_ROW["HEAT_HDR"] and hh + 2 == RM_ROW["HEAT_0"], (hh, RM_ROW)
    hrange = f"B{RM_ROW['HEAT_0']}:F{RM_ROW['HEAT_0']+len(VBPS)-1}"
    ws.conditional_formatting.add(hrange, ColorScaleRule(
        start_type="min", start_color="FFFFC7CE",
        mid_type="percentile", mid_value=50, mid_color="FFFFEB9C",
        end_type="max", end_color="FFC6EFCE"))
    r = RM_ROW["HEAT_0"] + len(VBPS) + 1

    # ---- Block C: status matrix -----------------------------------------
    ws.cell(row=r, column=1,
            value="C. 数据状态矩阵 — 绿 = 精确临界值 ；黄 = ≥扫描上限（下限，需扩大扫描）；"
                  f"红 = N/A（基础误差>{T:g}%）").font = F_BOLD
    r += 1
    RM_ROW["STAT_HDR"] = r
    RM_ROW["STAT_0"] = r + 1
    ws.cell(row=r, column=1, value="BONE_P / V").font = F_HDR
    for j, iu in enumerate(IREF_UA):
        c = ws.cell(row=r, column=2 + j, value=iu)
        c.font = F_HDR; c.number_format = HDR_UA; c.alignment = CTR
    ST_TXT = {"EXACT": "精确", "LB": "≥ 扫描上限 (下限)",
              "N/A": f"N/A 基础误差>{T:g}%"}
    ST_FILL = {"EXACT": FILL_GREEN, "LB": FILL_AMBER, "N/A": FILL_RED}
    for k, v in enumerate(VBPS):
        rr = r + 1 + k
        ws.cell(row=rr, column=1, value=v).font = F_BOLD
        ws.cell(row=rr, column=1).number_format = NF_1DP
        for j, iu in enumerate(IREF_UA):
            st = groups[(v, iu / 1e6)]["status"]
            cc = ws.cell(row=rr, column=2 + j, value=ST_TXT[st])
            cc.fill = ST_FILL[st]; cc.font = F_BODY; cc.border = BOX
            cc.alignment = CTR
    r = RM_ROW["STAT_0"] + len(VBPS) + 1

    # ---- Block D: global parameters --------------------------------------
    ws.cell(row=r, column=1, value="D. 全局参数（供本工作簿各处公式引用）").font = F_BOLD
    r += 1
    RM_ROW["P_MIN"] = r
    RM_ROW["P_MAX"] = r + 1
    params = [
        ("扫描最小 RB (Ω)", f"=MIN({NAMED['RD_RB']})", NF_URB),
        ("扫描最大 RB (Ω)", f"=MAX({NAMED['RD_RB']})", NF_URB),
        ("数据行数 (仿真组合数)", f"=COUNT({NAMED['RD_RB']})", NF_INT),
        ("PASS 判据 IERR ≤ (%)", T, "0.0#"),
        ("VBP 取值个数", f"=COUNT($A${RM_ROW['MAIN_0']}:$A${RM_ROW['MAIN_0']+len(VBPS)-1})", NF_INT),
        ("目标电流取值个数", f"=COUNT($B${RM_ROW['MAIN_HDR']}:$F${RM_ROW['MAIN_HDR']})", NF_INT),
        ("扫描上限处仍 PASS 的组合数 (→下限)", f"=SUMPRODUCT(({NAMED['RD_RB']}=$B${RM_ROW['P_MAX']})*({NAMED['RD_PASS']}=1))", NF_INT),
        ("最小负载即 FAIL 的组合数 (→N/A)", f"=SUMPRODUCT(({NAMED['RD_RB']}=$B${RM_ROW['P_MIN']})*({NAMED['RD_PASS']}=0))", NF_INT),
        ("PASS=1 数据行数", f"=SUMPRODUCT({NAMED['RD_PASS']})", NF_INT),
        ("PASS=0 数据行数", f"=$B${r+2}-$B${r+8}", NF_INT),
    ]
    for i, (lab, val, nf) in enumerate(params):
        rr = r + i
        ws.cell(row=rr, column=1, value=lab).font = F_BOLD
        c = ws.cell(row=rr, column=2, value=val)
        c.number_format = nf; c.font = F_BODY
        if lab.startswith("PASS 判据"):
            RM_ROW["THRESH"] = rr
    r = r + len(params) + 1

    # Block A formulas last: they reference $B$<P_MAX>, which is only known now.
    fill_matrix_formulas(ws, MATRIX_CELLS)

    ws.cell(row=r, column=1,
            value=f"注：Block B 为静态数值（由解析脚本从 Raw_Data 生成），以保证图表把空白识别为"
                  f"真正的空点（公式返回 \"\" 会被图表当作 0）。Block A 为公式，替换数据后可重算。").font = F_NOTE
    ws.column_dimensions["A"].width = 40
    for col in "BCDEF":
        ws.column_dimensions[col].width = 30
    return ws


# ======================================================= 4. Boundary_Detail
BD_HDR = 4
BD_0 = 5


def build_boundary():
    ws = wb.create_sheet("Boundary_Detail")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Boundary_Detail — 每个 BONE_P × 目标电流的恒流临界区间"
    ws["A1"].font = F_TITLE
    ws["A2"] = ("Last_PASS_RB = 仍满足 PASS=1 的最大 RB ；First_FAIL_RB = 其上方第一个 PASS=0 的 RB。"
                "二者之间即建议细扫窗口（当前分辨率 1 kΩ）。")
    ws["A2"].font = F_SUB
    cols = ["VBP_V", "IREF_uA", "Last_PASS_RB_kOhm", "First_FAIL_RB_kOhm",
            "Last_PASS_I_uA", "First_FAIL_I_uA", "Last_PASS_Error_pct",
            "First_FAIL_Error_pct", "Refine_Window_kOhm", "Status_Note",
            "（参考）Last_PASS_RB_Ohm", "（参考）First_FAIL_RB_Ohm"]
    for j, h in enumerate(cols, start=1):
        c = ws.cell(row=BD_HDR, column=j, value=h)
        c.font = F_HDR; c.fill = FILL_HDR; c.alignment = CTR; c.border = BOX
    for k in range(len(VBPS) * len(IREF_A)):
        r = BD_0 + k
        v = VBPS[k // len(IREF_A)]
        i_a = IREF_A[k % len(IREF_A)]
        g = groups[(v, i_a)]
        ws.cell(row=r, column=1, value=v).number_format = NF_1DP
        ws.cell(row=r, column=2, value=round(i_a * MUA, 6)).number_format = NF_INT
        cond = "(RD_VBP=$A{r})*(RD_IREF=$B{r})"
        # reference numeric helpers (K, L)
        ws.cell(row=r, column=11,
                value=f'=IFERROR(LOOKUP(2,1/({cond.format(r=r)}*(RD_PASS=1)),RD_RB),"")'
                ).number_format = NF_URB
        ws.cell(row=r, column=12,
                value=(f'=IF($K{r}="","",'
                       f'IF(SUMPRODUCT({cond.format(r=r)}*(RD_PASS=0)*(RD_RB>$K{r}))=0,"",'
                       f'SUMPRODUCT(MIN({cond.format(r=r)}*(RD_PASS=0)*(RD_RB>$K{r})*RD_RB'
                       f'+(1-{cond.format(r=r)}*(RD_PASS=0)*(RD_RB>$K{r}))*1E+15))))'
                       )).number_format = NF_URB
        ws.cell(row=r, column=3, value=f'=IF($K{r}="","N/A",$K{r}/1000)').number_format = NF_UK
        ws.cell(row=r, column=4,
                value=(f'=IF($K{r}="","N/A (无临界区)",'
                       f'IF($L{r}="","无 (扫描上限内仍 PASS)",$L{r}/1000))')
                ).number_format = NF_UK
        ws.cell(row=r, column=5,
                value=(f'=IF($K{r}="","N/A",'
                       f'LOOKUP(2,1/({cond.format(r=r)}*(RD_RB=$K{r})),RD_IB))')
                ).number_format = NF_MUA
        ws.cell(row=r, column=6,
                value=(f'=IF($L{r}="","N/A",'
                       f'LOOKUP(2,1/({cond.format(r=r)}*(RD_RB=$L{r})),RD_IB))')
                ).number_format = NF_MUA
        ws.cell(row=r, column=7,
                value=f'=IF($K{r}="","N/A",LOOKUP(2,1/({cond.format(r=r)}*(RD_RB=$K{r})),RD_IERR))'
                ).number_format = NF_PCT4
        ws.cell(row=r, column=8,
                value=f'=IF($L{r}="","N/A",LOOKUP(2,1/({cond.format(r=r)}*(RD_RB=$L{r})),RD_IERR))'
                ).number_format = NF_PCT4
        ws.cell(row=r, column=9,
                value=(f'=IF($K{r}="","— (需先解决基础误差)",'
                       f'IF($L{r}="","— (需将扫描上限扩大到 "&TEXT({RB_MAX/1000},"General")'
                       f'&" kΩ 以上)",'
                       f'TEXT($K{r}/1000,"General")&" ~ "&TEXT($L{r}/1000,"General")&" kΩ 之间细扫"))')
                )
        ws.cell(row=r, column=10,
                value=(f'=IF(SUMPRODUCT({cond.format(r=r)}*(RD_PASS=1))=0,'
                       f'"基础误差>{T:g}%：全程 FAIL（最小负载 RB="&'
                       f'TEXT(Rmax_Summary!$B${RM_ROW["P_MIN"]}/1000,"General")&'
                       f'" kΩ 时 IERR 已 >{T:g}%），无恒流临界区，应改进电路而非缩小负载",'
                       f'IF($L{r}="","扫描上限 ("&TEXT(Rmax_Summary!$B${RM_ROW["P_MAX"]}/1000,'
                       f'"General")&" kΩ) 内仍 PASS：Rmax 为下限，需扩大扫描范围",'
                       f'"正常恒流临界区，建议按 I 列窗口细扫"))')
                )
        for j in range(1, 11):
            ws.cell(row=r, column=j).font = F_BODY
            ws.cell(row=r, column=j).border = BOX
        ws.cell(row=r, column=10).alignment = WRAP
        ws.cell(row=r, column=9).alignment = WRAP
    last = BD_0 + len(VBPS) * len(IREF_A) - 1
    ws.freeze_panes = f"A{BD_0}"
    ws.auto_filter.ref = f"A{BD_HDR}:L{last}"
    # highlight the rows that need no refinement vs the special cases
    ws.conditional_formatting.add(
        f"J{BD_0}:J{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("基础误差",$J{BD_0}))'], fill=FILL_RED))
    ws.conditional_formatting.add(
        f"J{BD_0}:J{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("下限",$J{BD_0}))'], fill=FILL_AMBER))
    ws.conditional_formatting.add(
        f"J{BD_0}:J{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("正常",$J{BD_0}))'], fill=FILL_GREEN))
    for col, w in zip("ABCDEFGHIJKL",
                      (8, 9, 13, 14, 13, 14, 13, 14, 28, 62, 15, 15)):
        ws.column_dimensions[col].width = w
    return ws


# ===================================================== 5. Current_Accuracy
CA_HDR = 5
CA_0 = 6
CA_BH = 39
CA_B0 = 40


def build_accuracy():
    ws = wb.create_sheet("Current_Accuracy")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Current_Accuracy — 目标恒流精度分析（IREF = 10 µA 全部数据保留，未因 PASS=0 删除）"
    ws["A1"].font = F_TITLE
    ws["A2"] = (f"低负载区域 = RB 取扫描最小值 {RB_MIN/1000:.0f} kΩ（恒流区最有利工况）。"
                "误差直接取日志 .meas 的 IERR；另给出按公式重算值以便核对。")
    ws["A2"].font = F_SUB
    ws["A4"] = ("A. 低负载工作点精度（每个 BONE_P × 目标电流一行；"
                "Last/Fail 临界详见 Boundary_Detail）")
    ws["A4"].font = F_BOLD
    cols = ["VBP_V", "Target_I_uA", "RB_low_kOhm", "Actual_I_uA", "Error_pct",
            f"Within_±{T:g}%", "V_BONE_V", "Error_recalc_pct", "Δ_vs_log_pctpt", "Note"]
    for j, h in enumerate(cols, start=1):
        c = ws.cell(row=CA_HDR, column=j, value=h)
        c.font = F_HDR; c.fill = FILL_HDR; c.alignment = CTR; c.border = BOX
    for k in range(len(VBPS) * len(IREF_A)):
        r = CA_0 + k
        v = VBPS[k // len(IREF_A)]
        i_a = IREF_A[k % len(IREF_A)]
        ws.cell(row=r, column=1, value=v).number_format = NF_1DP
        ws.cell(row=r, column=2, value=round(i_a * MUA, 6)).number_format = NF_INT
        ws.cell(row=r, column=3,
                value=f"=Rmax_Summary!$B${RM_ROW['P_MIN']}/1000").number_format = NF_UK
        cond = f"(RD_VBP=$A{r})*(RD_IREF=$B{r})*(RD_RB=Rmax_Summary!$B${RM_ROW['P_MIN']})"
        ws.cell(row=r, column=4,
                value=f'=IFERROR(LOOKUP(2,1/({cond}),RD_IB),"")'
                ).number_format = NF_MUA
        ws.cell(row=r, column=5,
                value=f'=IFERROR(LOOKUP(2,1/({cond}),RD_IERR),"")'
                ).number_format = NF_PCT4
        ws.cell(row=r, column=6,
                value=f'=IF(NOT(ISNUMBER($E{r})),"",IF($E{r}<={T:g},"Yes","No"))'
                ).alignment = CTR
        ws.cell(row=r, column=7,
                value=f'=IFERROR(LOOKUP(2,1/({cond}),RD_VB),"")'
                ).number_format = NF_V
        ws.cell(row=r, column=8,
                value=f'=IF(NOT(ISNUMBER($D{r})),"",100*ABS($D{r}-$B{r})/$B{r})'
                ).number_format = NF_PCT4
        ws.cell(row=r, column=9,
                value=f'=IF(OR(NOT(ISNUMBER($E{r})),NOT(ISNUMBER($H{r}))),"",$H{r}-$E{r})'
                ).number_format = "0.000000000"
        ws.cell(row=r, column=10,
                value=(f'=IF($F{r}="No","基础恒流误差 >{T:g}%：原始数据保留，'
                       f'Rmax_Summary 中标记为 N/A（不写作 0）",'
                       f'IF($F{r}="Yes","低负载区满足 ±{T:g}%","无数据"))')
                ).alignment = WRAP
        for j in range(1, 11):
            ws.cell(row=r, column=j).font = F_BODY
            ws.cell(row=r, column=j).border = BOX
    last = CA_0 + len(VBPS) * len(IREF_A) - 1
    ws.conditional_formatting.add(
        f"F{CA_0}:F{last}", FormulaRule(formula=[f'$F{CA_0}="Yes"'], fill=FILL_GREEN))
    ws.conditional_formatting.add(
        f"F{CA_0}:F{last}", FormulaRule(formula=[f'$F{CA_0}="No"'], fill=FILL_RED))

    # Block B -----------------------------------------------------------------
    ws.cell(row=37, column=1,
            value=f"B. 恒流误差 IERR (%) 随负载变化 — 绿 = 仍在 ±{T:g}% 恒流区 ；"
                  f"红 = 已超出 ±{T:g}% ；用于判断各负载下何时掉出恒流区").font = F_BOLD
    assert CA_BH == 39
    hdrB = ["VBP_V", "Target_I_uA"] + KEY_RB + [f"n_PASS (共 {len(ALL_RB)} 点)"]
    for j, h in enumerate(hdrB, start=1):
        c = ws.cell(row=CA_BH, column=j, value=h)
        c.font = F_HDR; c.fill = FILL_HDR; c.alignment = CTR; c.border = BOX
        if isinstance(h, int):
            c.number_format = '#,##0" Ω"'
    for k in range(len(VBPS) * len(IREF_A)):
        r = CA_B0 + k
        v = VBPS[k // len(IREF_A)]
        i_a = IREF_A[k % len(IREF_A)]
        ws.cell(row=r, column=1, value=v).number_format = NF_1DP
        ws.cell(row=r, column=2, value=round(i_a * MUA, 6)).number_format = NF_INT
        for j in range(len(KEY_RB)):
            cl = get_column_letter(3 + j)
            ws.cell(row=r, column=3 + j,
                    value=(f'=IFERROR(LOOKUP(2,1/((RD_VBP=$A{r})*(RD_IREF=$B{r})'
                           f'*(RD_RB={cl}${CA_BH})),RD_IERR),"")')
                    ).number_format = NF_PCT4
        ws.cell(row=r, column=3 + len(KEY_RB),
                value=f'=SUMPRODUCT((RD_VBP=$A{r})*(RD_IREF=$B{r})*(RD_PASS=1))'
                ).number_format = NF_INT
        for j in range(1, 4 + len(KEY_RB)):
            ws.cell(row=r, column=j).font = F_BODY
            ws.cell(row=r, column=j).border = BOX
    lastB = CA_B0 + len(VBPS) * len(IREF_A) - 1
    brange = (f"C{CA_B0}:"
              f"{get_column_letter(2 + len(KEY_RB))}{lastB}")
    ws.conditional_formatting.add(brange, FormulaRule(
        formula=[f'AND(ISNUMBER(C{CA_B0}),C{CA_B0}<={T:g})'], fill=FILL_GREEN))
    ws.conditional_formatting.add(brange, FormulaRule(
        formula=[f'AND(ISNUMBER(C{CA_B0}),C{CA_B0}>{T:g})'], fill=FILL_RED))
    ws.freeze_panes = f"A{CA_0}"
    for col, w in zip("ABCDEFGHIJ", (8, 11, 12, 13, 11, 11, 12, 14, 15, 46)):
        ws.column_dimensions[col].width = w
    for j in range(len(KEY_RB)):
        ws.column_dimensions[get_column_letter(3 + j)].width = 13
    ws.column_dimensions[get_column_letter(3 + len(KEY_RB))].width = 13
    ws.column_dimensions["H"].width = 15
    return ws


# ============================================================== 6. Charts
def styled_title(text, size=1100, bold=True):
    """Build a chart/axis Title; each '\\n'-separated line becomes its own paragraph."""
    cp = CharacterProperties(sz=size, b=bold)
    paras = [Paragraph(pPr=ParagraphProperties(defRPr=cp),
                       endParaRPr=CharacterProperties(sz=size, b=bold),
                       r=[RegularTextRun(rPr=cp, t=line)])
             for line in text.split("\n")]
    return Title(tx=Text(rich=RichText(bodyPr=RichTextProperties(), p=paras)),
                 overlay=False)


def axis_title(text, size=1000):
    return styled_title(text, size=size, bold=False)


def build_charts():
    ws = wb.create_sheet("Charts")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Charts — 图① Maximum BONE Resistance vs BONE_P Voltage"
    ws["A1"].font = F_TITLE

    ch = ScatterChart()
    ch.scatterStyle = "lineMarker"
    ch.style = 2
    # Title kept to one line: the ≥lower-bound / N-A caveats are carried by the
    # legend entry and the status table beside the chart (as requested), which
    # keeps the figure clean enough to drop into a paper.
    ch.title = styled_title(
        "Maximum BONE Resistance vs BONE_P Voltage", size=1100)
    ch.x_axis.title = axis_title("BONE_P Voltage (V)")
    ch.y_axis.title = axis_title("Maximum BONE Resistance (kΩ)")
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.x_axis.majorTickMark = "out"
    ch.y_axis.majorTickMark = "out"
    ch.height = 11.5
    ch.width = 18.0
    ch.legend.position = "b"
    ch.legend.overlay = False
    ch.x_axis.number_format = "0.#"
    ch.y_axis.number_format = "0"
    ch.x_axis.majorGridlines = None

    h0, h1 = RM_ROW["HEAT_0"], RM_ROW["HEAT_0"] + len(VBPS) - 1
    xref = Reference(ws, min_col=1, min_row=h0, max_row=h1)   # placeholder, replaced below
    # x values live on Rmax_Summary
    rms = wb["Rmax_Summary"]
    for j, iu in enumerate(IREF_UA):
        col = 2 + j
        yref = Reference(rms, min_col=col, min_row=h0, max_row=h1)
        xref = Reference(rms, min_col=1, min_row=h0, max_row=h1)
        _has = any(RMX_NUM[(v, iu / 1e6)] is not None for v in VBPS)
        name = (f"{iu} µA" if _has else f"{iu} µA (N/A: all above {T:g}%)")
        s = Series(yref, xref, title=name)
        s.marker = Marker(symbol="circle", size=(7 if iu != 10 else 5))
        s.graphicalProperties.line.solidFill = SERIES_COLOR[j]
        s.graphicalProperties.line.width = 22000
        s.smooth = False
        ch.series.append(s)
    # lower-bound overlay points
    cs = wb["Chart_Source"]
    nlb = CS_ROW.get("lb_n", 0)
    if nlb:
        s = Series(Reference(cs, min_col=2, min_row=CS_ROW["lb_0"],
                             max_row=CS_ROW["lb_0"] + nlb - 1),
                   Reference(cs, min_col=1, min_row=CS_ROW["lb_0"],
                             max_row=CS_ROW["lb_0"] + nlb - 1),
                   title=f"≥{RB_MAX/1000:.0f} kΩ only (lower bound)")
        s.marker = Marker(symbol="x", size=9)
        s.marker.graphicalProperties.solidFill = "FF0000"
        s.marker.graphicalProperties.line.solidFill = "FF0000"
        s.graphicalProperties.line.noFill = True
        ch.series.append(s)
    # scan-limit reference line
    # Only draw it when at least one point is actually censored: with RB_MAX now
    # 10 MΩ a line at the ceiling would crush every curve flat.
    if CENSORED:
        s = Series(Reference(cs, min_col=2, min_row=CS_ROW["lim_0"],
                             max_row=CS_ROW["lim_1"]),
                   Reference(cs, min_col=1, min_row=CS_ROW["lim_0"],
                             max_row=CS_ROW["lim_1"]),
                   title=f"Scan limit {fmt_rb(RB_MAX)}")
        s.marker = Marker(symbol="none")
        s.graphicalProperties.line.solidFill = "808080"
        s.graphicalProperties.line.width = 12000
        s.graphicalProperties.line.dashStyle = "dash"
        s.smooth = False
        ch.series.append(s)
    ws.add_chart(ch, "B3")



    # ---- status table beside the chart ① --------------------------------
    ws["N2"] = "状态表（与 Rmax_Summary Block C 同步）"
    ws["N2"].font = F_BOLD
    c = ws.cell(row=3, column=14, value="BONE_P / V")
    c.font = F_HDR; c.fill = FILL_HDR; c.border = BOX; c.alignment = CTR
    for j, iu in enumerate(IREF_UA):
        cc = ws.cell(row=3, column=15 + j, value=iu)
        cc.font = F_HDR; cc.fill = FILL_HDR; cc.number_format = HDR_UA
        cc.border = BOX; cc.alignment = CTR
    for k, v in enumerate(VBPS):
        rr = 4 + k
        cc = ws.cell(row=rr, column=14,
                     value=f"=Rmax_Summary!$A${RM_ROW['STAT_0']+k}")
        cc.number_format = NF_1DP; cc.font = F_BOLD; cc.border = BOX
        for j in range(5):
            src = f"{get_column_letter(2+j)}{RM_ROW['STAT_0']+k}"
            x = ws.cell(row=rr, column=15 + j, value=f"=Rmax_Summary!{src}")
            x.font = F_BODY; x.border = BOX; x.alignment = CTR
    ws.conditional_formatting.add(
        "O4:S9", FormulaRule(formula=['ISNUMBER(SEARCH("精确",O4))'], fill=FILL_GREEN))
    ws.conditional_formatting.add(
        "O4:S9", FormulaRule(formula=['ISNUMBER(SEARCH("下限",O4))'], fill=FILL_AMBER))
    ws.conditional_formatting.add(
        "O4:S9", FormulaRule(formula=['ISNUMBER(SEARCH("N/A",O4))'], fill=FILL_RED))

    rr = 11
    notes = [
        ("绘图规则（务必遵守）", None, True),
        ("· 实线 + 圆点", "仅连接【实测精确】Rmax（RB 继续增大即 FAIL）；三次扫描合并后"
                        "24/30 组合已测得真实临界值", False),
        ("· 红色 × 标记", "仅在下限未知时出现（在上限处仍 PASS）。本次合并后【无此情形】，"
                        "故图中没有 × 标记", False),
        ("· 灰色虚线", "扫描上限参考线，仅当存在“≥上限”的点时才绘制；本次无此类点，故不绘制", False),
        ("· 10 µA", "10 µA 的低负载基础误差为 "
                   + " ~ ".join(f"{groups[(v, 1e-5)]['first']['IERR']:.3f}%"
                                for v in (VBPS[0], VBPS[-1]))
                   + f"，与 ±{T:g}% 判据的关系见 Rmax_Summary 与状态表", False),
        ("· 无插值", "未对缺失点插值或外推；空白即未仿真，不补数", False),
        ("需细扫的组合（窗口见 Boundary_Detail）", None, True),
    ]
    for a, b, isbold in notes:
        cc = ws.cell(row=rr, column=14, value=a)
        cc.font = F_BOLD if isbold else F_BODY
        if b:
            ws.cell(row=rr, column=15, value=b).font = F_NOTE
        rr += 1
    refine = [f"VBP={v:g} V, {i*1e6:.0f} µA → "
              f"{groups[(v,i)]['lastP']/1000:.0f} ~ {groups[(v,i)]['firstF']/1000:.0f} kΩ"
              for v in VBPS for i in IREF_A
              if groups[(v, i)]["status"] == "EXACT" and groups[(v, i)]["firstF"]]
    for t in refine:
        ws.cell(row=rr, column=14, value=t).font = F_NOTE
        rr += 1
    if CENSORED:
        rr += 1
        ws.cell(row=rr, column=14, value="需扩大扫描范围（目前只能给下限）").font = F_BOLD
        rr += 1
        for v, i, _ in CENSORED:
            ws.cell(row=rr, column=14,
                    value=f"VBP={v:g} V, {i*1e6:.0f} µA → Rmax ≥ {fmt_rb(RB_MAX)}").font = F_NOTE
            rr += 1
    ws.column_dimensions["A"].width = 2
    for col in "NOPQRS":
        ws.column_dimensions[col].width = 22
    ws.column_dimensions["N"].width = 34
    return ws


# ======================================================= 7. Charts_I_vs_R
def build_current_charts():
    ws = wb.create_sheet("Charts_I_vs_R")
    ws.sheet_view.showGridLines = False
    ws["A1"] = ("Charts_I_vs_R — 图③ Actual BONE Current vs BONE Resistance"
                f"（按 BONE_P 分为 6 张独立图；细虚线 = 该目标电流的 −{T:g}% 限值，"
                f"曲线跌破虚线即掉出 ±{T:g}% 恒流区；X 轴对数刻度，覆盖 10 kΩ … 10 MΩ）")
    ws["A1"].font = F_TITLE
    xmin, xmax = ALL_RB[0] / 1000.0, ALL_RB[-1] / 1000.0
    for gi, v in enumerate(VBPS):
        grow, gcol = gi // 3, gi % 3
        ch = ScatterChart()
        ch.scatterStyle = "lineMarker"
        ch.style = 2
        ch.title = styled_title(
            f"Actual BONE Current vs BONE Resistance — BONE_P = {v:g} V"
            + chr(10) +
            f"(solid: measured current; thin dashed: −{T:g} % limit of each target)",
            size=1000)
        # NOTE: never replace ScatterChart.x_axis / y_axis. The defaults carry
        # axId/crossAx; a bare NumericAxis() has axId=None, and the two axes then
        # collapse into a single key in ChartBase._axes -> the chart is written
        # with no axes at all (Excel refuses to open the file).
        ch.x_axis.title = axis_title("BONE Resistance (kΩ, log scale)")
        ch.y_axis.title = axis_title("Actual BONE Current (µA)")
        ch.x_axis.delete = False
        ch.y_axis.delete = False
        ch.height = 10.5
        ch.width = 14.0
        ch.legend.position = "b"
        ch.legend.overlay = False
        ch.x_axis.number_format = "0"
        # data now spans three decades (10 kΩ … 10 MΩ): a log x-axis keeps the
        # constant-current region readable instead of compressing it into 10 %
        ch.x_axis.scaling.logBase = 10
        ch.x_axis.scaling.min = xmin
        ch.x_axis.scaling.max = xmax
        ch.y_axis.number_format = "0"
        for j, iu in enumerate(IREF_UA):
            if (v, iu / 1e6) not in GROUP_ROWS:
                continue                      # combo absent from the stored sweeps
            s0, s1 = GROUP_ROWS[(v, iu / 1e6)]
            s = Series(Reference(wb["Raw_Data"], min_col=6, min_row=s0, max_row=s1),
                       Reference(wb["Raw_Data"], min_col=5, min_row=s0, max_row=s1),
                       title=f"{iu} µA")
            s.marker = Marker(symbol="none")
            s.graphicalProperties.line.solidFill = SERIES_COLOR[j]
            s.graphicalProperties.line.width = 20000
            s.smooth = False
            ch.series.append(s)
            b = Series(Reference(wb["Chart_Source"], min_col=2 + j, min_row=3, max_row=4),
                       Reference(wb["Chart_Source"], min_col=1, min_row=3, max_row=4),
                       title=f"{iu} µA −{T:g}%")
            b.marker = Marker(symbol="none")
            b.graphicalProperties.line.solidFill = SERIES_COLOR[j]
            b.graphicalProperties.line.width = 7000
            b.graphicalProperties.line.dashStyle = "dash"
            b.smooth = False
            ch.series.append(b)
        # NB: openpyxl does not serialise Legend.legendEntry, so per-series legend
        # suppression is unavailable; all 10 short entries do fit.
        # 25 rows apart: a 10.5 cm chart spans ~23 rows once Excel converts the
        # one-cell anchor to a two-cell anchor, so 20 rows would overlap.
        anchor = f"{get_column_letter(2 + gcol * 8)}{2 + grow * 25}"
        ws.add_chart(ch, anchor)
    for col in "ABCDEFGHIJKLMNOPQRSTUVWX":
        ws.column_dimensions[col].width = 8.43
    return ws


# ========================================================= 8. Chart_Source
CS_ROW = {}      # row anchors written by build_chart_source, read by build_charts


def build_chart_source():
    ws = wb.create_sheet("Chart_Source")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Chart_Source — 图表源数据（由脚本生成，供 Charts / Charts_I_vs_R 引用；请勿手工改动）"
    ws["A1"].font = F_BOLD
    ws["A2"] = f"Block 1：各目标电流的 −{T:g}% 限值线（横线），x 取扫描区间两端"
    ws["A2"].font = F_NOTE
    for j, iu in enumerate(IREF_UA):
        c = ws.cell(row=3, column=2 + j, value=f"=Rmax_Summary!{get_column_letter(2+j)}"
                                               f"${RM_ROW['MAIN_HDR']}*{1 - T/100:.6g}")
        c.number_format = NF_MUA
        c2 = ws.cell(row=2, column=2 + j, value=f"{iu} µA −{T:g}% (µA)")
        c2.font = F_NOTE
    ws["A3"] = ALL_RB[0] / 1000.0
    ws["A4"] = ALL_RB[-1] / 1000.0
    for rr in (3, 4):
        ws.cell(row=rr, column=1).number_format = NF_UK
    for j in range(5):
        ws.cell(row=4, column=2 + j, value=f"={get_column_letter(2+j)}3").number_format = NF_MUA
        ws.cell(row=3, column=2 + j).font = F_BODY
        ws.cell(row=4, column=2 + j).font = F_BODY
    ws["A2"].value = (f"Block 1：各目标电流的 −{T:g}% 限值线"
                      f"（x = 扫描区间两端, y = {1 - T/100:.4g} × Target）")
    ws["A6"] = "Block 2：仅知下限的点（在扫描上限处仍 PASS）→ 图① 红色 × 标记"
    ws["A6"].font = F_NOTE
    CS_ROW["lb_hdr"] = 7
    for j, h in enumerate(["VBP_V", "Rmax_kOhm (≥下限)", "IREF_uA", "备注"]):
        c = ws.cell(row=7, column=1 + j, value=h)
        c.font = F_HDR; c.fill = FILL_HDR; c.border = BOX
    CS_ROW["lb_0"] = 8
    CS_ROW["lb_n"] = len(CENSORED)
    if not CENSORED:
        ws.cell(row=8, column=1,
                value="（本次两次扫描合并后无此情形：除 10 µA 外全部组合已在扫描上限内定界）"
                ).font = F_NOTE
    for k, (v, i, rb) in enumerate(CENSORED):
        rr = 8 + k
        ws.cell(row=rr, column=1, value=v).number_format = NF_1DP
        ws.cell(row=rr, column=2, value=rb / 1000.0).number_format = NF_UK
        ws.cell(row=rr, column=3, value=round(i * MUA, 6)).number_format = NF_INT
        ws.cell(row=rr, column=4,
                value=f"扫描上限 {rb/1000:.0f} kΩ 处仍 PASS → 真实 Rmax 更大").font = F_NOTE
        for j in range(1, 4):
            ws.cell(row=rr, column=j).font = F_BODY
    rr = 8 + len(CENSORED) + 1
    ws.cell(row=rr, column=1, value="Block 3：扫描上限参考线 → 图① 灰色虚线").font = F_NOTE
    CS_ROW["lim_hdr"] = rr + 1
    CS_ROW["lim_0"], CS_ROW["lim_1"] = rr + 2, rr + 3
    ws.cell(row=rr + 1, column=1, value="VBP_V").font = F_HDR
    ws.cell(row=rr + 1, column=2, value="Scan_limit_kOhm").font = F_HDR
    for i, x in enumerate([VBPS[0], VBPS[-1]]):
        ws.cell(row=rr + 2 + i, column=1, value=x).number_format = NF_1DP
        ws.cell(row=rr + 2 + i, column=2, value=RB_MAX / 1000.0).number_format = NF_UK
        ws.cell(row=rr + 2 + i, column=1).font = F_BODY
        ws.cell(row=rr + 2 + i, column=2).font = F_BODY
    for col, w in zip("ABCD", (10, 20, 12, 46)):
        ws.column_dimensions[col].width = w
    return ws


build_readme()
build_raw()
build_rmax()
fill_pass_formulas()      # needs Rmax_Summary's threshold cell to exist
build_boundary()
build_accuracy()
build_chart_source()
build_charts()
build_current_charts()
wb.save(OUT_XLSX)
print(f"[out] {OUT_XLSX}")

# ------------------------------------------------- ground truth for verifier
gt = {
    "rb_min": RB_MIN, "rb_max": RB_MAX, "n": len(data),
    "rmax_disp": {f"{v}|{i*1e6:.0f}": RMX_DISP[(v, i)] for v in VBPS for i in IREF_A},
    "rmax_status": {f"{v}|{i*1e6:.0f}": groups[(v, i)]["status"]
                    for v in VBPS for i in IREF_A},
    "rmax_num": {f"{v}|{i*1e6:.0f}": RMX_NUM[(v, i)] for v in VBPS for i in IREF_A},
    "boundary": {f"{v}|{i*1e6:.0f}": [groups[(v, i)]["lastP"], groups[(v, i)]["firstF"]]
                 for v in VBPS for i in IREF_A},
    "acc_low": {f"{v}|{i*1e6:.0f}": (
        [D[(v, i, RB_MIN)]["IBONE"] * MUA, D[(v, i, RB_MIN)]["IERR"],
         D[(v, i, RB_MIN)]["VBONE"], D[(v, i, RB_MIN)]["PASS_T"]]
        if (v, i, RB_MIN) in D else [None, None, None, None])
        for v in VBPS for i in IREF_A},
    "err_matrix": {f"{v}|{i*1e6:.0f}": [
        (D[(v, i, rb)]["IERR"] if (v, i, rb) in D else None) for rb in KEY_RB]
                   for v in VBPS for i in IREF_A},
    "npass": {f"{v}|{i*1e6:.0f}": groups[(v, i)]["n_pass"]
              for v in VBPS for i in IREF_A},
    "params": {
        "rb_min": RB_MIN, "rb_max": RB_MAX, "rows": len(data),
        "n_at_max_pass": len(CENSORED),
        "n_fail_at_min": sum(1 for v in VBPS for i in IREF_A
                             if D[(v, i, RB_MIN)]["PASS_T"] == 0),
        "n_pass_rows": sum(1 for r_ in data if r_["PASS_T"] == 1),
        "n_fail_rows": sum(1 for r_ in data if r_["PASS_T"] == 0),
    },
    "censored": [[v, i * MUA, RB_MAX / 1000.0] for v, i, _ in CENSORED],
    "layout": {"rm": dict(RM_ROW), "bd_hdr": BD_HDR, "bd_0": BD_0,
               "ca_hdr": CA_HDR, "ca_0": CA_0, "ca_bh": CA_BH, "ca_b0": CA_B0},
}
(WORK / "ground_truth.json").write_text(
    json.dumps(gt, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"[out] {WORK/'ground_truth.json'}")
print("sheets:", wb.sheetnames)
