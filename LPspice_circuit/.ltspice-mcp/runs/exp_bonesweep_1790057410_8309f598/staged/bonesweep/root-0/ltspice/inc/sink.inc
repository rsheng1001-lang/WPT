* Current-sink core, no load. Exact PDF values and topology (2026-09-20 19:42).
* Split out of core.inc so test decks can substitute their own load fixture
* without duplicating the sink itself.
R5 V3V3 DIV 100k
R7 DIV 0 10k
R6 DIV I_SET 10k
C12 I_SET 0 100n
C13 V3V3 0 100n
XU3 I_SET I_SENSE V3V3 0 OUTA OPAx333
C14 OUTA I_SENSE 100p
R8 OUTA STIM_GATE 10k
XQ1 BONE_N STIM_GATE I_SENSE N7002
R9 STIM_GATE I_SENSE 10Meg
R10 I_SENSE 0 3k
