"""Generate LTspice schematics that mirror the .cir decks, plus the subckt symbols.

The .cir decks are the source of truth; this script only draws them.

The sheet is organised into the same six functional modules as the 嘉立创 PDF
(输入 / 8V稳压 / 3.3V / 恒流调节 / 恒流控制 / BONE负载), each inside its own
rectangle, and the modules are joined by net labels only - which is how the PDF
is drawn too. Text annotations are deliberately absent: LTspice renders
non-ASCII text read from an .asc as mojibake, and they were not wanted.

Layout rules that matter for readability in LTspice itself:
  - LTspice draws a net label's text ALONG its wire, so a label dropped on a
    vertical pin comes out as vertical text. Every power label therefore goes
    through a horizontal stub (Sheet.hlabel).
  - A pin placed outside a symbol box has its name drawn rotated along the pin.
    LTspice's own NE555.asy puts box pins exactly on the box edge, where the
    name is drawn horizontally inside; the box symbols here do the same.
  - Horizontal resistors carry explicit WINDOW attributes (refdes above the
    body, value below), because LTspice's defaults overlap the two strings.
  - The .asc is written in the system codepage (GBK), not UTF-8: LTspice reads
    an .asc byte-wise, so UTF-8 text would be copied into the netlist as
    garbage and can break the parse. Keep this if you ever add text back.

Acceptance test: run the .asc and compare its numbers against the .cir run.

usage: python make_schematic.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent   # ltspice/, where the .asc lives
LTSPICE_LIB = Path(r'C:\Users\Liuxm\AppData\Local\LTspice\lib\sym')

SYMS = {
    'res':               [(16, 16), (16, 96)],
    'cap':               [(16, 0), (16, 64)],
    'voltage':           [(0, 16), (0, 96)],
    'OPAx333':           [(-32, 80), (-32, 48), (0, 32), (0, 96), (32, 64)],
    'N7002':             [(48, 0), (0, 80), (48, 96)],
    'ST715_APPROX':      [(-96, -32), (96, -32), (0, 64), (-96, 32)],
    'MCP1703A33_APPROX': [(-80, 0), (80, 0), (0, 48)],
    'VESD16_APPROX':     [(-48, 0), (48, 0)],
}
PINNAME = {
    'OPAx333': ['In+', 'In-', 'V+', 'V-', 'OUT'],
    'N7002': ['D', 'G', 'S'],
    'ST715_APPROX': ['IN', 'OUT', 'GND', 'FB'],
    'MCP1703A33_APPROX': ['IN', 'OUT', 'GND'],
    'VESD16_APPROX': ['K', 'A'],
}


def rot(px, py, r):
    return {'R0': (px, py), 'R90': (-py, px), 'R180': (-px, -py),
            'R270': (py, -px), 'M0': (-px, py)}[r]


class Sheet:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.body, self.placed = [], {}
        self.segs, self.flags = [], []

    def sym(self, ref, kind, x, y, r='R0', value=None):
        self.placed[ref] = (kind, x, y, r)
        self.body.append(f'SYMBOL {kind} {x} {y} {r}')
        if kind == 'res' and r in ('R90', 'R270'):
            self.body.append('WINDOW 0 0 56 VBottom 2')
            self.body.append('WINDOW 3 32 56 VTop 2')
        self.body.append(f'SYMATTR InstName {ref}')
        if value is not None:
            self.body.append(f'SYMATTR Value {value}')
        return ref

    def pin(self, ref, n):
        kind, x, y, r = self.placed[ref]
        dx, dy = rot(*SYMS[kind][n - 1], r)
        return (x + dx, y + dy)

    def pins(self):
        return {f'{ref}.{n}': self.pin(ref, n)
                for ref, (kind, *_rest) in self.placed.items()
                for n in range(1, len(SYMS[kind]) + 1)}

    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                raise ValueError(f'non-orthogonal wire {a} -> {b}')
            self.body.append(f'WIRE {a[0]} {a[1]} {b[0]} {b[1]}')
            self.segs.append((a, b))

    def ref(self, pt, net):
        self.body.append(f'FLAG {pt[0]} {pt[1]} {net}')
        self.flags.append((tuple(pt), net))

    def hlabel(self, pin, net, dx=48, dy=32):
        """Label a pin through a horizontal stub: LTspice draws a label's text
        along its wire, so a label dropped straight onto a vertical pin renders
        as vertical text."""
        x, y = pin
        self.wire(pin, (x, y + dy), (x + dx, y + dy))
        self.ref((x + dx, y + dy), net)

    def frame(self, x, y, w, h):
        """Module boundary only. Text annotations were removed on request:
        LTspice renders non-ASCII text from the .asc as mojibake anyway."""
        self.body.append(f'RECTANGLE Normal {x} {y} {x + w} {y + h}')

    def directive(self, x, y, text):
        self.body.append(f'TEXT {x} {y} Left 2 !{text}')

    def check(self, label):
        """Catch what LTspice's own geometry scan does not: a pin sitting in the
        interior of another net's wire (which silently shorts the two), and pins
        with nothing attached at all."""
        bad = []
        pins = self.pins()
        for name, p in pins.items():
            touch = sum(1 for a, b in self.segs if p in (a, b))
            touch += sum(1 for f, _ in self.flags if f == p)
            touch += sum(1 for q in pins.values() if q == p) - 1
            if touch == 0:
                bad.append(f'{label}: pin {name} at {p} has nothing attached')
            for a, b in self.segs:
                if not (a[0] == b[0] == p[0] or a[1] == b[1] == p[1]):
                    continue
                lo, hi = sorted((a, b))
                if lo < p < hi:
                    bad.append(f'{label}: pin {name} at {p} sits INSIDE wire '
                               f'{a}-{b} (shorts two nets)')
        for i, (a, b) in enumerate(self.segs):
            for c, d in self.segs[i + 1:]:
                for axis in (0, 1):
                    if not (a[axis] == b[axis] == c[axis] == d[axis]):
                        continue
                    other = 1 - axis
                    if a[other] != b[other] or c[other] != d[other]:
                        continue
                    lo1, hi1 = sorted((a[other], b[other]))
                    lo2, hi2 = sorted((c[other], d[other]))
                    if min(hi1, hi2) > max(lo1, lo2):
                        bad.append(f'{label}: collinear wires overlap: '
                                   f'{a}-{b} and {c}-{d} (shorts two nets)')
        return bad

    def render(self):
        return '\n'.join(['Version 4.1', f'SHEET 1 {self.w} {self.h}']
                         + self.body) + '\n'


def write_symbols():
    box = {'ST715_APPROX': (-96, -64, 96, 64),
           'MCP1703A33_APPROX': (-80, -48, 80, 48),
           'VESD16_APPROX': (-48, -48, 48, 48)}
    for name, (x0, y0, x1, y1) in box.items():
        w0, w3 = (y0 - 40, y0 - 72)   # both above: a pin name is drawn inside
                                      # the box, so keep the outside clear for
                                      # the net-label stubs
        if name == 'VESD16_APPROX':
            w0, w3 = (y1 + 40, y1 + 72)   # TVS sits on a rail: stubs go up
        L = ['Version 4', 'SymbolType BLOCK',
             f'RECTANGLE Normal {x0} {y0} {x1} {y1}',
             f'WINDOW 0 0 {w0} Center 2', f'WINDOW 3 0 {w3} Center 2',
             'SYMATTR Prefix X', f'SYMATTR Value {name}',
             'SYMATTR Description User-created surrogate, see '
             'models/APPROX_NOT_VENDOR.lib - NOT a manufacturer model.']
        for i, (px, py) in enumerate(SYMS[name]):
            side = ('LEFT' if px <= x0 else 'RIGHT' if px >= x1
                    else 'BOTTOM' if py >= y1 else 'TOP')
            L += [f'PIN {px} {py} {side} 8',
                  f'PINATTR PinName {PINNAME[name][i]}',
                  f'PINATTR SpiceOrder {i + 1}']
        (HERE / f'{name}.asy').write_text('\n'.join(L) + '\n', encoding='utf-8')

    # op-amp: LTspice's opamp2 drawing; its pin order already is In+ In- V+ V- OUT.
    # Rewrite Value and Description in place - the PIN definitions sit after
    # Description in opamp2.asy, so truncating the file would drop them.
    L = []
    for ln in (LTSPICE_LIB / 'Opamps' / 'opamp2.asy').read_text(
            encoding='utf-8', errors='replace').splitlines():
        if ln.startswith('SYMATTR Value opamp2'):
            L.append('SYMATTR Value OPAx333')
        elif ln.startswith('SYMATTR Description'):
            L.append('SYMATTR Description TI OPAx333 macro-model '
                     '(models/OPAx333.LIB). Pin order matches '
                     '.SUBCKT OPAx333 IN+ IN- VCC VEE OUT.')
        else:
            L.append(ln)
    (HERE / 'OPAx333.asy').write_text('\n'.join(L) + '\n', encoding='utf-8')

    # MOSFET: Diodes 2N7002 subckt (D G S) drawn with the standard NMOS artwork
    t = (LTSPICE_LIB / 'Contrib' / 'Toshiba' / 'lvmos'
         / 'T2N7002AK_G0_00.asy').read_text(encoding='utf-8', errors='replace')
    L = []
    for ln in t.splitlines():
        if ln.startswith(('SYMATTR Value', 'SYMATTR ModelFile')):
            continue
        if ln.startswith('PINATTR PinName'):
            L.append({'3': 'PINATTR PinName D', '1': 'PINATTR PinName G',
                      '2': 'PINATTR PinName S'}[ln.split()[-1]])
        else:
            L.append(ln)
    L += ['SYMATTR Value N7002',
          'SYMATTR Description Diodes Inc. 2N7002 subckt '
          '(models/2N7002_DIODES.lib), terminals D G S.']
    (HERE / 'N7002.asy').write_text('\n'.join(L) + '\n', encoding='utf-8')


# --------------------------------------------------------------------------
# Layout convention, learned the hard way: LTspice draws a vertical part's
# refdes+value in two lines to its RIGHT (~72 units), a box symbol's texts
# ABOVE it (or below, for the TVS), and a net label's text along its wire.
# Every module below reserves those zones explicitly.
# --------------------------------------------------------------------------

# module 1 - input. The rectifier front end is NOT modelled: the RX coil and
# its excitation were never supplied, so the sheet starts at V_BUS.
def mod_input(s, fx, fy):
    s.frame(fx, fy, 520, 480)
    s.sym('VBUS', 'voltage', fx + 80, fy + 240, 'R0', '12')
    s.wire(s.pin('VBUS', 1), (fx + 80, fy + 200), (fx + 200, fy + 200))
    s.ref((fx + 200, fy + 200), 'V_BUS')
    s.hlabel(s.pin('VBUS', 2), 'PGND', dx=64)
    s.sym('C5', 'cap', fx + 320, fy + 160, 'R0', '1u')
    s.hlabel(s.pin('C5', 1), 'V_BUS', dy=-32)
    s.hlabel(s.pin('C5', 2), 'PGND', dx=112)
    s.sym('C6', 'cap', fx + 320, fy + 320, 'R0', '100n')
    s.hlabel(s.pin('C6', 1), 'V_BUS', dy=-32)
    s.hlabel(s.pin('C6', 2), 'PGND', dx=112)


# module 2 - the 8 V bone rail (ST715CR + feedback divider + TVS)
def mod_bone_rail(s, fx, fy):
    s.frame(fx, fy, 880, 600)
    s.sym('U1', 'ST715_APPROX', fx + 400, fy + 240, 'R0', 'ST715_APPROX')
    s.wire(s.pin('U1', 1), (fx + 160, fy + 208))
    s.ref((fx + 160, fy + 208), 'V_BUS')
    s.hlabel(s.pin('U1', 2), 'BONE_P', dx=64)
    s.hlabel(s.pin('U1', 3), 'PGND', dx=64)
    s.sym('C7', 'cap', fx + 80, fy + 80, 'R0', '100n')
    s.hlabel(s.pin('C7', 1), 'V_BUS', dy=-32)
    s.hlabel(s.pin('C7', 2), 'PGND', dx=112)
    s.sym('C8', 'cap', fx + 520, fy + 120, 'R0', '470n')
    s.hlabel(s.pin('C8', 1), 'BONE_P', dy=-64)
    s.hlabel(s.pin('C8', 2), 'PGND')
    s.sym('D5', 'VESD16_APPROX', fx + 680, fy + 160, 'R0', 'VESD16_APPROX')
    s.hlabel(s.pin('D5', 1), 'V_BUS', dy=-64)
    s.hlabel(s.pin('D5', 2), 'PGND', dy=-32)

    # feedback: BONE_P -R1- FB_TOP -R2- FB -R3- PGND, laid out horizontally
    s.sym('R1', 'res', fx + 400, fy + 504, 'R90', '560k')
    s.sym('R2', 'res', fx + 560, fy + 504, 'R90', '6.8k')
    s.sym('R3', 'res', fx + 720, fy + 504, 'R90', '100k')
    s.wire(s.pin('R1', 2), (fx + 200, fy + 520))
    s.ref((fx + 200, fy + 520), 'BONE_P')
    s.wire(s.pin('R1', 1), s.pin('R2', 2))                  # FB_TOP
    s.wire((fx + 424, fy + 520), (fx + 424, fy + 556))
    s.ref((fx + 424, fy + 556), 'FB_TOP')
    s.wire(s.pin('R2', 1), s.pin('R3', 2))                  # FB
    s.wire((fx + 584, fy + 520), (fx + 584, fy + 556))
    s.ref((fx + 584, fy + 556), 'FB')
    s.wire(s.pin('R3', 1), (fx + 768, fy + 520))
    s.ref((fx + 768, fy + 520), 'PGND')
    s.wire((fx + 584, fy + 520), (fx + 584, fy + 400),
           (fx + 160, fy + 400), (fx + 160, fy + 272), s.pin('U1', 4))


# module 3 - the 3.3 V reference rail (MCP1703AT) and the PGND/GND tie
def mod_v33(s, fx, fy):
    s.frame(fx, fy, 560, 480)
    s.sym('U2', 'MCP1703A33_APPROX', fx + 280, fy + 248, 'R0',
          'MCP1703A33_APPROX')
    s.wire(s.pin('U2', 1), (fx + 80, fy + 248))
    s.ref((fx + 80, fy + 248), 'BONE_P')
    s.hlabel(s.pin('U2', 2), 'V3V3', dx=64)
    s.hlabel(s.pin('U2', 3), 'PGND', dx=64)
    s.sym('C9', 'cap', fx + 24, fy + 64, 'R0', '100n')
    s.hlabel(s.pin('C9', 1), 'BONE_P', dy=-32)
    s.hlabel(s.pin('C9', 2), 'PGND', dy=64)
    s.sym('C10', 'cap', fx + 380, fy + 64, 'R0', '1u')
    s.hlabel(s.pin('C10', 1), 'V3V3', dy=-32)
    s.hlabel(s.pin('C10', 2), 'PGND')
    s.sym('R4', 'res', fx + 280, fy + 400, 'R90', '1m')
    s.ref(s.pin('R4', 2), '0')
    s.wire(s.pin('R4', 1), (fx + 328, fy + 416))
    s.ref((fx + 328, fy + 416), 'PGND')


# module 4 - current setpoint
def mod_current_set(s, fx, fy, ideal=True):
    s.frame(fx, fy, 600, 600)
    s.sym('R5', 'res', fx + 176, fy + 120, 'R0', '100k')
    s.sym('R7', 'res', fx + 176, fy + 340, 'R0', '10k')
    s.wire(s.pin('R5', 2), (fx + 192, fy + 296))                # DIV
    s.wire((fx + 192, fy + 296), s.pin('R7', 1))
    s.wire((fx + 192, fy + 296), (fx + 144, fy + 296))
    s.ref((fx + 144, fy + 296), 'DIV')
    s.ref(s.pin('R7', 2), '0')
    if ideal:
        s.sym('V33', 'voltage', fx + 64, fy + 320, 'R0', '3.3')
        s.wire(s.pin('V33', 1), (fx + 64, fy + 136), s.pin('R5', 1))
        s.ref(s.pin('V33', 2), '0')
    else:
        s.wire(s.pin('R5', 1), (fx + 176, fy + 136), (fx + 64, fy + 136))
    s.ref((fx + 112, fy + 136), 'V3V3')
    s.sym('R6', 'res', fx + 400, fy + 280, 'R90', '10k')
    s.wire((fx + 192, fy + 296), s.pin('R6', 2))                # DIV -> R6
    s.sym('C12', 'cap', fx + 480, fy + 360, 'R0', '100n')
    s.wire(s.pin('R6', 1), (fx + 496, fy + 296), s.pin('C12', 1))
    s.ref((fx + 440, fy + 296), 'I_SET')
    s.ref(s.pin('C12', 2), '0')


# module 5 - the control loop (OPA333, compensation, gate resistor)
def mod_control(s, fx, fy):
    s.frame(fx, fy, 720, 600)
    s.sym('U3', 'OPAx333', fx + 280, fy + 200, 'R0', 'OPAx333')
    s.wire(s.pin('U3', 1), (fx + 128, fy + 280))                # In+
    s.ref((fx + 128, fy + 280), 'I_SET')
    s.wire(s.pin('U3', 3), (fx + 280, fy + 200), (fx + 344, fy + 200))
    s.ref((fx + 344, fy + 200), 'V3V3')
    s.ref(s.pin('U3', 4), '0')
    s.sym('C13', 'cap', fx + 500, fy + 80, 'R0', '100n')
    s.hlabel(s.pin('C13', 1), 'V3V3', dy=-32)
    s.ref(s.pin('C13', 2), '0')

    # OUTA node: op-amp out -> C14 tap -> R8
    s.wire(s.pin('U3', 5), (fx + 416, fy + 264), (fx + 504, fy + 264))
    s.ref((fx + 352, fy + 264), 'OUTA')
    s.sym('C14', 'cap', fx + 400, fy + 320, 'R0', '100p')
    s.wire((fx + 416, fy + 264), s.pin('C14', 1))
    s.wire(s.pin('C14', 2), (fx + 416, fy + 480))
    s.sym('R8', 'res', fx + 600, fy + 248, 'R90', '10k')
    s.wire(s.pin('R8', 2), (fx + 504, fy + 264))
    s.wire(s.pin('R8', 1), (fx + 620, fy + 264))
    s.ref((fx + 620, fy + 264), 'STIM_GATE')

    # I_SENSE rail
    s.wire(s.pin('U3', 2), (fx + 80, fy + 248), (fx + 80, fy + 480),
           (fx + 416, fy + 480), (fx + 520, fy + 480))
    s.ref((fx + 120, fy + 480), 'I_SENSE')


# module 6 - bone load. R_BONE is the tissue: it is drawn IN the current path,
# from BONE_P down to the MOSFET drain, with one BONE_N label on that wire.
def mod_bone_load(s, fx, fy, ideal=True):
    s.frame(fx, fy, 600, 600)
    s.sym('R_BONE', 'res', fx + 400, fy + 80, 'R0', '10k')
    s.hlabel(s.pin('R_BONE', 1), 'BONE_P', dy=-32)
    s.sym('Q1', 'N7002', fx + 400, fy + 240, 'R0', 'N7002')
    s.wire(s.pin('R_BONE', 2), (fx + 416, fy + 208), (fx + 448, fy + 208),
           s.pin('Q1', 1))
    s.ref((fx + 432, fy + 208), 'BONE_N')
    s.wire(s.pin('Q1', 2), (fx + 400, fy + 352))
    s.wire((fx + 400, fy + 352), (fx + 336, fy + 352))
    s.ref((fx + 336, fy + 352), 'STIM_GATE')
    s.sym('R9', 'res', fx + 384, fy + 368, 'R0', '10Meg')
    s.wire((fx + 400, fy + 352), s.pin('R9', 1))
    s.wire(s.pin('R9', 2), (fx + 400, fy + 520))
    s.wire(s.pin('Q1', 3), (fx + 448, fy + 520))
    s.sym('R10', 'res', fx + 480, fy + 504, 'R0', '3k')
    s.ref(s.pin('R10', 2), '0')
    s.wire((fx + 200, fy + 520), (fx + 400, fy + 520), (fx + 448, fy + 520),
           s.pin('R10', 1))
    s.ref((fx + 200, fy + 520), 'I_SENSE')
    if ideal:
        s.sym('V8', 'voltage', fx + 160, fy + 80, 'R0', '8.0016')
        s.wire(s.pin('V8', 1), (fx + 160, fy + 96), s.pin('R_BONE', 1))
        s.ref(s.pin('V8', 2), '0')
    else:
        s.wire(s.pin('R_BONE', 1), (fx + 416, fy + 64), (fx + 480, fy + 64))


SINK_SAVE = ('.save V(V3V3) V(BONE_P) V(BONE_N) V(I_SET) V(I_SENSE) '
             'V(OUTA) V(STIM_GATE) I(R_BONE) I(R10)')
FULL_SAVE = ('.save V(V_BUS) V(BONE_P) V(V3V3) V(I_SET) V(I_SENSE) '
             'V(OUTA) V(BONE_N) I(R_BONE) I(VBUS)')
SINK_DIRECTIVES = ['.include models/OPAx333.LIB',
                   '.include models/2N7002_DIODES.lib',
                   '.include inc/solver.inc']
FULL_DIRECTIVES = ['.include models/OPAx333.LIB',
                   '.include models/2N7002_DIODES.lib',
                   '.include models/APPROX_NOT_VENDOR.lib',
                   '.include inc/solver.inc']


def build_sink():
    """Current sink with the vendor models and ideal rails: modules 4, 5, 6."""
    s = Sheet(2100, 900)
    mod_current_set(s, 100, 100, ideal=True)
    mod_control(s, 740, 100)
    mod_bone_load(s, 1500, 100, ideal=True)
    for i, t in enumerate(SINK_DIRECTIVES + ['.op', SINK_SAVE,
                                             '.options plotwinsize=0 numdgt=7']):
        s.directive(100, 740 + i * 32, t)
    (HERE / 'sink_vendor.asc').write_text(s.render(), encoding='gbk')
    return s


def build_full_bus():
    """Whole chain, modules 1-6, with the surrogate regulators."""
    s = Sheet(2200, 1580)
    mod_input(s, 100, 100)
    mod_bone_rail(s, 660, 100)
    mod_v33(s, 1580, 100)
    mod_current_set(s, 100, 760, ideal=False)
    mod_control(s, 740, 760)
    mod_bone_load(s, 1500, 760, ideal=False)
    for i, t in enumerate(FULL_DIRECTIVES + ['.dc VBUS 4 16 0.25', FULL_SAVE,
                                             '.options plotwinsize=0 numdgt=7']):
        s.directive(100, 1400 + i * 32, t)
    (HERE / 'full_bus.asc').write_text(s.render(), encoding='gbk')
    return s


if __name__ == '__main__':
    write_symbols()
    problems = build_sink().check('sink_vendor.asc') + \
        build_full_bus().check('full_bus.asc')
    for p in problems:
        print('PROBLEM', p)
    print(f'wrote .asy symbols, sink_vendor.asc, full_bus.asc; '
          f'{len(problems)} geometry problem(s)')
