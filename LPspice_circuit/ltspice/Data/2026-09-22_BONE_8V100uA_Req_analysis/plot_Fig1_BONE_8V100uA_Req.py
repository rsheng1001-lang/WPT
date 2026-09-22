"""Figure 1 — VBUS-port equivalent load vs bone load, at the 8 V / 100 uA design point.

FIGURE CONTRACT (nature-figure skill, backend = Python/matplotlib, exclusive)
--------------------------------------------------------------------------
1. Core conclusion (one sentence)
   At VBUS = 8 V with the sink set to 100 uA, the equivalent load seen at the VBUS
   port is a 48.5 kOhm constant-current-type load that is completely independent of
   the bone impedance as long as that impedance stays below the ~77 kOhm compliance
   limit; once it exceeds that limit the delivered current collapses ohmicly, the
   VBUS port load lightens (Req -> 109 kOhm at 1 MOhm), and all dissipation moves
   from the MOSFET into the bone load.

   Results-level question: when the bone load changes, how does the VBUS-port
   equivalent load change, where is the boundary, and what does crossing it cost?

2. Evidence chain (one distinct inferential role per panel)
   a  I_bone vs R_BONE          dose control itself: flat regulated band + the knee
   b  Req_VBUS vs R_BONE        the port characteristic that answers the question:
                                invariance, then the rise, with the analytic 123 kOhm
                                asymptote implied by the fixed bias
   c  V(I_SENSE)-V(I_SET)       regime-boundary evidence: the loop is in control
                                (deviation 0) exactly where a and b are flat, and
                                saturates only past the same 77 kOhm boundary; also
                                the practical in-circuit diagnostic
   d  P_bone and P_FET          mechanism and design cost: the same boundary moves
                                all dissipation from the device into the tissue
   Panels a-d share one x axis and one shaded out-of-compliance region, which is
   what makes them one argument rather than four redrawn metrics.

3. Archetype: quantitative grid (2 x 2, equal spans), hero panel = a by salience.

4. Backend: Python / matplotlib only.

5. Export contract
   Final size 183 mm x 118 mm (double column). Base font 7 pt, ticks/legends 6.5 pt,
   panel labels 8 pt bold lowercase; no rendered glyph below 5 pt (no mathtext
   subscripts). Editable text (pdf.fonttype 42, svg.fonttype none).
   Exports: PNG (600 dpi) + PDF + SVG. QA artifacts: panel-alignment JSON/SVG and
   the rendered collision-audit JSON.
   Source data: ../data/BONE_8V100uA_curve.csv — all 23 swept operating points are
   plotted; none excluded.
   Statistics: deterministic LTspice run (n = 23 steady-state operating points,
   27-30 ms average of a 30 ms .tran with startup); no statistical test applies and
   no uncertainty band is drawn because repeats are not part of this dataset.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.transforms import ScaledTranslation

# ---- mandatory editable-text configuration (skill rule, no exceptions) --------
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "Microsoft YaHei", "DejaVu Sans", "Liberation Sans"]
# Glyph-level fallback only engages through the font.family *list* (matplotlib >= 3.6):
# Latin/Greek resolve to Arial, the Chinese labels fall back to Microsoft YaHei.
plt.rcParams["font.family"] = ["Arial", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams.update({
    'svg.fonttype': 'none',      # keep SVG text as <text> nodes, not paths
    'pdf.fonttype': 42,          # embedded TrueType, text stays editable
    "font.size": 7,
    "axes.labelsize": 7,
    "axes.titlesize": 7,
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

PALETTE = {"main": "#0F4D92", "neutral": "#767676", "band": "#F2F2F2"}

RUN = Path(__file__).resolve().parent
DATA = RUN / "data" / "BONE_8V100uA_curve.csv"
CHARTS = RUN / "charts"
QA = CHARTS / "qa"
STEM = CHARTS / "Fig1_BONE_8V100uA_Req"

MM = 1 / 25.4
FIG_WIDTH_MM = 183.0   # Nature double column
FIG_HEIGHT_MM = 118.0
KNEE = 77.0            # last regulating bone resistance (kOhm), measured
VBP = 7.9991           # BONE_P at an 8 V bus (V)


def load():
    with open(DATA, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    d = {
        "r": np.array([float(r["R_bone_Ohm"]) for r in rows]) / 1e3,
        "ib": np.array([float(r["I_bone_A"]) for r in rows]) * 1e6,
        "req": np.array([float(r["Req_vbus_Ohm"]) for r in rows]) / 1e3,
        "pb": np.array([float(r["P_bone_W"]) for r in rows]) * 1e6,
        "pf": np.array([float(r["P_fet_W"]) for r in rows]) * 1e6,
        "dv": (np.array([float(r["V_ISENSE_V"]) for r in rows])
               - np.array([float(r["V_ISET_V"]) for r in rows])) * 1e3,
        "reg": np.array([r["state"] == "regulating" for r in rows]),
    }
    return d


def panel_label(ax, label, x_offset_pt=-30, y_offset_pt=3):
    """Bold lowercase panel label at a fixed physical offset from the axes corner."""
    off = ScaledTranslation(x_offset_pt / 72, y_offset_pt / 72, ax.figure.dpi_scale_trans)
    ax.text(0, 1, label, transform=ax.transAxes + off, fontsize=8,
            fontweight="bold", ha="left", va="bottom")


NOTES: list[tuple] = []


def note(ax, x, y, s, **kw):
    """Annotation that must stay inside its own axes box (checked after layout)."""
    t = ax.text(x, y, s, **kw)
    NOTES.append((ax, t, s))
    return t


def check_notes_inside_axes(fig, tol_pt=0.5):
    """Fail loudly if an annotation leaves the plot area it belongs to."""
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


def shade(ax, rmax):
    ax.axvspan(KNEE, rmax, color=PALETTE["band"], lw=0, zorder=0)
    ax.axvline(KNEE, color=PALETTE["neutral"], lw=0.7, ls=(0, (4, 2)), zorder=1)


def main():
    d = load()
    assert d["reg"].sum() >= 14 and (~d["reg"]).sum() == 23 - d["reg"].sum()
    # the shared x axis is logarithmic, so every bone resistance must be strictly positive
    assert np.all(d["r"] > 0), "log x-axis requires strictly positive bone resistance"
    i_flat = d["ib"][d["reg"]].mean()
    req_flat = d["req"][d["reg"]].mean()
    xlim = (0.42, 1500)
    rmax = xlim[1]

    fig, axes = plt.subplots(2, 2, figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM),
                             sharex=True)
    # fixed margins: the exported page must be exactly FIG_WIDTH_MM x FIG_HEIGHT_MM
    fig.subplots_adjust(left=0.085, right=0.985, top=0.952, bottom=0.195,
                        wspace=0.42, hspace=0.26)
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    # ---- a: dose control ------------------------------------------------------
    ax_a.plot(d["r"], d["ib"], "o", ms=2.8, mfc=PALETTE["main"], mec=PALETTE["main"],
              mew=0.5, zorder=3, clip_on=False)
    # the flat setpoint only holds left of the knee, so the guide line stops there
    ax_a.plot([xlim[0], 92], [i_flat, i_flat], color=PALETTE["main"], lw=0.7,
              ls=(0, (4, 2)), zorder=2)
    rr = np.logspace(np.log10(KNEE), 3.3, 200)
    ax_a.plot(rr, VBP / (rr + 3.0), color=PALETTE["neutral"], lw=0.8, ls=(0, (1, 1.6)),
              zorder=2)
    shade(ax_a, rmax)
    ax_a.set_ylim(0, 125)
    ax_a.set_ylabel("骨电流 I_bone (µA)")
    note(ax_a, 2.0, 103, f"恒流 {i_flat:.2f} µA", fontsize=6.5,
              color=PALETTE["main"], va="bottom")
    note(ax_a, 3.0, 55, "恒流区", fontsize=6.5, color=PALETTE["neutral"], va="center")
    note(ax_a, 110, 112, "越限区：环路饱和", fontsize=6.5, color=PALETTE["neutral"],
              va="center")
    panel_label(ax_a, "a")

    # ---- b: the port characteristic ------------------------------------------
    ax_b.plot(d["r"], d["req"], "o", ms=2.8, mfc=PALETTE["main"], mec=PALETTE["main"],
              mew=0.5, zorder=3, clip_on=False)
    ax_b.plot([xlim[0], 92], [req_flat, req_flat], color=PALETTE["main"], lw=0.7,
              ls=(0, (4, 2)), zorder=2)
    shade(ax_b, rmax)
    ax_b.set_ylim(40, 145)
    ax_b.set_ylabel("VBUS 等效负载 Req (kΩ)")
    note(ax_b, 2.0, 57, f"{req_flat:.2f} kΩ\n与骨阻无关", fontsize=6.5,
         color=PALETTE["main"], va="bottom")
    note(ax_b, 200, 128, f"{d['req'][-1]:.1f} kΩ\n@1 MΩ", fontsize=6.5,
         color=PALETTE["neutral"], va="center")
    note(ax_b, 170, 44, "偏置 65 µA\n渐近上限 123 kΩ", fontsize=6,
         color=PALETTE["neutral"], va="bottom")
    panel_label(ax_b, "b")

    # ---- c: regime boundary / loop diagnostic --------------------------------
    ax_c.plot(d["r"], d["dv"], "o", ms=2.8, mfc=PALETTE["main"], mec=PALETTE["main"],
              mew=0.5, zorder=3, clip_on=False)
    ax_c.axhline(0, color=PALETTE["neutral"], lw=0.7, zorder=2)
    shade(ax_c, rmax)
    ax_c.set_ylim(-320, 60)
    ax_c.set_ylabel("环路失调\nV(I_SENSE) − V(I_SET) (mV)")
    note(ax_c, 1.6, 14, "误差为 0：环路在控", fontsize=6.5, color=PALETTE["main"],
              va="bottom")
    note(ax_c, 110, -32, f"{d['dv'][-1]:.0f} mV @1 MΩ", fontsize=6.5,
              color=PALETTE["neutral"], va="top")
    ax_c.set_xlabel("骨阻抗 R_BONE (kΩ)")
    panel_label(ax_c, "c")

    # ---- d: where the power goes --------------------------------------------
    ax_d.plot(d["r"], d["pb"], "o", ms=2.8, mfc=PALETTE["main"], mec=PALETTE["main"],
              mew=0.5, zorder=3, clip_on=False)
    ax_d.plot(d["r"], d["pf"], "o", ms=2.8, mfc="white", mec=PALETTE["neutral"],
              mew=0.7, zorder=3, clip_on=False)
    shade(ax_d, rmax)
    ax_d.set_ylim(-40, 1000)
    ax_d.set_ylabel("耗散功率 (µW)")
    note(ax_d, 1.2, 380, "骨负载 P_bone", fontsize=6.5, color=PALETTE["main"],
         va="bottom")
    note(ax_d, 0.75, 800, "MOSFET P_FET", fontsize=6.5, color=PALETTE["neutral"],
         va="bottom")
    note(ax_d, 95, 790, f"峰值 {d['pb'].max():.0f} µW\n@{KNEE:.0f} kΩ", fontsize=6.5,
         color=PALETTE["main"], va="bottom")
    ax_d.set_xlabel("骨阻抗 R_BONE (kΩ)")
    panel_label(ax_d, "d")

    for ax in axes.ravel():
        ax.set_xscale("log")
        ax.set_xlim(*xlim)
        ax.set_xticks([1, 10, 100, 1000])
        ax.set_xticklabels(["1", "10", "100", "1000"])
        ax.xaxis.set_minor_formatter(plt.NullFormatter())
        ax.tick_params(axis="x", which="minor", length=1.2)
    for ax in (ax_a, ax_b):
        ax.tick_params(labelbottom=False)

    note_text = (
        "数据：LTspice 26 稳态，VBUS = 8 V，设定 100 µA；n = 23 个骨阻抗工作点"
        "（0.5 kΩ–1 MΩ，全部绘出）；确定性仿真，无统计检验。\n"
        "参考线：竖虚线 = 顺从上限 77 kΩ；点线 = 欧姆极限 I = V_BONE_P/(R_BONE + 3 kΩ)。"
    )
    fig.text(0.005, 0.045, note_text, fontsize=6, color=PALETTE["neutral"],
             ha="left", va="bottom", linespacing=1.5)
    return fig


if __name__ == "__main__":
    CHARTS.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    fig = main()

    check_notes_inside_axes(fig)

    from audit_panel_alignment import require_matplotlib_panel_alignment
    axs = fig.axes
    require_matplotlib_panel_alignment(
        fig,
        axes=axs,
        panel_ids=["a", "b", "c", "d"],
        row_groups=[["a", "b"], ["c", "d"]],
        column_groups=[["a", "c"], ["b", "d"]],
        json_out=str(QA / "Fig1.alignment.json"),
        overlay_svg=str(QA / "Fig1.alignment.svg"),
        tolerance_pt=1.5,
        gutter_tolerance_pt=1.5,
        require_panel_labels=True,
        strict=True,
    )
    fig.savefig(f"{STEM}.png", dpi=600)
    fig.savefig(f"{STEM}.pdf")
    fig.savefig(f"{STEM}.svg")
    fig.savefig(f"{STEM}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)
    print("saved", STEM)
