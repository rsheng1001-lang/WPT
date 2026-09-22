"""Figure 1 — VBUS equivalent load on a (bus voltage x setpoint) grid at a fixed 10 kOhm bone load.

FIGURE CONTRACT (nature-figure skill, backend = Python/matplotlib, exclusive)
--------------------------------------------------------------------------
1. Core conclusion (one sentence)
   With the bone load fixed at 10 kOhm - comfortably inside the regulating band of
   every combination - the VBUS-port equivalent load is set by the bus voltage and
   the setpoint alone: Req = V_BUS/(I_set - 0.218 uA + bias) falls from 106.9 to
   30.2 kOhm on the 8 V rail and from 71.1 to 19.2 kOhm on the 5 V rail, and the
   8 V rail is always ~1.6x higher because the same current is drawn at a higher
   voltage; the fixed bias (65.0 uA at 8 V, 60.5 uA at 5 V) keeps the useful share
   of the bus current between 13% and 77%, and the smallest compliance margin of
   the whole grid is 2.1x (5 V / 200 uA).

   Results-level question: on a 5 V / 8 V bus, what equivalent load does the supply
   see for each setpoint when the bone impedance is a fixed 10 kOhm, and how much
   margin does that choice leave?

2. Evidence chain (one distinct inferential role per panel)
   a  Req vs I_set, both rails        the answer: the port load on the grid, against
                                      the analytic V/(I+bias) lines
   b  bus-current split, stacked      mechanism: how much of the drawn current is
                                      useful bone current vs circuit bias
   c  measured compliance bracket     robustness: where each combination collapses,
                                      against the fixed 10 kOhm load
   d  dissipation split               consequence: bone dissipation depends only on
                                      the setpoint, MOSFET dissipation on the rail

3. Archetype: quantitative grid (2 x 2, equal spans), hero panel = a.

4. Backend: Python / matplotlib only.

5. Export contract
   Final size 183 mm x 118 mm (fixed margins, no tight cropping). Base 7 pt, ticks
   6.5 pt, panel labels 8 pt bold lowercase; no glyph below 5 pt. Editable text
   (pdf.fonttype 42, svg.fonttype none). Exports: PNG 600 dpi + PDF + SVG + TIFF.
   Source data: ../data/BONE_10k_5V8V_IREF_grid.csv — all 30 operating points
   (10 fixed-load + 20 knee-bracket points) are plotted; none excluded.
   Statistics: deterministic LTspice runs (n = 30 steady-state operating points,
   27-30 ms average of a 30 ms .tran with startup); no statistical test applies.
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
    'svg.fonttype': 'none',
    'pdf.fonttype': 42,
    "font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
    "axes.spines.right": False, "axes.spines.top": False, "axes.linewidth": 0.8,
    "xtick.direction": "out", "ytick.direction": "out",
    "xtick.major.width": 0.8, "ytick.major.width": 0.8,
    "xtick.major.size": 2.2, "ytick.major.size": 2.2,
    "legend.frameon": False, "lines.linewidth": 1.0,
})

RAIL = {8: "#0F4D92", 5: "#42949E"}      # categorical: the two bus voltages
NEUTRAL = "#767676"
R_FIXED = 10.0                            # kOhm, the fixed bone load of this study
I_OFFSET = 0.218                          # uA lost to R9 before reaching the bone
RUN = Path(__file__).resolve().parent
DATA = RUN / "data" / "BONE_10k_5V8V_IREF_grid.csv"
CHARTS, QA = RUN / "charts", RUN / "charts" / "qa"
STEM = CHARTS / "Fig1_BONE_10k_5V8V_IREF_grid_Req"
MM = 1 / 25.4
FIG_WIDTH_MM, FIG_HEIGHT_MM = 183.0, 118.0
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
        r["pb"] = float(r["P_bone_W"]) * 1e6
        r["pf"] = float(r["P_fet_W"]) * 1e6
        r["reg"] = r["state"] == "regulating"
    main = [r for r in rows if r["kind"] == "fixed"]
    bias = {vb: np.mean([r["ibus"] - r["ibone"] for r in main if r["vb"] == vb]) for vb in RAIL}
    return rows, main, bias


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
            bad.append(f"{s!r} bbox=({tb.x0:.0f},{tb.y0:.0f})-({tb.x1:.0f},{tb.y1:.0f})")
    if bad:
        raise AssertionError("annotation(s) outside their axes:\n  " + "\n  ".join(bad))


def main():
    rows, main, bias = load()
    ii = np.logspace(np.log10(8), np.log10(300), 120)

    fig, axes = plt.subplots(2, 2, figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    fig.subplots_adjust(left=0.085, right=0.985, top=0.952, bottom=0.195,
                        wspace=0.42, hspace=0.26)
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    # ---- a: the port load on the grid --------------------------------------
    for vb in (8, 5):
        col = RAIL[vb]
        pts = sorted([r for r in main if r["vb"] == vb], key=lambda r: r["iref"])
        x = [r["iref"] for r in pts]; y = [r["req"] for r in pts]
        ax_a.plot(ii, vb * 1e3 / (ii - I_OFFSET + bias[vb]), color=col, lw=0.8, zorder=2)
        ax_a.plot(x, y, "o", ms=3.4, mfc=col, mec=col, mew=0.5, zorder=3, clip_on=False)
    ax_a.set_xscale("log"); ax_a.set_yscale("log")
    ax_a.set_xlim(7, 320); ax_a.set_ylim(15, 135)
    ax_a.set_xticks(SETS); ax_a.set_xticklabels([str(s) for s in SETS])
    ax_a.xaxis.set_minor_formatter(plt.NullFormatter())
    ax_a.tick_params(axis="x", which="minor", length=1.2)
    ax_a.set_yticks([20, 30, 50, 70, 100]); ax_a.set_yticklabels(["20", "30", "50", "70", "100"])
    ax_a.yaxis.set_minor_formatter(plt.NullFormatter())
    ax_a.tick_params(axis="y", which="minor", length=1.2)
    ax_a.set_xlabel("设定电流 I_set (µA)")
    ax_a.set_ylabel("VBUS 等效负载 Req (kΩ)")
    note(ax_a, 11, 118, "8 V 母线", fontsize=6.5, color=RAIL[8], va="bottom")
    note(ax_a, 11, 45, "5 V 母线", fontsize=6.5, color=RAIL[5], va="top")
    panel_label(ax_a, "a")

    # ---- b: bus current split ---------------------------------------------
    w, xs = 0.46, np.arange(len(SETS))
    bone = {}
    for k, vb in enumerate((8, 5)):
        bone[vb] = [next(r["ibone"] for r in main if r["vb"] == vb and r["iref"] == s) for s in SETS]
        off = (k - 0.5) * w
        ax_b.bar(xs + off, bone[vb], width=w, color=RAIL[vb], edgecolor="white", linewidth=0.5,
                 zorder=3)
        ax_b.bar(xs + off, [bias[vb]] * len(SETS), width=w, bottom=bone[vb], color="#D9D9D9",
                 edgecolor="white", linewidth=0.5, zorder=3)
    # one share label per setpoint (two per group would merge into one audit trace)
    for j in range(len(SETS)):
        tot = bone[8][j] + bias[8]
        ax_b.text(xs[j], tot + 8, f"{bone[8][j] / tot * 100:.0f}%", fontsize=5.4, color=RAIL[8],
                  ha="center", va="bottom")
    ax_b.set_xticks(xs); ax_b.set_xticklabels([str(s) for s in SETS])
    ax_b.set_xlim(-0.6, len(SETS) - 0.4); ax_b.set_ylim(0, 330)
    ax_b.set_xlabel("设定电流 I_set (µA)")
    ax_b.set_ylabel("母线电流构成 (µA)")
    ax_b.text(0.99, 0.97, "实心 = 骨电流，灰 = 电路偏置（8 V: 65.0 µA，5 V: 60.5 µA）",
              transform=ax_b.transAxes, fontsize=6, color=NEUTRAL, ha="right", va="top")
    panel_label(ax_b, "b")

    # ---- c: measured compliance bracket ------------------------------------
    for vb in (8, 5):
        col = RAIL[vb]
        lo, hi = [], []
        for s in SETS:
            b = sorted([r for r in rows if r["vb"] == vb and r["iref"] == s and r["kind"] != "fixed"],
                       key=lambda r: r["rb"])
            lo.append(b[0]["rb"]); hi.append(b[1]["rb"])
        ax_c.plot(SETS, lo, "-o", color=col, ms=3.4, mew=0.5, lw=0.8, zorder=3, clip_on=False)
        for x, a, b_ in zip(SETS, lo, hi):
            ax_c.plot([x, x], [a, b_], color=col, lw=1.6, alpha=0.35, zorder=2,
                      solid_capstyle="butt")
    ax_c.axhline(R_FIXED, color=NEUTRAL, lw=0.8, ls=(0, (4, 2)), zorder=1)
    ax_c.set_xscale("log"); ax_c.set_yscale("log")
    ax_c.set_xlim(7, 320); ax_c.set_ylim(8, 1400)
    ax_c.set_xticks(SETS); ax_c.set_xticklabels([str(s) for s in SETS])
    ax_c.xaxis.set_minor_formatter(plt.NullFormatter())
    ax_c.tick_params(axis="x", which="minor", length=1.2)
    ax_c.set_yticks([10, 30, 100, 300, 1000]); ax_c.set_yticklabels(["10", "30", "100", "300", "1000"])
    ax_c.yaxis.set_minor_formatter(plt.NullFormatter())
    ax_c.tick_params(axis="y", which="minor", length=1.2)
    ax_c.set_xlabel("设定电流 I_set (µA)")
    ax_c.set_ylabel("顺从上限 R_max (kΩ)")
    note(ax_c, 11, 12, "固定骨阻 10 kΩ", fontsize=6, color=NEUTRAL, va="bottom")
    note(ax_c, 11, 70, "8 V 母线", fontsize=6.5, color=RAIL[8], va="bottom")
    note(ax_c, 11, 33, "5 V 母线", fontsize=6.5, color=RAIL[5], va="top")
    note(ax_c, 95, 950, "余量最小 2.1×\n（5 V / 200 µA）", fontsize=6, color=NEUTRAL, va="center")
    panel_label(ax_c, "c")

    # ---- d: dissipation split ---------------------------------------------
    pb = [next(r["pb"] for r in main if r["vb"] == 8 and r["iref"] == s) for s in SETS]
    ax_d.plot(SETS, pb, "-o", color=NEUTRAL, ms=3.4, mew=0.5, lw=0.8, zorder=3, clip_on=False)
    for vb in (8, 5):
        pf = [next(r["pf"] for r in main if r["vb"] == vb and r["iref"] == s) for s in SETS]
        ax_d.plot(SETS, pf, "-o", color=RAIL[vb], ms=3.4, mew=0.5, lw=0.8, zorder=3, clip_on=False)
    ax_d.set_xscale("log")
    ax_d.set_xlim(7, 320); ax_d.set_ylim(0, 1650)
    ax_d.set_xticks(SETS); ax_d.set_xticklabels([str(s) for s in SETS])
    ax_d.xaxis.set_minor_formatter(plt.NullFormatter())
    ax_d.tick_params(axis="x", which="minor", length=1.2)
    ax_d.set_xlabel("设定电流 I_set (µA)")
    ax_d.set_ylabel("耗散功率 (µW)")
    handles = [plt.Line2D([], [], color=NEUTRAL, marker="o", ms=3.4, lw=0.8,
                          label="骨负载 P_bone（两组母线相同）"),
               plt.Line2D([], [], color=RAIL[5], marker="o", ms=3.4, lw=0.8,
                          label="MOSFET P_FET，5 V 母线"),
               plt.Line2D([], [], color=RAIL[8], marker="o", ms=3.4, lw=0.8,
                          label="MOSFET P_FET，8 V 母线")]
    ax_d.legend(handles=handles, loc="upper left", fontsize=5.8, handlelength=1.6,
                labelspacing=0.3, borderpad=0.3)
    panel_label(ax_d, "d")

    fig.text(0.005, 0.085, f"数据：LTspice 26 稳态；骨负载固定为理想电阻 {R_FIXED:.0f} kΩ；设定值由 R10 = 0.3 V/I_set 设定。",
             fontsize=6, color=NEUTRAL, ha="left", va="bottom")
    fig.text(0.005, 0.053, f"n = {len(rows)} 个工作点（10 主点 + 每组合 2 个拐点校核点，全部绘出）；确定性仿真，无统计检验；b 中占比按 8 V 母线标注。",
             fontsize=6, color=NEUTRAL, ha="left", va="bottom")
    fig.text(0.005, 0.021, "参考线：a 中细线 = V_BUS/(I_set − 0.218 µA + 偏置)；c 中竖条 = 实测拐点区间（下界恒流、上界已越限）。",
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
