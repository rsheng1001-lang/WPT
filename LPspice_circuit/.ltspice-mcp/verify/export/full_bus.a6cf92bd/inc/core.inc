* Sink plus a resistive test load. Values and topology are the PDF's
* (2026-09-20 19:42); RLOAD is a test resistor, not a measured bone/electrode
* impedance. Decks that need another load fixture include sink.inc directly.
.include sink.inc
R_BONE BONE_P BONE_N {RLOAD}
