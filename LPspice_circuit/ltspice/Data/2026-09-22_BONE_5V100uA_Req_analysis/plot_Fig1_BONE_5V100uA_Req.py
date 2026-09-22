"""Figure 1 — VBUS-port equivalent load vs bone load, at the 5 V / 100 uA operating point.

FIGURE CONTRACT (nature-figure skill, backend = Python/matplotlib, exclusive)
--------------------------------------------------------------------------
1. Core conclusion (one sentence)
   At VBUS = 5 V with the sink set to 100 uA the VBUS-port equivalent load is a
   31.19 kOhm constant-current-type load, invariant with bone impedance up to the
   ~47 kOhm compliance limit of this lower rail; past it the delivered current
   collapses ohmicly, the port load lightens (76.2 kOhm at 1 MOhm) and all
   dissipation moves from the MOSFET into the bone load. Compared with the 8 V
   run the flat current is identical (the setpoint tracks the 3.3 V rail, not the
   bus) while both the compliance limit and the port resistance scale down.

   Results-level question: how does the VBUS-port equivalent load behave against
   bone load at a 5 V bus, and where does the design point stop being a current
   source?

2. Evidence chain (one distinct inferential role per panel)
   a  I_bone vs R_BONE          dose control itself: flat regulated band + the knee
   b  Req_VBUS vs R_BONE        the port characteristic: invariance, the rise, and
                                the 82.6 kOhm asymptote implied by the 60.5 uA bias
   c  V(I_SENSE)-V(I_SET)       regime-boundary evidence: loop in control (0) exactly
                                where a and b are flat, saturating past the same knee
   d  P_bone and P_FET          mechanism and cost: the knee moves all dissipation
                                from the device into the tissue
   The four panels share one log x axis and one shaded out-of-compliance band.

3. Archetype: quantitative grid (2 x 2, equal spans), hero panel = a.

4. Backend: Python / matplotlib only.

5. Export contract
   Final size 183 mm x 118 mm (double column). Base 7 pt, ticks 6.5 pt, panel labels
   8 pt bold lowercase; no rendered glyph below 5 pt (no mathtext scripts). Editable
   text (pdf.fonttype 42, svg.fonttype none). Exports: PNG 600 dpi + PDF + SVG + TIFF.
   QA artifacts: alignment JSON/SVG and the rendered collision-audit JSON.
   Source data: ../data/BONE_5V100uA_curve.csv — all 23 swept operating points are
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

# ---- mandatory editable-text configuration (skill rule) -----------------------
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
DATA = RUN / "data" / "BONE_5V100uA_curve.csv"
CHARTS = RUN / "charts"
QA = CHARTS / "qa"
STEM = CHARTS / "Fig1_BONE_5V100uA_Req"

MM = 1 / 25.4
FIG_WIDTH_MM = 183.0   # Nature double column
FIG_HEIGHT_MM = 118.0
V_BUS = 5.0            # this run's bus voltage
R10 = 3.0              # sense resistor, kOhm


def load():
    with open(DATA, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {
        "r": np.array([float(r["R_bone_Ohm"]) for r in rows]) / 1e3,
        "ib": np.array([float(r["I_bone_A"]) for r in rows]) * 1e6,
        "req": np.array([float(r["Req_vbus_Ohm"]) for r in rows]) / 1e3,
        "pb": np.array([float(r["P_bone_W"]) for r in rows]) * 1e6,
        "pf": np.array([float(r["P_fet_W"]) for r in rows]) * 1e6,
        "dv": (np.array([float(r["V_ISENSE_V"]) for r in rows])
               - np.array([float(r["V_ISET_V"]) for r in rows])) * 1e3,
        "reg": np.array([r["state"] == "regulating" for r in rows]),
    }


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


def main():
    d = load()
    reg = d["reg"]
    # the shared x axis is logarithmic, so every bone resistance must be strictly positive
    assert np.all(d["r"] > 0), "log x-axis requires strictly positive bone resistance"
    assert 5 < reg.sum() < len(d["r"]), "need both regimes represented"
    i_flat = d["ib"][reg].mean()
    req_flat = d["req"][reg].mean()
    knee = d["r"][reg].max()                       # last regulating bone resistance
    knee_next = d["r"][~reg].min()
    bias = V_BUS / req_flat * 1e3 - i_flat    # uA drawn beside I_bone (divider+rail+quiescent)
    req_asym = V_BUS / bias * 1e3             # kOhm as R_BONE -> inf
    vbp = 8.0016 if V_BUS > 8.4 else V_BUS - 0.0009  # 8 V rail regulated, else in dropout
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
    ax_a.plot([xlim[0], knee * 1.2], [i_flat, i_flat], color=PALETTE["main"], lw=0.7,
              ls=(0, (4, 2)), zorder=2)
    rr = np.logspace(np.log10(knee), 3.3, 200)
    ax_a.plot(rr, vbp / (rr + R10), color=PALETTE["neutral"], lw=0.8, ls=(0, (1, 1.6)),
              zorder=2)
    ax_a.axvspan(knee, rmax, color=PALETTE["band"], lw=0, zorder=0)
    ax_a.axvline(knee, color=PALETTE["neutral"], lw=0.7, ls=(0, (4, 2)), zorder=1)
    ax_a.set_ylim(0, 125)
    ax_a.set_ylabel("骨电流 I_bone (µA)")
    note(ax_a, 2.0, 103, f"恒流 {i_flat:.2f} µA", fontsize=6.5, color=PALETTE["main"],
         va="bottom")
    note(ax_a, 3.0, 55, "恒流区", fontsize=6.5, color=PALETTE["neutral"], va="center")
    note(ax_a, 80, 112, "越限区：环路饱和", fontsize=6.5, color=PALETTE["neutral"],
         va="center")
    panel_label(ax_a, "a")

    # ---- b: the port characteristic ------------------------------------------
    ax_b.plot(d["r"], d["req"], "o", ms=2.8, mfc=PALETTE["main"], mec=PALETTE["main"],
              mew=0.5, zorder=3, clip_on=False)
    ax_b.plot([xlim[0], knee * 1.2], [req_flat, req_flat], color=PALETTE["main"], lw=0.7,
              ls=(0, (4, 2)), zorder=2)
    ax_b.axvspan(knee, rmax, color=PALETTE["band"], lw=0, zorder=0)
    ax_b.axvline(knee, color=PALETTE["neutral"], lw=0.7, ls=(0, (4, 2)), zorder=1)
    ax_b.set_ylim(20, 100)
    ax_b.set_ylabel("VBUS 等效负载 Req (kΩ)")
    note(ax_b, 2.0, 38, f"{req_flat:.2f} kΩ\n与骨阻无关", fontsize=6.5,
         color=PALETTE["main"], va="bottom")
    note(ax_b, 230, 88, f"{d['req'][-1]:.1f} kΩ\n@1 MΩ", fontsize=6.5,
         color=PALETTE["neutral"], va="center")
    note(ax_b, 130, 23, f"偏置 {bias:.1f} µA\n渐近上限 {req_asym:.0f} kΩ", fontsize=6,
         color=PALETTE["neutral"], va="bottom")
    panel_label(ax_b, "b")

    # ---- c: regime boundary / loop diagnostic --------------------------------
    ax_c.plot(d["r"], d["dv"], "o", ms=2.8, mfc=PALETTE["main"], mec=PALETTE["main"],
              mew=0.5, zorder=3, clip_on=False)
    ax_c.axhline(0, color=PALETTE["neutral"], lw=0.7, zorder=2)
    ax_c.axvspan(knee, rmax, color=PALETTE["band"], lw=0, zorder=0)
    ax_c.axvline(knee, color=PALETTE["neutral"], lw=0.7, ls=(0, (4, 2)), zorder=1)
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
    ax_d.axvspan(knee, rmax, color=PALETTE["band"], lw=0, zorder=0)
    ax_d.axvline(knee, color=PALETTE["neutral"], lw=0.7, ls=(0, (4, 2)), zorder=1)
    ax_d.set_ylim(-40, 1000)
    ax_d.set_ylabel("耗散功率 (µW)")
    note(ax_d, 1.2, 230, "骨负载 P_bone", fontsize=6.5, color=PALETTE["main"], va="bottom")
    note(ax_d, 0.75, 800, "MOSFET P_FET", fontsize=6.5, color=PALETTE["neutral"],
         va="bottom")
    note(ax_d, 58, 640, f"峰值 {d['pb'][reg].max():.0f} µW\n@{knee:.0f} kΩ", fontsize=6.5,
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
        f"数据：LTspice 26 稳态，VBUS = {V_BUS:.0f} V，设定 100 µA；n = {len(d['r'])} 个骨阻抗工作点"
        "（0.5 kΩ–1 MΩ，全部绘出）；确定性仿真，无统计检验。\n"
        f"参考线：竖虚线 = 顺从上限 {knee:.0f} kΩ（下一个点 {knee_next:.0f} kΩ 已越限）；"
        f"点线 = 欧姆极限 I = V_BONE_P/(R_BONE + {R10:.0f} kΩ)。"
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
    require_matplotlib_panel_alignment(
        fig,
        axes=fig.axes,
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
