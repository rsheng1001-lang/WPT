* Solver policy for decks that load the TI OPAx333 macro-model.
* LTspice's Gmin/source stepping fallbacks inject leakage into the model's
* tera-ohm internal nodes (e.g. R_R53 VCC_CLP MID 1T) and can return a
* spurious operating point whose output sits outside the supply rails
* (measured: V(OUTA)=-5.21 V on a 0/3.3 V supply). Pure Newton with the
* pseudo-transient fallback keeps every reported solution physical.
.options gminsteps=0 srcsteps=0
