# Figure QA notes — BONE_P constant-current source

Deliverable: three publication figures, double-column 183 mm, exported as editable
SVG + PDF + TIFF (600 dpi) with a source-data CSV.

## Figure contract

**Core conclusion.** The largest BONE load the source can drive inside its ±1.5 %
accuracy budget scales as Rmax ≈ VBP/((1−T/100)·IREF) − R10 (R10 = 3 kΩ) and is
capped by the sense resistor's IR drop; all 30 (VBP, IREF) combinations were
located to a 1 Ω window.

**Evidence chain (panels have distinct inferential roles, no repeats).**

| Figure | Panel | Role |
|---|---|---|
| Fig. 1 | a | hero: the design-rule surface (Rmax vs supply, 5 target currents) |
| | b | validation: measured vs the analytic prediction, parity |
| | c | boundary of validity: where the rule stops holding (10 µA) |
| Fig. 2 | a–f | mechanism: the ±1.5 % compliance limit per supply rail |
| Fig. 3 | a–f | raw transfer characteristic (user-specified axes) |
| Fig. 4 | a | lookup matrix: Rmax read straight off a (VBP × IREF) grid |

Fig. 4 orientation and precision (as requested):
both axes run small → large (BONE_P 3.3 V at the bottom, 15 V at the top; IREF
10 µA on the left, 200 µA on the right), and every cell is printed to **three
decimals**. Three decimals is exact, not a rounding choice: each Rmax is an
integer number of ohms, so `RB/1000` is representable to exactly 3 dp.

Archetype: `quantitative grid`. Backend: Python / matplotlib (exclusive).

## Statistics and uncertainty (part of the figure, not caption cleanup)

```text
n definition:               12,369 simulated operating points, 12 LTspice runs
biological replicates:      none — this is a circuit simulation, not a biological experiment
technical replicates:       none — the transient solver is deterministic
center statistic:           not applicable; each point is one deterministic measurement
spread/interval:            none drawn. The only interval is the located PASS/FAIL
                            window, refined to 1 Ω (far below marker size)
test / correction:          none — no hypothesis test is applied
source data:                fig_source_rmax.csv (Rmax table); full data in
                            ../work/parsed_combined.json and the workbook Raw_Data
```

Error bars are deliberately absent: the data are deterministic simulation results.
Drawing a spread would misrepresent a solver output as a statistical estimate.

## Automated QA chain (all run on the final render)

| Check | Result |
|---|---|
| `validate_figure.py` source preflight | 20 pass, 1 warn, 0 fail |
| `require_matplotlib_panel_alignment` (render-time gate, strict) | **PASS** on all three |
| `audit_pdf_text.py --min-pt 5` (glyph floor) | **PASS** on all three (min 5.6 pt) |
| `audit_figure_collisions.py` | **PASS** on all three (0 fail, 0 warn) |
| Final page size measured from the PDF | 183.0 × 64.0, 183.0 × 112.0, 89.0 × 82.0 mm |
| Fig. 4 alignment gate | `NOT APPLICABLE` (single plot area, as the contract expects) |

### Documented warning

`FINAL-WIDTH` (source preflight): "No static final width detected". The width is
held in named constants (`FIG_W = 7.2047` in = 183.0 mm) that the static checker
cannot resolve. Resolved by measuring the exported PDF directly: **183.0 mm**
exactly, i.e. the double-column contract. Not a defect.

## Defects found and fixed during QA (kept here for the record)

1. **Wrong quantity plotted in Fig. 3.** The transfer panels computed the actual
   current as `IERR × IREF / 100`, but IERR is a *relative* error, so the factor
   was wrong by **732×** — the curves rose from zero instead of showing the
   constant-current plateau. Caught by panel inspection, not by any automated
   check. Fixed to read `IBONE` directly from the data.
2. **Invisible elements carrying labels.** A ±1 % band on a log parity axis
   (Fig. 1b) and ±1.5 % ribbons on a 0–250 µA linear axis (Fig. 3) are sub-pixel
   for most series; labelling something the reader cannot see is worse than
   omitting it. Both removed; Fig. 2 carries the budget quantitatively.
3. **Legend overlapping tick labels.** The shared legend was anchored with a
   negative offset and collided with the bottom row's x tick labels — the
   collision audit returned `FIX BEFORE DELIVERY`. Fixed by reserving an explicit
   bottom band and anchoring the legend inside it.
4. **Page wider than the contract.** A single-line footer note stretched the page
   to 223 mm. Wrapped to two lines; page is now exactly 183 mm.
5. **Glyphs below the 5 pt floor.** Matplotlib's default log formatter emits
   mathtext (`10^-2`) whose superscript renders at ~0.7× the parent — 4.55 pt
   from a 6.5 pt label. Replaced with a plain `%g` formatter. Also removed
   mathtext subscripts (`R_{max}` → `Rmax`).
6. **A glyph missing from Arial.** U+226A (≪) rendered as a missing-glyph box;
   replaced with plain text.
7. **Low label contrast in the heatmap.** Dark colormap ends (deep navy to dark
   maroon) forced per-cell white/ink switching and still bottomed out at 3.37:1.
   Keeping both ends at mid-tone — blue from the palette's blue family, red
   between `red_2` and `red_strong` — lets every cell take ink text at
   **4.72–13.91:1, none below 4.5:1**, and matches the reference style in which
   all cells carry dark text.
8. **The heatmap altered the data by rounding.** Cell labels were printed as
   integers, so e.g. 148.501 kΩ displayed as "149" — a 0.5 kΩ distortion of a
   1 Ω-precision result. Now printed to three decimals, which is lossless for
   this data. Verified by asserting every displayed value equals its raw
   last-PASS resistance / 1000 exactly (30/30 combinations).
9. **A narrow figure clipped its own footer.** The two-line note and the colourbar
   label ran past the 89 mm page edge (`text-page-clipping` FAILs). The footer is
   now wrapped to the figure width (`note_for(width_mm)`), and the colourbar sits
   in an explicitly reserved right band.

## Data integrity

- **No data excluded.** All 12,369 stored rows are used; nothing is sampled,
  interpolated, or imputed. Curves connect measured points only.
- The 30 Rmax values are the last PASS at the configured threshold, each located
  to a 1 Ω window (converged over 5 refinement rounds; every `lastPASS` has
  IERR = 1.4990–1.5000 %, every `firstFAIL` 1.5000–1.5050 %).
- The criterion is read from `../scripts/config.py` (`IERR_MAX_PCT = 1.5`), the
  same single source of truth the workbook uses, so figures and tables cannot
  drift apart.
- Rejected during analysis: none. One candidate outlier set (the 10 µA row) is
  *not* removed — it is the figure's subject.
- **No rounding, interpolation, smoothing or imputation anywhere.** Each figure
  value is a raw measurement from the stored dataset: Fig. 1/4 use the last-PASS
  load resistance, Fig. 2 the measured IERR, Fig. 3 the measured IBONE. A
  programmatic check asserts the 30 Fig. 4 cell values equal the raw
  last-PASS resistances / 1000 exactly.

## Files

| File | Purpose |
|---|---|
| `fig1_rmax_design_rule.{svg,pdf,tiff}` | design rule + validation |
| `fig2_compliance_limit.{svg,pdf,tiff}` | ±1.5 % compliance limit per rail |
| `fig3_transfer_characteristic.{svg,pdf,tiff}` | raw transfer characteristic |
| `fig4_rmax_heatmap.{svg,pdf,tiff}` | Rmax lookup matrix (single column, 89 mm) |
| `fig_source_rmax.csv` | source data behind Fig. 1 |
| `*.alignment.json`, `*.collision-audit.json` | QA reports (preserve with delivery) |
| `*.alignment.svg`, `*.collision-audit.pdf` | QA overlays — diagnostics only, never submission assets |
| `make_figures.py` | the plotting source |

Text is editable in SVG/PDF (`svg.fonttype="none"`, `pdf.fonttype=42`).
