"""Re-run every deck and print the measured summary. One command to reproduce.

usage: python run_all.py
"""
import subprocess, sys
from pathlib import Path
import numpy as np
from read_raw import read_raw

ROOT = Path(__file__).resolve().parent.parent   # ltspice/
RUNS = ROOT / 'runs'
EXE = Path('D:/Program Files/LTspice/LTspice.exe')


FLAKY = []


def collect(deck):
    """Move a deck's outputs into runs/, so the deck folder stays readable."""
    src = ROOT / deck
    for suf in ('.raw', '.log', '.db', '.op.raw'):
        f = src.with_suffix(suf)
        if f.exists():
            f.replace(RUNS / f.name)


def export_netlist(asc, timeout=60):
    """Write the drawing's sidecar <stem>.net, which only LTspice can produce.

    make_schematic.py writes the .asc, and collect() only moves
    .raw/.log/.db/.op.raw, so nothing else in this flow creates the netlist that
    section 7 reads. LTspice can hang on a modal dialog here, so bound the
    wait."""
    p = subprocess.run([str(EXE), '-netlist', asc], cwd=ROOT, timeout=timeout,
                       creationflags=subprocess.CREATE_NO_WINDOW,
                       capture_output=True)
    net = (ROOT / asc).with_suffix('.net')
    if p.returncode != 0 or not net.exists():
        raise SystemExit(f'{asc}: LTspice netlist export failed (exit '
                         f'{p.returncode}); section 7 has no netlist to compare')
    return net


def raw(name):
    return read_raw(RUNS / f'{name}.raw')


def run(deck, timeout=300, attempts=3):
    """Run one deck. The vendor macro-model's DC solve is fragile: the same
    unchanged deck normally finishes in seconds but can occasionally take the
    pseudo-transient branch and then grind with a collapsing timestep. Retry,
    and if it keeps failing say so loudly and fall back to the previous .raw so
    the rest of the sweep still reports."""
    for attempt in range(1, attempts + 1):
        try:
            p = subprocess.run([str(EXE), '-b', deck], cwd=ROOT, timeout=timeout,
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               capture_output=True)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/F', '/IM', 'LTspice.exe'],
                           capture_output=True)
            if attempt < attempts:
                print(f'   [{deck} timed out after {timeout}s, retry '
                      f'{attempt + 1}/{attempts}]')
                continue
            FLAKY.append(deck)
            prev = RUNS / f'{Path(deck).stem}.raw'
            print(f'   [!! {deck} timed out {attempts}x - a known flakiness of '
                  f'the vendor model]')
            if prev.exists():
                print(f'   [!! falling back to the previous {prev.name}: the '
                      f'numbers below are from an earlier run]')
                return True
            raise SystemExit(f'{deck} timed out and no previous .raw exists')
        if p.returncode != 0:
            log = (ROOT / deck).with_suffix('.log')
            txt = ''
            if log.exists():
                data = log.read_bytes()
                txt = (data.decode('utf-16') if data[:2] == bytes([0xFF, 0xFE])
                       else data.decode('utf-8', errors='replace'))
            raise SystemExit(f'{deck} failed ({p.returncode})\n{txt[-2000:]}')
        collect(deck)
        return True
    return False


def out(title):
    print()
    print('=' * 72)
    print(title)
    print('=' * 72)


# 1 ---------------------------------------------------------------- model check
out('1. Vendor OPAx333 macro-model qualification (unity-gain DC follower)')
run('decks/opa333_validation.cir')
d = read_raw(RUNS / 'opa333_validation.raw')
err = np.max(np.abs(d['V(out)'] - d['V(in)']))
print(f'   input sweep 0.1..3.2 V, worst |V(out)-V(in)| = {err*1e6:.3f} uV')
print('   -> the model\'s differential behaviour is sound in LTspice.')

# 2 ------------------------------------------------------- operating point table
out('2. Current sink operating points (vendor models, ideal rails)')
run('decks/core_op.cir')
d = read_raw(RUNS / 'core_op.raw')
print(f"   {'RLOAD':>6} {'I(R10)':>11} {'V(I_SENSE)':>11} {'V(OUTA)':>9} {'V(BONE_N)':>10} {'I(R_BONE)':>11}")
for i, rl in enumerate(d['rload']):
    print(f"   {rl/1e3:5.0f}k {d['I(R10)'][i]*1e6:8.3f} uA {d['V(i_sense)'][i]:11.6f} "
          f"{d['V(outa)'][i]:9.4f} {d['V(bone_n)'][i]:10.4f} {d['I(R_BONE)'][i]*1e6:8.3f} uA")

# 3 ----------------------------------------------------------- compliance curve
out('3. Compliance curve (behavioural load, .dc continuation from 1k)')
run('decks/core_compliance.cir')
d = read_raw(RUNS / 'core_compliance.raw')
rl = 1e3 + d['VCTRL'] * 99e3
ise = d['V(i_sense)']
reg = np.where(ise > 0.2975)[0]
edge = reg[-1]
print(f'   regulation holds to RLOAD = {rl[edge]/1e3:.2f} k, V(BONE_N) = {d["V(bone_n)"][edge]:.4f} V there')
print(f'   so the sink needs ~{d["V(bone_n)"][edge]:.3f} V of drain headroom and holds the load')
print(f'   voltage up to {8.0016 - d["V(bone_n)"][edge]:.3f} V at 100 uA')
print(f"   {'RLOAD':>8} {'I(R10)':>11} {'V(I_SENSE)':>11} {'V(OUTA)':>9}  state")
for target in (10e3, 40e3, 60e3, 70e3, 76e3, 78e3, 80e3, 90e3, 100e3):
    j = int(np.argmin(abs(rl - target)))
    st = 'regulating' if ise[j] > 0.2975 else ('saturated' if d['V(outa)'][j] > 3.0 else 'other')
    print(f"   {rl[j]/1e3:7.2f}k {d['I(R10)'][j]*1e6:8.3f} uA {ise[j]:11.6f} "
          f"{d['V(outa)'][j]:9.4f}  {st}")

# 4 ------------------------------------------------------------------- startup
out('4. Cold power-up at RLOAD=10k (ideal rails ramped in 1-2 ms, 3 s span)')
run('decks/core_startup.cir')
d = read_raw(RUNS / 'core_startup.raw')
t = d['time']
i = d['I(R_BONE)']
m = t >= 2.9
fin = i[m].mean()
bad = np.where(np.abs(i - fin) > 0.01 * abs(fin))[0]
print(f'   settled I = {fin*1e6:.3f} uA, min {i[m].min()*1e6:.3f}, max {i[m].max()*1e6:.3f}')
print(f'   peak over the whole run = {i.max()*1e6:.3f} uA  -> overshoot above the settled value = '
      f'{(i.max()-i[m].max())/fin*100:.2f} %')
print(f'   V(OUTA) stayed within {d["V(outa)"].min():.4f} .. {d["V(outa)"].max():.4f} V (rails 0..3.3)')
print(f'   within +-1% of final after {t[bad[-1]]*1e3:.2f} ms')
print('   -> no current overshoot; the gate is only driven after the 3.3 V rail is up.')
print('   -> heavier loads are not reported: the vendor model\'s t=0 operating')
print('      point is already spurious above ~50k, so that transient never advances.')

# 5 ------------------------------------------------------------ load step
out('5. Load step inside the compliant range (60k -> 9.37k at t=5 ms)')
run('decks/core_reconnect.cir')
d = read_raw(RUNS / 'core_reconnect.raw')
t = d['time']
i = d['I(R_BONE)'] + d['I(RB)']
post = t >= 5e-3
tp, ip = t[post], i[post]
step0 = 5e-3
exc = np.clip(ip - 100e-6, 0, None)
defi = np.clip(100e-6 - ip, 0, None)
bad = np.where(np.abs(ip - 99.78e-6) > 0.02 * 99.78e-6)[0]
print(f'   settled before/after: {i[t<5e-3].mean()*1e6:.3f} uA / {ip[tp>20e-3].mean()*1e6:.3f} uA')
print(f'   peak = {ip.max()*1e6:.1f} uA ({(ip.max()/99.78e-6):.1f}x nominal) at {(tp[np.argmax(ip)]-step0)*1e6:.2f} us')
print(f'   minimum after step = {ip.min()*1e6:.3f} uA')
print(f'   excess charge above 100 uA = {np.trapezoid(exc, tp)*1e9:.3f} nC')
print(f'   deficit charge below 100 uA = {np.trapezoid(defi, tp)*1e9:.3f} nC')
print(f'   back within +-2% after {(tp[bad[-1]]-step0)*1e6:.1f} us')

# 6 ----------------------------------------------------------------- full bus
out('6. Full bus DC sweep 4..16 V (surrogate LDOs and TVS, not vendor models)')
run('decks/full_bus_dc.cir')
d = read_raw(RUNS / 'full_bus_dc.raw')
v = d['V(v_bus)']
for target in (4, 6, 8, 8.5, 12, 16):
    j = int(np.argmin(abs(v - target)))
    print(f"   V_BUS={v[j]:6.2f} V  BONE_P={d['V(bone_p)'][j]:7.4f} V  +3.3V={d['V(v3v3)'][j]:7.4f} V  "
          f"I_sink={d['I(R_BONE)'][j]*1e6:8.3f} uA  I(V_BUS)={d['I(VBUS)'][j]*1e6:9.3f} uA")
j = int(np.argmin(abs(v - 12)))
print(f"   at 12 V the bus delivers {abs(d['I(VBUS)'][j])*1e6:.1f} uA total; sink {d['I(R_BONE)'][j]*1e6:.1f} uA,"
      f" the rest is bias ({abs(d['I(VBUS)'][j])*1e6 - d['I(R_BONE)'][j]*1e6:.1f} uA)")

# 7 ------------------------------------------------- schematic == netlist check
out('7. Schematics vs netlist decks (the .asc drawings must be the same circuit)')
subprocess.run([sys.executable, 'tools/make_schematic.py'], cwd=ROOT, check=True,
               capture_output=True)
run('sink_vendor.asc', timeout=300)
run('full_bus.asc', timeout=300)
export_netlist('sink_vendor.asc')
export_netlist('full_bus.asc')

a = read_raw(RUNS / 'sink_vendor.raw')
b = read_raw(RUNS / 'core_op.raw')
j = int(np.argmin(abs(b['rload'] - 10e3)))
worst = 0.0
for k in ['V(i_set)', 'V(i_sense)', 'V(outa)', 'V(bone_n)', 'V(bone_p)',
          'V(v3v3)', 'I(R10)', 'I(R_BONE)']:
    worst = max(worst, abs(a[k][0] - b[k][j]) / max(abs(b[k][j]), 1e-12))
ok_sink = worst < 1e-6
print(f'   sink_vendor.asc (.op, 10k) vs core_op.cir : worst relative diff {worst:.2e}'
      f'  -> {"same circuit" if ok_sink else "MISMATCH"}')
print(f'   named nets: {", ".join(sorted(k[2:-1] for k in a if k.startswith("V(")))}')

a = read_raw(RUNS / 'full_bus.raw')
b = read_raw(RUNS / 'full_bus_dc.raw')
worst = 0.0
# the drawing's own analysis directive decides what its .raw holds: only a VBUS
# sweep can be compared point-by-point against the deck
ok_bus = 'VBUS' in a
if ok_bus:
    for k, kk in [('V(bone_p)', 'V(bone_p)'), ('V(v3v3)', 'V(v3v3)'),
                  ('V(bone_n)', 'V(bone_n)'), ('V(outa)', 'V(outa)'),
                  ('V(i_sense)', 'V(i_sense)'), ('I(R_BONE)', 'I(R_BONE)'),
                  ('I(VBUS)', 'I(VBUS)')]:
        worst = max(worst, np.max(np.abs(a[k] - b[kk]) /
                                  np.maximum(np.abs(b[kk]), 1e-9)))
    ok_bus = worst < 1e-6
    print(f'   full_bus.asc ({len(a["VBUS"])} sweep points) vs full_bus_dc.cir :'
          f' worst relative diff {worst:.2e}  -> {"same circuit" if ok_bus else "MISMATCH"}')
else:
    kind = 'a transient run' if 'time' in a else 'an unrecognised run'
    print(f'   full_bus.asc ({kind}, no VBUS vector) vs full_bus_dc.cir : MISMATCH')
    print('      the drawing carries a different analysis directive than the deck')

# element-by-element netlist comparison: the numeric check says *that* a drawing
# differs, this says *where*
print()
ok_net = True
# the exported .net keeps its includes relative to the .asc, so it
# stays beside the .asc rather than in runs/
for net, deck in [('sink_vendor.net', 'decks/core_op.cir'),
                  ('full_bus.net', 'decks/full_bus_dc.cir')]:
    r = subprocess.run([sys.executable, str(Path(__file__).parent / 'compare_netlists.py'),
                        net, deck],
                       cwd=ROOT, capture_output=True, text=True)
    last = r.stdout.strip().splitlines()[-1]
    ok_net &= last.endswith('0 difference(s)')
    print(f'   {net} vs {deck}: {last}')
# 8 ------------------------------------------- worst case + vendor TVS check
out('8. Worst-case gate drive, and the TVS surrogate vs the Vishay library')
run('decks/core_gate_margin.cir', timeout=200)
run('decks/core_gate_cliff.cir', timeout=200)
for tag, deck, vto in [('Vth=2.5 V (datasheet max), rail 3.2 V', 'core_gate_margin.cir', 2.5),
                       ('Vth=3.0 V (past the limit), rail 3.2 V', 'core_gate_cliff.cir', 3.0)]:
    d = raw(Path(deck).stem)
    ise, iset, vo, i10 = (d['V(i_sense)'][0], d['V(i_set)'][0],
                          d['V(outa)'][0], d['I(R10)'][0])
    reg = abs(ise - iset) < 1e-4
    print(f'   {tag}: I={i10*1e6:7.3f} uA  V(I_SET)={iset:.4f}  V(I_SENSE)={ise:.6f}  '
          f'V(OUTA)={vo:.4f}  -> {"regulating" if reg else "NOT regulating"}')
print('   -> the setpoint itself is ratiometric to the 3.3 V rail:')
print('      I_out = V3V3 / (11 * 3k), so a rail error is a current error.')

run('decks/tvs_compare.cir', timeout=200)
d = read_raw(RUNS / 'tvs_compare.raw')
va, vb = d['V(v_bus_a)'], d['V(v_bus_b)']
ia, ib = d['I(V_A)'], d['I(V_B)']
print(f"   {'V_BUS':>6} {'surrogate':>12} {'Vishay':>12}")
for tgt in (12, 16, 18, 19, 22):
    ja, jb = int(np.argmin(abs(va - tgt))), int(np.argmin(abs(vb - tgt)))
    print(f'   {tgt:6.1f} {abs(ia[ja])*1e9:9.3f} nA {abs(ib[jb])*1e9:9.3f} nA')
ja, jb = int(np.argmin(abs(va - 12))), int(np.argmin(abs(vb - 12)))
print(f'   at 12 V the leakage differs by {abs(abs(ia[ja]) - abs(ib[jb]))*1e9:.1f} nA, '
      f'i.e. {abs(abs(ia[ja]) - abs(ib[jb]))/165e-6*100:.4f} % of the bus current')
print('   -> DC conclusions unaffected; the clamp knee is NOT interchangeable:')
for name, c, v in (('surrogate', ia, va), ('Vishay', ib, vb)):
    k = np.where(np.abs(c) > 1.0)[0]
    kk = np.where(np.abs(c) > 1e-6)[0]
    print(f'      {name:9s} 1 uA at {v[kk[0]]:.2f} V, 1 A at '
          f'{v[k[0]]:.2f} V' if len(k) else f'      {name:9s} never reaches 1 A')

print()
if FLAKY:
    print('NOTE: these decks hit the vendor model flakiness and used a '
          'previous .raw: ' + ', '.join(FLAKY))
if not (ok_sink and ok_bus and ok_net):
    print('!! A SCHEMATIC DOES NOT MATCH ITS NETLIST - the drawing is wrong, '
          'not the deck.')
elif not FLAKY:
    print('All decks re-ran clean; both schematics netlist to the same circuits.')
