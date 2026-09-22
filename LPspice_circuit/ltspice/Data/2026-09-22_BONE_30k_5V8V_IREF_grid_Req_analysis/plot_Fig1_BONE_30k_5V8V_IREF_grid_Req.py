"""Figure 1 — fixed 30 kOhm bone load: the (bus x setpoint) grid across the compliance edge.

FIGURE CONTRACT (nature-figure skill, backend = Python/matplotlib, exclusive)
--------------------------------------------------------------------------
1. Core conclusion (one sentence)
   Tripling the fixed bone load from 10 to 30 kOhm leaves the VBUS-port equivalent
   load bit-identical in 9 of 10 combinations - the port load is set by bus voltage
   and setpoint alone - and the single exception is 5 V / 200 uA, whose measured
   compliance limit sits at 21-24 kOhm: there the bone current collapses from the
   200 uA setpoint to 158.7 uA (the ohmic limit 4.9991 V/(30+1.5) kOhm) and the port
   load rises from the predicted 19.2 to 22.8 kOhm, i.e. the load gets lighter.

   Results-level question: with a 30 kOhm bone, which (bus, setpoint) combinations
   still hold their setpoint, and what does crossing that edge do to the equivalent
   load?

2. Evidence chain (one distinct inferential role per panel)
   a  Req vs I_set on both rails     the answer, with the 5 V/200 uA point visibly off
                                     its analytic line
   b  parity Req(30 kOhm) vs Req(10 kOhm)  invariance evidence: nine points on the
                                     identity line, one outlier
   c  the 30 kOhm load against the measured compliance limits  boundary map: which
                                     setpoints still tolerate a 30 kOhm bone
   d  delivered bone current vs setpoint   the dose consequence of crossing the edge

3. Archetype: quantitative grid (2 x 2, equal spans), hero panel = a.

4. Backend: Python / matplotlib only.

5. Export contract
   Final size 183 mm x 118 mm (fixed margins, no tight cropping). Base 7 pt, ticks
   6.5 pt, panel labels 8 pt bold lowercase; no glyph below 5 pt. Editable text.
   Exports: PNG 600 dpi + PDF + SVG + TIFF.
   Source data: ../data/BONE_30k_5V8V_IREF_grid.csv plus the 10 kOhm run for the parity
   panel; all 14 points of this run are plotted, none excluded.
   Statistics: deterministic LTspice runs (n = 14 here, 27-30 ms average of a 30 ms
   .tran with startup); no statistical test applies.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.transforms import ScaledTranslation

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "Microsoft YaHei", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["font.family"] = ["Arial", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams.update({
    'svg.fonttype': 'none', 'pdf.fonttype': 42,
    "font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
    "axes.spines.right": False, "axes.spines.top": False, "axes.linewidth": 0.8,
    "xtick.direction": "out", "ytick.direction": "out",
    "xtick.major.width": 0.8, "ytick.major.width": 0.8,
    "xtick.major.size": 2.2, "ytick.major.size": 2.2,
    "legend.frameon": False, "lines.linewidth": 1.0,
})

RAIL = {8: "#0F4D92", 5: "#42949E"}
NEUTRAL = "#767676"
R_FIXED = 30.0
I_OFFSET = 0.218
V_HEAD = 0.345
VBP = {8: 8.0016, 5: 4.9991}
RUN = Path(__file__).resolve().parent
DATA = RUN / "data" / "BONE_30k_5V8V_IREF_grid.csv"
OLD10 = RUN.parent / "2026-09-22_BONE_10k_5V8V_IREF_grid_Req_analysis" / "data" / "BONE_10k_5V8V_IREF_grid.csv"
CHARTS, QA = RUN / "charts", RUN / "charts" / "qa"
STEM = CHARTS / "Fig1_BONE_30k_5V8V_IREF_grid_Req"
MM = 1 / 25.4
FIG_WIDTH_MM = 183.0   # Nature double column
FIG_HEIGHT_MM = 118.0
SETS = [10, 20, 50, 100, 200]


def load():
    with open(DATA, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["ibone"] = float(r["I_bone_A"]) * 1e6
        r["ibus"] = float(r["I_bus_A"]) * 1e6
        r["rb"] = float(r["R_bone_Ohm"]) / 1e3
        r["req"] = float(r["Req_vbus_Ohm"]) / 1e3
        r["iref"] = float(r["IREF_uA"])
        r["vb"] = float(r["V_bus_V"])
        r["reg"] = r["state"] == "regulating"
    with open(OLD10, encoding="utf-8") as fh:
        old = {(float(r["V_bus_V"]), float(r["IREF_uA"])): float(r["Req_vbus_Ohm"]) / 1e3
               for r in csv.DictReader(fh) if r["kind"] == "fixed"}
    return rows, [r for r in rows if r["kind"] == "fixed"], old


def panel_label(ax, label, x_offset_pt=-30, y_offset_pt=3):
    off = ScaledTranslation(x_offset_pt / 72, y_offset_pt / 72, ax.figure.dpi_scale_trans)
    ax.text(0, 1, label, transform=ax.transAxes + off, fontsize=8, fontweight="bold",
            ha="left", va="bottom")


NOTES = []


def note(ax, x, y, s, **kw):
    t = ax.text(x, y, s, **kw)
    NOTES.append((ax, t, s))
    return t


def check_notes_inside_axes(fig, tol_pt=0.5):
    fig.canvas.draw()
    bad = []
    for ax, t, s in NOTES:
        tb = t.get_window_extent(fig.canvas.get_renderer())
        ab = ax.get_window_extent(fig.canvas.get_renderer())
        slack = tol_pt * fig.dpi / 72.0
        if (tb.x0 < ab.x0 - slack or tb.x1 > ab.x1 + slack
                or tb.y0 < ab.y0 - slack or tb.y1 > ab.y1 + slack):
            bad.append(f"{s!r}")
    if bad:
        raise AssertionError("annotation(s) outside their axes: " + "; ".join(bad))


def logx(ax, ylim, yticks):
    ax.set_xscale("log"); ax.set_xlim(7, 320)
    ax.set_xticks(SETS); ax.set_xticklabels([str(s) for s in SETS])
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.tick_params(axis="x", which="minor", length=1.2)
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks); ax.set_yticklabels([f"{t:g}" for t in yticks])
    ax.set_xlabel("设定电流 I_set (µA)")


def main():
    rows, main, old = load()
    # every log axis in this figure needs strictly positive values
    assert np.all(np.array([r["rb"] for r in rows]) > 0)
    assert np.all(np.array([r["iref"] for r in rows]) > 0)
    ii = np.logspace(np.log10(8), np.log10(300), 120)
    fig, axes = plt.subplots(2, 2, figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    fig.subplots_adjust(left=0.085, right=0.985, top=0.952, bottom=0.195,
                        wspace=0.42, hspace=0.26)
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    def markers(ax, xs, ys, col, reg, **kw):
        """filled = regulating, open = out of compliance (convention stated in footnote)"""
        for x, y, ok in zip(xs, ys, reg):
            ax.plot(x, y, "o", ms=3.4, mfc=col if ok else "white", mec=col, mew=0.6,
                    zorder=3, clip_on=False, **kw)

    # ---- a: port load on the grid ------------------------------------------
    for vb in (8, 5):
        col = RAIL[vb]
        pts = sorted([r for r in main if r["vb"] == vb], key=lambda r: r["iref"])
        ax_a.plot(ii, vb * 1e3 / (ii - I_OFFSET + (65.02 if vb == 8 else 60.52)),
                  color=col, lw=0.8, zorder=2)
        markers(ax_a, [r["iref"] for r in pts], [r["req"] for r in pts], col,
                [r["reg"] for r in pts])
    ax_a.set_yscale("log"); logx(ax_a, (15, 135), [20, 30, 50, 70, 100])
    ax_a.yaxis.set_minor_formatter(plt.NullFormatter())
    ax_a.tick_params(axis="y", which="minor", length=1.2)
    ax_a.set_ylabel("VBUS 等效负载 Req (kΩ)")
    note(ax_a, 11, 118, "8 V 母线", fontsize=6.5, color=RAIL[8], va="bottom")
    note(ax_a, 11, 45, "5 V 母线", fontsize=6.5, color=RAIL[5], va="top")
    panel_label(ax_a, "a")

    # ---- b: parity against the 10 kOhm run ---------------------------------
    ax_b.plot([16, 130], [16, 130], color=NEUTRAL, lw=0.8, ls=(0, (4, 2)), zorder=1)
    for vb in (8, 5):
        pts = sorted([r for r in main if r["vb"] == vb], key=lambda r: r["iref"])
        markers(ax_b, [old[(vb, r["iref"])] for r in pts], [r["req"] for r in pts],
                RAIL[vb], [r["reg"] for r in pts])
    ax_b.set_xscale("log"); ax_b.set_yscale("log")
    ax_b.set_xlim(16, 130); ax_b.set_ylim(16, 130)
    for axis in (ax_b.xaxis, ax_b.yaxis):
        axis.set_major_locator(matplotlib.ticker.FixedLocator([20, 30, 50, 70, 100]))
        axis.set_major_formatter(matplotlib.ticker.FixedFormatter(["20", "30", "50", "70", "100"]))
        axis.set_minor_formatter(plt.NullFormatter())
    ax_b.tick_params(which="minor", length=1.2)
    ax_b.set_xlabel("10 kΩ 组的 Req (kΩ)")
    ax_b.set_ylabel("30 kΩ 组的 Req (kΩ)")
    note(ax_b, 18, 90, "y = x：两组一致", fontsize=6, color=NEUTRAL, va="bottom")
    panel_label(ax_b, "b")

    # ---- c: boundary map ---------------------------------------------------
    for vb in (8, 5):
        ax_c.plot(ii, (VBP[vb] - V_HEAD) * 1e3 / ii, color=RAIL[vb], lw=0.8, zorder=2)
    ax_c.axhline(R_FIXED, color=NEUTRAL, lw=0.8, ls=(0, (4, 2)), zorder=1)
    for vb in (8, 5):
        pts = sorted([r for r in main if r["vb"] == vb], key=lambda r: r["iref"])
        markers(ax_c, [r["iref"] for r in pts], [(VBP[vb] - V_HEAD) * 1e3 / r["iref"] for r in pts],
                RAIL[vb], [r["reg"] for r in pts])
    ax_c.set_yscale("log"); logx(ax_c, (15, 1400), [30, 100, 300, 1000])
    ax_c.yaxis.set_minor_formatter(plt.NullFormatter())
    ax_c.tick_params(axis="y", which="minor", length=1.2)
    ax_c.set_ylabel("实测顺从上限 R_max (kΩ)")
    note(ax_c, 8, 34, "固定骨阻 30 kΩ", fontsize=6, color=NEUTRAL, va="bottom")
    note(ax_c, 11, 120, "8 V 母线", fontsize=6.5, color=RAIL[8], va="bottom")
    note(ax_c, 11, 60, "5 V 母线", fontsize=6.5, color=RAIL[5], va="top")
    panel_label(ax_c, "c")

    # ---- d: delivered current ---------------------------------------------
    ax_d.plot(ii, ii - I_OFFSET, color=NEUTRAL, lw=0.8, ls=(0, (4, 2)), zorder=1)
    for vb in (8, 5):
        pts = sorted([r for r in main if r["vb"] == vb], key=lambda r: r["iref"])
        markers(ax_d, [r["iref"] for r in pts], [r["ibone"] for r in pts], RAIL[vb],
                [r["reg"] for r in pts])
    ax_d.set_xscale("log")
    ax_d.set_xlim(7, 320); ax_d.set_ylim(0, 275)
    ax_d.set_xticks(SETS); ax_d.set_xticklabels([str(s) for s in SETS])
    ax_d.xaxis.set_minor_formatter(plt.NullFormatter())
    ax_d.tick_params(axis="x", which="minor", length=1.2)
    ax_d.set_xlabel("设定电流 I_set (µA)")
    ax_d.set_ylabel("实际骨电流 I_bone (µA)")
    note(ax_d, 8, 230, "设定值 − 0.22 µA", fontsize=6, color=NEUTRAL, va="bottom")
    panel_label(ax_d, "d")

    fig.text(0.005, 0.085, f"数据：LTspice 26 稳态；骨负载固定为理想电阻 {R_FIXED:.0f} kΩ；"
                           "设定值由 R10 = 0.3 V/I_set 设定；n = 14 个工作点（10 主点 + 4 个边界细化点）。",
             fontsize=6, color=NEUTRAL, ha="left", va="bottom")
    fig.text(0.005, 0.053, "空心标记 = 越限（环路饱和）；a/d 细虚线 = 解析式（含 −0.218 µA 的 R9 误差）；"
                           "b 的横轴取自 10 kΩ 那组运行；c 的竖线为 0.345 V 漏极余量的解析极限。",
             fontsize=6, color=NEUTRAL, ha="left", va="bottom")
    fig.text(0.005, 0.021, "确定性仿真，无统计检验；d 中唯一的空芯点即 5 V / 200 µA：30 kΩ 超过该档 21–24 kΩ 的上限，"
                           "骨流塌到 158.7 µA。",
             fontsize=6, color=NEUTRAL, ha="left", va="bottom")
    return fig


if __name__ == "__main__":
    CHARTS.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    fig = main()
    check_notes_inside_axes(fig)
    from audit_panel_alignment import require_matplotlib_panel_alignment
    require_matplotlib_panel_alignment(
        fig, axes=fig.axes, panel_ids=["a", "b", "c", "d"],
        row_groups=[["a", "b"], ["c", "d"]], column_groups=[["a", "c"], ["b", "d"]],
        json_out=str(QA / "Fig1.alignment.json"), overlay_svg=str(QA / "Fig1.alignment.svg"),
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True)
    fig.savefig(f"{STEM}.png", dpi=600)
    fig.savefig(f"{STEM}.pdf")
    fig.savefig(f"{STEM}.svg")
    fig.savefig(f"{STEM}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)
    print("saved", STEM)
