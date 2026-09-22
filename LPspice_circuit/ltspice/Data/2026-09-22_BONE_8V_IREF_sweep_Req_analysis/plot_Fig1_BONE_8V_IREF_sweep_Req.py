"""Figure 1 — how the setpoint current changes the VBUS-port equivalent load.

FIGURE CONTRACT (nature-figure skill, backend = Python/matplotlib, exclusive)
--------------------------------------------------------------------------
1. Core conclusion (one sentence)
   At a fixed 8 V bus the VBUS-port equivalent load falls from 107.0 kOhm to
   30.2 kOhm as the setpoint is raised 10 -> 200 uA, but it is NOT inversely
   proportional to the setpoint: the circuit draws a setpoint-independent 65.0 uA
   bias, so at 10 uA only 13% of the bus current reaches the bone and the port
   load can never exceed V_BUS/65 uA = 123 kOhm; conversely the compliance limit
   scales exactly as 1/I_set (766 -> 38 kOhm), so a lower setpoint buys drive
   capability at the cost of current accuracy (-2.16% at 10 uA, from the fixed
   0.22 uA R9 error).

   Results-level question: what does the choice of setpoint current do to the
   equivalent load the supply sees, and to where the current source gives up?

2. Evidence chain (one distinct inferential role per panel)
   a  I_bone vs R_BONE, five setpoints   dose levels and where each stops regulating
   b  Req_VBUS vs R_BONE, five setpoints the port load per setpoint: plateaus and the
                                         post-knee rise (the direct answer)
   c  plateau Req vs I_set               mechanism: measured points against the ideal
                                         V/I line and the 65 uA bias floor
   d  compliance limit vs I_set          consequence: R_max * I_set is a constant
                                         7.6 V, i.e. drive capability trades 1:1
                                         against setpoint
   Panels a and b share the colour-to-setpoint mapping and the log bone axis;
   c and d share the log setpoint axis.

3. Archetype: quantitative grid (2 x 2, equal spans), hero panel = b (the answer).

4. Backend: Python / matplotlib only.

5. Export contract
   Final size 183 mm x 118 mm (fixed margins, no tight cropping). Base 7 pt, ticks
   6.5 pt, panel labels 8 pt bold lowercase; no rendered glyph below 5 pt. Editable
   text (pdf.fonttype 42, svg.fonttype none). Exports: PNG 600 dpi + PDF + SVG + TIFF.
   Source data: ../data/BONE_8V_IREF_sweep.csv — all 45 swept operating points
   (5 setpoints x 9 bone resistances) are plotted; none excluded.
   Statistics: deterministic LTspice runs (n = 45 steady-state operating points,
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

# ---- mandatory editable-text configuration (skill rule) -----------------------
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "Microsoft YaHei", "DejaVu Sans", "Liberation Sans"]
# Glyph-level fallback only engages through the font.family *list* (matplotlib >= 3.6):
# Latin/Greek resolve to Arial, the Chinese labels fall back to Microsoft YaHei.
plt.rcParams["font.family"] = ["Arial", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams.update({
    'svg.fonttype': 'none',
    'pdf.fonttype': 42,
    "font.size": 7,
    "axes.labelsize": 7,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "xtick.major.size": 2.2,
    "ytick.major.size": 2.2,
    "legend.frameon": False,
    "lines.linewidth": 1.0,
})

# sequential blue family, light -> dark as the setpoint rises (ordered parameter)
SERIES = {10: "#9ECAE1", 20: "#6BAED6", 50: "#3775BA", 100: "#0F4D92", 200: "#08306B"}
NEUTRAL = "#767676"
V_BUS = 8.0
V_BONE_P = 8.0016
V_HEAD = 0.345          # drain-node floor: I*R10 (0.30 V) + residual Vds

RUN = Path(__file__).resolve().parent
DATA = RUN / "data" / "BONE_8V_IREF_sweep.csv"
CHARTS = RUN / "charts"
QA = CHARTS / "qa"
STEM = CHARTS / "Fig1_BONE_8V_IREF_sweep_Req"

MM = 1 / 25.4
FIG_WIDTH_MM = 183.0
FIG_HEIGHT_MM = 118.0


def load():
    with open(DATA, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    d = {"iref": np.array([float(r["IREF_uA"]) for r in rows])}
    for k, col, scale in (("r", "R_bone_Ohm", 1e-3), ("ib", "I_bone_A", 1e6),
                          ("req", "Req_vbus_Ohm", 1e-3), ("ibus", "I_bus_A", 1e6),
                          ("pb", "P_bone_W", 1e6), ("pf", "P_fet_W", 1e6)):
        d[k] = np.array([float(r[col]) for r in rows]) * scale
    d["reg"] = np.array([r["state"] == "regulating" for r in rows])
    d["sets"] = sorted(set(d["iref"]))
    return d


def panel_label(ax, label, x_offset_pt=-30, y_offset_pt=3):
    off = ScaledTranslation(x_offset_pt / 72, y_offset_pt / 72, ax.figure.dpi_scale_trans)
    ax.text(0, 1, label, transform=ax.transAxes + off, fontsize=8,
            fontweight="bold", ha="left", va="bottom")


NOTES: list[tuple] = []


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
            bad.append(f"{s!r} bbox=({tb.x0:.0f},{tb.y0:.0f})-({tb.x1:.0f},{tb.y1:.0f})"
                       f" axes=({ab.x0:.0f},{ab.y0:.0f})-({ab.x1:.0f},{ab.y1:.0f})")
    if bad:
        raise AssertionError("annotation(s) outside their axes:\n  " + "\n  ".join(bad))


def main():
    d = load()
    assert np.all(d["r"] > 0), "log axis requires strictly positive bone resistance"
    # per-setpoint summary: plateau values and the last regulating resistance
    sums = {}
    for s in d["sets"]:
        m = d["iref"] == s
        reg = m & d["reg"]
        sums[s] = {
            "ib": d["ib"][reg].mean(), "req": d["req"][reg].mean(),
            "rmax": d["r"][reg].max(), "rmax_next": d["r"][m & ~d["reg"]].min(),
            "ib_plateau": d["ib"][reg].mean(),
        }
        # V_BUS[kV per kOhm] -> mA -> uA, then subtract the bone current in uA
        sums[s]["bias"] = V_BUS / sums[s]["req"] * 1e3 - sums[s]["ib"]
    bias = np.mean([sums[s]["bias"] for s in d["sets"]])
    req_floor = V_BUS / bias * 1e3                 # kOhm, as I_set -> 0

    fig, axes = plt.subplots(2, 2, figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    fig.subplots_adjust(left=0.085, right=0.985, top=0.952, bottom=0.195,
                        wspace=0.42, hspace=0.26)
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    # ---- a / b: sweep curves per setpoint -----------------------------------
    for ax in (ax_a, ax_b):
        ax.set_xscale("log")
        ax.set_xlim(0.42, 2500)
        ax.set_xticks([1, 10, 100, 1000])
        ax.set_xticklabels(["1", "10", "100", "1000"])
        ax.xaxis.set_minor_formatter(plt.NullFormatter())
        ax.tick_params(axis="x", which="minor", length=1.2)
        # shared log axis: the top row carries neither tick labels nor an xlabel
        ax.tick_params(labelbottom=False)
    for s in d["sets"]:
        m = np.argsort(d["r"][d["iref"] == s])
        r = d["r"][d["iref"] == s][m]
        c = SERIES[s]
        ax_a.plot(r, d["ib"][d["iref"] == s][m], "-o", color=c, ms=2.6, mew=0.5,
                  lw=0.9, zorder=3, clip_on=False, label=f"{s} µA")
        ax_b.plot(r, d["req"][d["iref"] == s][m], "-o", color=c, ms=2.6, mew=0.5,
                  lw=0.9, zorder=3, clip_on=False, label=f"{s} µA")
        # plateau guide, stopping at the measured knee
        for ax, y in ((ax_a, sums[s]["ib"]), (ax_b, sums[s]["req"])):
            ax.plot([0.45, sums[s]["rmax"]], [y, y], color=c, lw=0.7,
                    ls=(0, (4, 2)), zorder=2)
    ax_a.set_ylim(0, 300)
    ax_a.set_ylabel("骨电流 I_bone (µA)")
    ax_a.legend(loc="upper right", fontsize=6, handlelength=1.6, labelspacing=0.3,
                borderpad=0.3, title="设定电流", title_fontsize=6)
    ax_b.set_ylim(25, 145)
    ax_b.set_ylabel("VBUS 等效负载 Req (kΩ)")
    note(ax_b, 1.5, 124, "越限后各曲线抬升，止于 123 kΩ 偏置地板", fontsize=6,
         color=NEUTRAL, va="center")
    panel_label(ax_a, "a")
    panel_label(ax_b, "b")

    # ---- c: plateau Req vs setpoint, with the bias floor --------------------
    ax_c.set_xscale("log")
    ax_c.set_yscale("log")
    ax_c.set_xlim(7, 320)
    ax_c.set_ylim(25, 150)
    ax_c.set_xticks([10, 20, 50, 100, 200])
    ax_c.set_xticklabels(["10", "20", "50", "100", "200"])
    ax_c.xaxis.set_minor_formatter(plt.NullFormatter())
    ax_c.tick_params(axis="x", which="minor", length=1.2)
    ax_c.set_yticks([30, 50, 70, 100, 140])
    ax_c.set_yticklabels(["30", "50", "70", "100", "140"])
    ax_c.yaxis.set_minor_formatter(plt.NullFormatter())
    ax_c.tick_params(axis="y", which="minor", length=1.2)
    ax_c.set_xlabel("设定电流 I_set (µA)")
    ax_c.set_ylabel("Req 平台值 (kΩ)")
    ii = np.logspace(np.log10(7), np.log10(320), 100)
    ax_c.plot(ii, V_BUS * 1e3 / ii, color=NEUTRAL, lw=0.8, ls=(0, (5, 2)), zorder=2)
    ax_c.plot(ii, V_BUS * 1e3 / (ii + bias), color="#0F4D92", lw=0.9, zorder=2)
    for s in d["sets"]:
        ax_c.plot(s, sums[s]["req"], "o", ms=3.4, mfc=SERIES[s], mec=SERIES[s], mew=0.5,
                  zorder=3, clip_on=False)
    ax_c.axhline(req_floor, color=NEUTRAL, lw=0.7, ls=(0, (1, 1.6)), zorder=1)
    # placement checked against both analytic lines and every marker
    note(ax_c, 150, 100, "V/I_set", fontsize=6, color=NEUTRAL, va="center")
    note(ax_c, 8, 45, "V/(I_set + 65 µA)", fontsize=6, color="#0F4D92", va="center")
    note(ax_c, 8, 131, f"偏置地板 {req_floor:.0f} kΩ", fontsize=6, color=NEUTRAL, va="center")
    panel_label(ax_c, "c")

    # ---- d: compliance limit vs setpoint -----------------------------------
    ax_d.set_xscale("log")
    ax_d.set_yscale("log")
    ax_d.set_xlim(7, 320)
    ax_d.set_ylim(20, 1500)
    ax_d.set_xticks([10, 20, 50, 100, 200])
    ax_d.set_xticklabels(["10", "20", "50", "100", "200"])
    ax_d.xaxis.set_minor_formatter(plt.NullFormatter())
    ax_d.tick_params(axis="x", which="minor", length=1.2)
    ax_d.set_yticks([30, 100, 300, 1000])
    ax_d.set_yticklabels(["30", "100", "300", "1000"])
    ax_d.yaxis.set_minor_formatter(plt.NullFormatter())
    ax_d.tick_params(axis="y", which="minor", length=1.2)
    ax_d.set_xlabel("设定电流 I_set (µA)")
    ax_d.set_ylabel("顺从上限 R_max (kΩ)")
    ax_d.plot(ii, (V_BONE_P - V_HEAD) * 1e3 / ii, color=NEUTRAL, lw=0.8, ls=(0, (5, 2)),
              zorder=2)
    for s in d["sets"]:
        ax_d.plot(s, sums[s]["rmax"], "o", ms=3.4, mfc=SERIES[s], mec=SERIES[s], mew=0.5,
                  zorder=3, clip_on=False)
    note(ax_d, 12, 1000, f"R_max = 7.66 V / I_set\n（漏极余量 0.345 V 恒定）", fontsize=6,
         color=NEUTRAL, va="center")
    note(ax_d, 30, 26, "降 10 倍电流 ↔ 换 10 倍可驱动骨阻", fontsize=6, color=NEUTRAL,
         va="center")
    panel_label(ax_d, "d")

    note_text = (
        f"数据：LTspice 26 稳态，VBUS = {V_BUS:.0f} V；设定值通过 R10 = 0.3 V/I_set 改变（30k/15k/6k/3k/1.5k Ω）；"
        f"n = {len(d['r'])} 个工作点（5 个设定值 × 9 个骨阻，全部绘出）；确定性仿真，无统计检验。\n"
        "虚线为解析参考：c 中 V/I_set 与 V/(I_set + 65.0 µA)；d 中 (V_BONE_P − 0.345 V)/I_set。"
    )
    fig.text(0.005, 0.045, note_text, fontsize=6, color=NEUTRAL, ha="left", va="bottom",
             linespacing=1.5)
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
        json_out=str(QA / "Fig1.alignment.json"),
        overlay_svg=str(QA / "Fig1.alignment.svg"),
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True,
    )
    fig.savefig(f"{STEM}.png", dpi=600)
    fig.savefig(f"{STEM}.pdf")
    fig.savefig(f"{STEM}.svg")
    fig.savefig(f"{STEM}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)
    print("saved", STEM)
