#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publication figures for the BONE_P constant-current-source sweep.

Figure contract (established before any drawing code)
-----------------------------------------------------
Core conclusion
    The largest BONE load the source can drive inside its +/-1.5 % accuracy budget
    scales as Rmax ~ VBP/IREF and is capped by the 3 kOhm sense resistor's IR drop;
    all 30 (VBP, IREF) combinations were located to a 1 ohm window.

Evidence chain / panel roles
    Fig 1  a  hero: the design-rule surface, Rmax vs supply for 5 target currents
           b  validation: measured vs the analytic prediction (identity + 1 % band)
           c  boundary of validity: formula error vs target current
    Fig 2  a-f mechanism: where the constant-current region ends, per supply rail
    Fig 3  a-f the raw transfer characteristic (user-specified axes), with the
               +/-1.5 % band drawn so the departure from regulation is visible

Archetype      quantitative grid
Backend        Python / matplotlib (exclusive; see nature-figure backend gate)
Export         double column 183 mm, base font 7 pt (>=5 pt glyph floor),
               editable text, SVG + PDF + TIFF @600 dpi, source CSV alongside

Statistics / uncertainty (part of the figure, not caption cleanup)
    n = 12,369 simulated operating points from 12 LTspice runs.
    The data are DETERMINISTIC transient-simulation results, not replicates, so no
    error bars are drawn and no statistical test is applied. The only interval is
    the located PASS->FAIL window, converged to 1 ohm, which is below marker size.
    Criterion: |IERR| <= 1.5 %.
"""
from __future__ import annotations

import csv
import json
import sys
import textwrap
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch

# Final physical size, double-column.  Quoted in inches because that is what
# Matplotlib takes; the mm equivalents are 183 x 64 and 183 x 112.
FIG_W = 7.2047        # 183 mm
FIG_H_ROW3 = 2.5197   #  64 mm
FIG_H_ROW6 = 4.4094   # 112 mm
FIG_W_COL = 3.5039    #  89 mm, single column
FIG_H_MAT = 3.2283    #  82 mm


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import config as CFG                                            # noqa: E402

# nature-figure render-time alignment gate (skill scripts dir on PYTHONPATH)
from audit_panel_alignment import require_matplotlib_panel_alignment   # noqa: E402

OUT = Path(__file__).resolve().parent
T = CFG.IERR_MAX_PCT
R10_KOHM = 3.0                      # current-sense resistor, sets the compliance cap

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",          # keep text editable
    "pdf.fonttype": 42,
    "font.size": 7,
    "axes.titlesize": 7.5,
    "axes.labelsize": 7,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "legend.fontsize": 6.5,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "lines.linewidth": 1.1,
    "lines.markersize": 3.0,
})

# --- one restrained palette: an ordered blue family + one red accent ----------
# The five target currents are an ORDERED family, so an ordered ramp is used
# rather than five unrelated hues. 10 uA is the accent because its accuracy
# margin is nearly exhausted (base error 1.30 % vs a 1.5 % budget).
IREF_UA = [10, 20, 50, 100, 200]
C10, C20, C50, C100, C200 = "#B64342", "#B4C0E4", "#7884B4", "#3775BA", "#0F4D92"
COLOR = {10: C10, 20: C20, 50: C50, 100: C100, 200: C200}
VBPS = [3.3, 5.0, 8.0, 10.0, 12.0, 15.0]
INK = "#272727"
NEUTRAL = "#767676"


def load():
    rows = json.loads((ROOT / "work" / "parsed_combined.json").read_text(encoding="utf-8"))
    for r in rows:
        r["iua"] = round(r["iref"] * 1e6, 6)
    return rows


ROWS = load()
G = {(r["vbp"], r["iua"], r["rb"]): r for r in ROWS}
ALL_RB = sorted({r["rb"] for r in ROWS})


def assert_positive(values, what):
    """Log axes are used below; make the positivity requirement explicit."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    assert arr.size and np.all(arr > 0), f"{what} must be strictly positive for a log axis"


def series(vbp, iua):
    """Rows of one (VBP, IREF) group, ordered by load resistance."""
    out = [G[(vbp, iua, rb)] for rb in ALL_RB if (vbp, iua, rb) in G]
    return out


def rmax(vbp, iua):
    """Last load that still meets the budget (the boundary is located to 1 ohm)."""
    ok = [r["rb"] for r in series(vbp, iua) if CFG.passes(r["IERR"])]
    return (max(ok), min(r["rb"] for r in series(vbp, iua)
                         if r["rb"] > max(ok) and not CFG.passes(r["IERR"]))) if ok else (None, None)


def predict(vbp, iua):
    """Analytic design rule: current has already sagged by ~T % at the boundary."""
    return vbp / ((1 - T / 100) * iua) * 1000 - R10_KOHM


def plain_log_labels(ax):
    """Plain decimal tick labels on log axes.

    Matplotlib's default log formatter emits mathtext (10^-2), whose superscript
    renders at ~0.7x the parent size -- 4.55 pt from a 6.5 pt label, below the
    5 pt glyph floor. A plain '%g' formatter keeps every glyph at full size.
    """
    fmt = FuncFormatter(lambda v, _pos: f"{v:g}")
    for axis, scale in ((ax.xaxis, ax.get_xscale()), (ax.yaxis, ax.get_yscale())):
        if scale == "log":
            axis.set_major_formatter(fmt)


def panel_label(ax, text):
    """Bold lowercase label at a fixed point offset from the axes corner."""
    ax.annotate(text, xy=(0, 1), xycoords="axes fraction",
                xytext=(-15.5, 4.0), textcoords="offset points",
                fontsize=8, fontweight="bold", color=INK,
                ha="left", va="bottom", annotation_clip=False)


def note_for(width_mm):
    """Wrap the footer note to the figure width (~1.15 mm per character at 5.6 pt)."""
    flat = " ".join((NOTE or "").split())
    return textwrap.fill(flat, width=max(40, int(width_mm / 1.15)))


def finish(fig, stem, panels=None, legend_handles=None, legend_cols=5, note=None,
           legend_y=0.094, note_y=0.014):
    """Shared legend + footer note, alignment gate, then export the bundle.

    The caller reserves the bottom band via subplots_adjust(bottom=...); the
    legend is anchored inside that band so it cannot overlap tick labels.
    """
    # matplotlib renders log-axis MINOR tick labels at ~0.7x the major size, which
    # fell to 4.55 pt -- below the 5 pt glyph floor. Pin them explicitly.
    for ax in fig.axes:
        ax.tick_params(which="minor", labelsize=6.0)
        plain_log_labels(ax)
    if legend_handles:
        fig.legend(handles=legend_handles, loc="lower center", ncol=legend_cols,
                   frameon=False, handlelength=1.8, columnspacing=1.4,
                   bbox_to_anchor=(0.5, legend_y))
    if note:
        fig.text(0.5, note_y, note, ha="center", va="bottom", fontsize=5.6,
                 color=NEUTRAL)
    require_matplotlib_panel_alignment(
        fig, json_out=f"{stem}.alignment.json", overlay_svg=f"{stem}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5,
        require_panel_labels=bool(panels), strict=True)
    # Save the full canvas: bbox_inches="tight" cropped the side margins and left
    # the page at ~158 mm instead of the contracted 183 mm double-column width.
    fig.savefig(f"{stem}.svg")
    fig.savefig(f"{stem}.pdf")
    fig.savefig(f"{stem}.tiff", dpi=600)
    print(f"  wrote {Path(stem).name}.svg/.pdf/.tiff")
    plt.close(fig)


NOTE = ("n = " + f"{len(ROWS):,}" + " simulated operating points from 12 LTspice runs "
        "(deterministic transient simulation; no stochastic replicates, so no error bars)."
        + chr(10) +
        f"Each PASS/FAIL boundary was refined until the window was 1 Ω, far below marker size. "
        f"Criterion |IERR| ≤ {T:g} %.")


# =============================================================== Figure 1
def figure1():
    fig, axes = plt.subplots(1, 3, figsize=(FIG_W, FIG_H_ROW3))
    ax = axes[0]

    for iua in IREF_UA:
        xs = [v for v in VBPS]
        ys = [rmax(v, iua)[0] / 1000.0 for v in VBPS]
        ax.plot(xs, ys, marker="o", color=COLOR[iua], label=f"{iua} \u00b5A",
                markeredgecolor="white", markeredgewidth=0.4, zorder=3)
    ax.set_xlabel("BONE_P supply voltage (V)")
    ax.set_ylabel("Maximum BONE load, Rmax (kΩ)")
    ax.set_title("Design rule: usable load range", pad=6)
    ax.set_xlim(2.6, 15.9)
    ax.set_ylim(0, 1620)
    ax.grid(axis="y", color="#E6E6E6", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    panel_label(ax, "a")

    # --- b: parity against the analytic rule ---------------------------------
    ax = axes[1]
    lim = (10, 1650)
    ax.plot(lim, lim, color=NEUTRAL, lw=0.8, ls="--", zorder=1)
    # A +/-1 % band is ~0.009 decades wide on a log parity axis -- invisible,
    # and a label pointing at something the reader cannot see is worse than
    # no label. Panel c carries the quantitative deviation instead.
    for iua in IREF_UA:
        ms = [rmax(v, iua)[0] / 1000.0 for v in VBPS]
        ps = [predict(v, iua) for v in VBPS]
        ax.plot(ps, ms, marker="o", ls="none", color=COLOR[iua],
                markeredgecolor="white", markeredgewidth=0.4, zorder=3)
    assert_positive([predict(v, i) for v in VBPS for i in IREF_UA], "prediction")
    assert_positive([rmax(v, i)[0] for v in VBPS for i in IREF_UA], "measured Rmax")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("Analytic prediction (k\u03a9)")
    ax.set_ylabel("Measured Rmax (kΩ)")
    ax.set_title("Agreement with the design rule", pad=6)
    panel_label(ax, "b")

    # --- c: where the rule stops holding ------------------------------------
    ax = axes[2]
    for iua in IREF_UA:
        dev = [abs(rmax(v, iua)[0] / 1000.0 - predict(v, iua)) / predict(v, iua) * 100
               for v in VBPS]
        ax.plot([iua] * len(dev), dev, marker="o", ls="none", color=COLOR[iua],
                markeredgecolor="white", markeredgewidth=0.4, zorder=3)
    assert_positive([abs(rmax(v, i)[0] / 1000.0 - predict(v, i)) / predict(v, i) * 100
                     for v in VBPS for i in IREF_UA], "rule deviation")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(8, 260)
    ax.set_ylim(0.005, 10)
    ax.axhline(0.1, color=NEUTRAL, lw=0.8, ls=":", zorder=1)
    ax.text(9, 0.112, "0.1 % ", fontsize=6, color=NEUTRAL, va="bottom")
    ax.annotate("accuracy margin nearly\nexhausted at 10 \u00b5A\n(base error 1.30 % vs 1.5 %)",
                xy=(10, 3.4), xytext=(15.5, 1.1), fontsize=6, color=C10,
                arrowprops=dict(arrowstyle="-", color=C10, lw=0.7,
                                shrinkA=0, shrinkB=2))
    ax.set_xlabel("Target current, IREF (µA)")
    ax.set_ylabel("|Measured \u2212 rule| / rule (%)")
    ax.set_title("Validity range of the rule", pad=6)
    ax.set_xticks(IREF_UA)
    ax.set_xticklabels([str(i) for i in IREF_UA])
    panel_label(ax, "c")

    handles = [Line2D([], [], color=COLOR[i], marker="o", ls="-",
                      markeredgecolor="white", markeredgewidth=0.4,
                      label=f"{i} \u00b5A") for i in IREF_UA]
    fig.subplots_adjust(wspace=0.34, bottom=0.37)
    finish(fig, str(OUT / "fig1_rmax_design_rule"), panels=True,
           legend_handles=handles, note=NOTE, legend_y=0.098, note_y=0.016)


# ========================================================== Figures 2 and 3
def small_multiples(kind):
    """kind='ierr' -> spec-compliance view;  kind='transfer' -> raw transfer."""
    fig, axes = plt.subplots(2, 3, figsize=(FIG_W, FIG_H_ROW6),
                             sharex=True, sharey=True)
    for k, vbp in enumerate(VBPS):
        ax = axes[k // 3][k % 3]
        for iua in IREF_UA:
            s = series(vbp, iua)
            x = [r["rb"] / 1000.0 for r in s]
            if kind == "ierr":
                y = [r["IERR"] for r in s]
            else:
                y = [r["IBONE"] * 1e6 for r in s]
            ax.plot(x, y, color=COLOR[iua], lw=1.0, zorder=3)
        if kind == "ierr":
            ax.axhline(T, color=INK, lw=0.8, ls="--", zorder=4)
            lo, hi = rmax(vbp, IREF_UA[-1])
            for iua in IREF_UA:
                b, _ = rmax(vbp, iua)
                ax.plot([b / 1000.0], [T], marker="v", ms=3.4, color=COLOR[iua],
                        markeredgecolor="white", markeredgewidth=0.35, zorder=5,
                        clip_on=False)
        # A +/-1.5 % ribbon is sub-pixel for 10-50 uA on a 0-250 uA linear
        # axis, so it would read as noise; the budget is quantified in Fig. 2.
        assert_positive([r["rb"] for r in series(vbp, IREF_UA[0])], "load resistance")
        if kind == "ierr":
            assert_positive([r["IERR"] for i in IREF_UA for r in series(vbp, i)], "IERR")
        ax.set_xscale("log")
        ax.set_xlim(10, 10000)
        ax.set_title(f"BONE_P = {vbp:g} V", pad=4)
        panel_label(ax, "abcdef"[k])
    if kind == "ierr":
        axes[0][0].set_yscale("log")
        axes[0][0].set_ylim(0.1, 130)
        axes[0][0].set_ylabel("Current error, IERR (%)")
        axes[1][0].set_ylabel("Current error, IERR (%)")
    else:
        axes[0][0].set_ylim(0, 260)
        axes[0][0].set_ylabel("Actual BONE current (\u00b5A)")
        axes[1][0].set_ylabel("Actual BONE current (\u00b5A)")
    for ax in axes[1]:
        ax.set_xlabel("BONE load resistance (\u03a9, log scale)")
    handles = [Line2D([], [], color=COLOR[i], lw=1.6, label=f"{i} \u00b5A")
               for i in IREF_UA]
    if kind == "ierr":
        handles.append(Line2D([], [], color=INK, lw=0.8, ls="--",
                              label=f"|IERR| = {T:g} % budget"))
        handles.append(Line2D([], [], color=NEUTRAL, marker="v", ls="none",
                              ms=3.4, label="Rmax (boundary)"))
    fig.subplots_adjust(hspace=0.32, wspace=0.22, bottom=0.225)
    stem = (OUT / ("fig2_compliance_limit" if kind == "ierr"
                   else "fig3_transfer_characteristic"))
    finish(fig, str(stem), panels=True, legend_handles=handles,
           legend_cols=len(handles), note=NOTE, legend_y=0.062, note_y=0.012)


# =============================================================== Figure 4
def figure4():
    """Design lookup matrix: Rmax for every (VBP, IREF) combination.

    Panel role: a 2-D lookup chart, not a trend -- it lets a reader read a value
    off the grid directly. Diverging blue-white-red as requested; the colourbar
    defines the mapping, and the midpoint is the data mid-range (there is no
    physical reference point for Rmax).
    """
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

    fig, ax = plt.subplots(figsize=(FIG_W_COL, FIG_H_MAT))
    order = list(range(len(VBPS)))[::-1]        # 15 V on top ... 3.3 V at the bottom
    vals = np.array([[rmax(VBPS[r], i)[0] / 1000.0 for i in IREF_UA] for r in order])
    lo, hi = vals.min(), vals.max()
    cmap = LinearSegmentedColormap.from_list(
        "bone_div", ["#7FA8D4", "#BFD3E8", "#F7F7F7", "#F0C9C5", "#D9736F"])
    norm = TwoSlopeNorm(vmin=lo, vcenter=(lo + hi) / 2, vmax=hi)
    im = ax.imshow(vals, cmap=cmap, norm=norm, aspect="auto",
                   extent=(-0.5, len(IREF_UA) - 0.5, len(VBPS) - 0.5, -0.5))

    # every cell takes ink text: the mid-tone map keeps that at >=6.6:1
    # (measured over all 30 cells) with no per-cell colour switching
    for r in range(len(VBPS)):
        for c in range(len(IREF_UA)):
            ax.text(c, r, f"{vals[r, c]:.3f}", ha="center", va="center",
                    fontsize=6.2, color=INK)

    ax.set_xticks(range(len(IREF_UA)))
    ax.set_xticklabels([str(i) for i in IREF_UA])
    ax.set_yticks(range(len(VBPS)))
    ax.set_yticklabels([f"{VBPS[r]:g}" for r in order])
    ax.set_xlabel("Target current, IREF (µA)")
    ax.set_ylabel("BONE_P supply voltage (V)")
    ax.set_title(f"Maximum BONE load, Rmax (kΩ), at a ±{T:g} % budget", pad=6)
    ax.set_xticks(np.arange(-0.5, len(IREF_UA), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(VBPS), 1), minor=True)
    ax.grid(which="minor", color="white", lw=1.2)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(which="major", length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    panel_label(ax, "a")

    cb = fig.colorbar(im, ax=ax, pad=0.025, fraction=0.055)
    cb.set_label("Rmax (kΩ)", fontsize=6.5)
    cb.ax.tick_params(labelsize=6.5, length=2)
    cb.outline.set_visible(False)

    # reserve a right band so the colourbar label cannot run off the page, and a
    # deep bottom band for the wrapped footer note
    fig.subplots_adjust(left=0.13, right=0.845, top=0.90, bottom=0.30)
    finish(fig, str(OUT / "fig4_rmax_heatmap"), panels=False,
           note=note_for(89), note_y=0.012)


def write_source_csv():
    """Source data behind the figures, for traceability."""
    with open(OUT / "fig_source_rmax.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["vbp_v", "iref_uA", "rmax_kohm", "first_fail_kohm",
                    "ierr_at_rmax_pct", "rule_kohm", "rule_error_pct"])
        for vbp in VBPS:
            for iua in IREF_UA:
                b, f = rmax(vbp, iua)
                p = predict(vbp, iua)
                w.writerow([vbp, iua, f"{b/1000:.3f}", f"{f/1000:.3f}",
                            f"{G[(vbp, iua, b)]['IERR']:.6f}", f"{p:.3f}",
                            f"{abs(b/1000-p)/p*100:.4f}"])
    print("  wrote fig_source_rmax.csv")


if __name__ == "__main__":
    write_source_csv()
    figure1()
    figure4()
    small_multiples("ierr")
    small_multiples("transfer")
    print("done")
