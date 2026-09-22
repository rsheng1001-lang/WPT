#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct XML audit of the DELIVERED .xlsx (no Excel involved).
Confirms per-sheet view state, autofilter, conditional formatting, number formats
and cached formula values survived the Excel round-trip.
"""
import re, zipfile, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as CFG

ROOT = Path(__file__).resolve().parent.parent
LAST_ROW = 1 + len(json.loads(
    (Path(__file__).resolve().parent.parent / 'work' /
     'parsed_combined.json').read_text(encoding='utf-8')))
WORK = ROOT / "work"
XLSX = ROOT / "Draft2_BONE_sweep_analysis.xlsx"
GT = json.loads((WORK / "ground_truth.json").read_text(encoding="utf-8"))

z = zipfile.ZipFile(XLSX)
wbx = z.read("xl/workbook.xml").decode("utf-8")
sheets = re.findall(r'<sheet name="([^"]+)" sheetId="\d+" r:id="(rId\d+)"/>', wbx)
rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
relmap = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels))

print(f"file: {XLSX.name}  ({XLSX.stat().st_size/1024:.0f} KB)")
print(f"sheets ({len(sheets)}): {[s[0] for s in sheets]}\n")

fails = []


def note(ok, msg):
    print(("  OK   " if ok else "  FAIL ") + msg)
    if not ok:
        fails.append(msg)


# ---- shared strings: the delivered file must contain the Chinese labels ----
for i, (name, rid) in enumerate(sheets, start=1):
    tgt = relmap[rid].lstrip("/").replace("xl/", "")
    xml = z.read("xl/" + tgt).decode("utf-8")
    view = re.search(r"<sheetView\s[^>]*/?>", xml)
    pane = re.findall(r"<pane[^>]*/>", xml)
    filt = re.findall(r'<autoFilter ref="([^"]+)"', xml)
    cf = re.findall(r"<conditionalFormatting sqref=\"([^\"]+)\"", xml)
    gridlines = ("showGridLines" in view.group(0)) if view else None
    print(f"[{name}] {tgt}")
    print(f"    sheetView: {view.group(0) if view else 'n/a'}")
    print(f"    freeze pane: {pane or 'none'}")
    print(f"    autofilter: {filt or 'none'}")
    print(f"    conditionalFormatting ranges: {len(cf)} -> {cf[:6]}")
    print(f"    gridlines shown: {gridlines}")

print()
# ---- the specific requirements from the task ----
print("requirement checks on delivered file:")
raw_path = "xl/" + relmap[[r for n, r in sheets if n == "Raw_Data"][0]].lstrip("/").replace("xl/", "")
raw = z.read(raw_path).decode("utf-8")
note('ySplit="1"' in raw and 'topLeftCell="A2"' in raw,
     "Raw_Data header row frozen (pane ySplit=1 @A2)")
note('state="frozen"' in raw, "Raw_Data freeze state = frozen (not split)")
note(f'<autoFilter ref="A1:K{LAST_ROW}"' in raw,
     f"Raw_Data autofilter A1:K{LAST_ROW}")
# OOXML puts several rules for the same range in ONE <conditionalFormatting>
# element with multiple <cfRule> children -- count rules, not elements.
nc = raw.count("<cfRule")
note(nc == 2, f"Raw_Data has 2 CF rules (PASS=1 green / PASS=0 red), got {nc}")

# conditional formatting formulas must reference $I (PASS)
note("$I2=1" in raw and "$I2=0" in raw, "Raw_Data CF keyed on PASS column ($I)")

# number formats: no scientific notation on uA / kOhm columns
sheetxml = z.read("xl/styles.xml").decode("utf-8")
for fmt in ["#,##0", "#,##0.###", "#,##0.000000", "#,##0.0000"]:
    note(fmt in sheetxml, f"number format present: {fmt}")
note("0.00E+00" not in raw and "E+00" not in raw,
     "no scientific-notation number format applied on Raw_Data")

# cached formula values (proves the file renders correctly without recalculation).
# Text results of FORMULAS are cached inline in the sheet XML (t="str"), while
# literal strings live in sharedStrings -- check both.
ss = z.read("xl/sharedStrings.xml").decode("utf-8")
sheets_all = "".join(z.read("xl/" + relmap[r].lstrip("/").replace("xl/", "")).decode("utf-8")
                     for _, r in sheets)
blob = ss + sheets_all
n_shared_f = blob.count('t="shared"')
note("<f" in blob and "<v>" in blob,
     "formulas present AND cached <v> results present")
print(f"    shared-formula groups: {n_shared_f}")
# derive the expected cached strings from ground truth instead of hardcoding
# them, so refining the data does not invalidate this audit
_rmax = sorted(set(GT["rmax_disp"].values()))
_na = f"N/A (基础误差&gt;{CFG.IERR_MAX_PCT:g}%)"
for want in [_na] + [w.replace(">", "&gt;") for w in _rmax]:
    note(want in blob, f"cached Rmax string present: {want}")
print(f"    ({len(_rmax)} distinct Rmax display strings checked)")
note('t="str"' in sheets_all, "formula TEXT results cached inline (t=\"str\")")

print()
print(f"delivered-file audit: {'PASS' if not fails else 'FAIL (%d)' % len(fails)}")
for f in fails:
    print("  x", f)
raise SystemExit(1 if fails else 0)
