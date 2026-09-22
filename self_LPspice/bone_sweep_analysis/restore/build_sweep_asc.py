#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild the sweep-version schematic that produced Draft2.log.

Basis: the ONLY things that differ between the surviving Draft2.asc and the deck
that was actually simulated are
  (1) R5's value expression  -> named param {R5SET} + a .param directive
  (2) U1's model             -> UniversalOpAmp2 (level2) with OPA333-spec params
  (3) the directive TEXT block (order matters: LTspice emits netlist directives
      in .asc line order, and .step nesting order defines which loop varies first)
Everything else (wires, flags, symbol placement, the other 18 devices) is taken
verbatim from the surviving .asc, whose netlist already matches the target.

Writes: restore/Draft2_sweep.asc   (scratch; nothing in the project dir is touched)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "Draft2_baseline.asc"
DST = HERE / "Draft2_sweep.asc"

s = SRC.read_text(encoding="utf-8")

# --- sanity: the baseline must not already be the sweep version -------------
for must in ["SYMATTR InstName U1", "SYMATTR Value OPAx333",
             r"SYMBOL OpAmps\\opamp2 656 160 R0", "!.lib OPAx333.LIB"]:
    if must not in s:
        sys.exit(f"ABORT: baseline is not the old revision (missing: {must!r})")
if "IREF list" in s or "UniversalOpAmp2" in s:
    sys.exit("ABORT: baseline already looks like a sweep version")

# --- (1) R5 value: named param ----------------------------------------------
a = "SYMATTR Value {10k*(3.3/(IREF*3k)-1)}"
b = "SYMATTR Value {R5SET}"
assert a in s, a
s = s.replace(a, b, 1)

# --- (2) U1: opamp2/OPAx333 -> UniversalOpAmp2 (level2) with OPA333 specs ----
# Field split mirrors UniversalOpAmp2.asy:  Value2 | SpiceLine | SpiceLine2
# (SpiceModel=level2 and ModelFile=UniversalOpAmp2.lib come from the .asy)
a = ("SYMBOL OpAmps\\\\opamp2 656 160 R0\n"
     "SYMATTR InstName U1\n"
     "SYMATTR Value OPAx333")
b = ("SYMBOL OpAmps\\\\UniversalOpAmp2 656 224 R0\n"
     "SYMATTR InstName U1\n"
     "SYMATTR Value2 Avol=3.16Meg GBW=350k Slew=160k\n"
     "SYMATTR SpiceLine Ilimit=5m Rail=50m Vos=2u\n"
     "SYMATTR SpiceLine2 En=55n Enk=0 In=100f Ink=0 Rin=1T")
assert a in s, "U1 block anchor not found"
s = s.replace(a, b, 1)

# --- (3) directive TEXT block, in the target's netlist order ----------------
# target netlist order: .meas x4, .tran, .param R5SET, .step IREF, .step RB, .step VBP
old_start = s.index("TEXT 1480 -288 Left 2 !.lib OPAx333.LIB")
old_block = s[old_start:]
assert old_block.count("TEXT ") == 6, old_block.count("TEXT ")
new_block = (
    "TEXT 1480 24 Left 2 !.meas tran IBONE AVG -I(R_BONE) FROM 12m TO 15m"
    "\\n.meas tran VBONE AVG V(BONE_P,BONE_N) FROM 12m TO 15m"
    "\\n.meas tran IERR PARAM 100*abs(IBONE-IREF)/IREF"
    "\\n.meas tran PASS PARAM if(IERR<=1,1,0)\n"
    "TEXT 1480 -88 Left 2 !.tran 15m startup\n"
    "TEXT 1480 -32 Left 2 !.param R5SET=10k*(3.3/(IREF*3k)-1)\n"
    "TEXT 1480 -288 Left 2 !.step param IREF list 10u 20u 50u 100u 200u\n"
    "TEXT 1480 -160 Left 2 !.step param RB 10k 200k 1k\n"
    "TEXT 1480 -192 Left 2 !.step param VBP list 3.3 5 8 10 12 15\n"
)
s = s[:old_start] + new_block
DST.write_text(s, encoding="utf-8")

print(f"[out] {DST}  ({DST.stat().st_size} bytes)")
print()
print("--- 指令区（顺序即网表顺序）---")
for ln in s.splitlines():
    if ln.startswith("TEXT"):
        print("  " + ln[:150])
print()
print("--- 改动确认 ---")
for probe in ["SYMATTR Value {R5SET}", "UniversalOpAmp2 656 224 R0",
              "SYMATTR Value2 Avol=3.16Meg GBW=350k Slew=160k",
              "SYMATTR SpiceLine Ilimit=5m Rail=50m Vos=2u",
              "SYMATTR SpiceLine2 En=55n Enk=0 In=100f Ink=0 Rin=1T"]:
    print(("  OK   " if probe in s else "  MISS ") + probe)
