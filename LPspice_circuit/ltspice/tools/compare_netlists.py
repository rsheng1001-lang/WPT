"""Compare a schematic's exported netlist against a .cir deck, element by element.

The numeric equivalence check tells you *that* a drawing differs; this tells you
*where*. It flattens .include files and .param values, then matches elements by
instance name.

usage: python compare_netlists.py <exported.net> <deck.cir> [more.cir ...]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # ltspice/


def strip_comments(text):
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith('*'):
            continue
        s = s.split(';')[0].rstrip()          # trailing comment
        out.append(s)
    return out


PASS1 = {}


def load(path, params=None, seen=None):
    """Flatten a netlist, following .include, substituting {PARAM}."""
    params = dict(params or {})
    seen = seen or set()
    path = Path(path)
    if path in seen:
        return []
    seen.add(path)
    lines = []
    depth = 0
    for s in strip_comments(path.read_text(encoding='utf-8', errors='replace')):
        low = s.lower()
        if low.startswith('.include') or low.startswith('.inc'):
            rel = s.split(None, 1)[1].strip().strip('"')
            lines += load(path.parent / rel, params, seen)
            continue
        if low.startswith('.param'):
            for kv in s.split(None, 1)[1].split():
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    params[k.strip().lower()] = v.strip()
                    PASS1[k.strip().lower()] = v.strip()
            continue
        if low.startswith('.subckt'):
            depth += 1
            continue
        if low.startswith('.ends'):
            depth = max(0, depth - 1)
            continue
        if depth:                 # inside a subckt definition: not top level
            continue
        if low.startswith(('.step', '.meas', '.tran', '.op', '.dc', '.ac',
                           '.save', '.options', '.end', '.nodeset', '.ic',
                           '.model', '.func', '.temp')):
            continue
        for k, v in params.items():
            s = re.sub(r'\{' + k + r'\}', v, s, flags=re.I)
        lines.append(s)
    return lines


def parse(lines):
    """element name -> (sorted nodes, value string)."""
    els = {}
    for s in lines:
        t = s.replace('\t', ' ').split()
        if len(t) < 3:
            continue
        name = t[0].replace('§', '')          # LTspice marks schematic X parts
        rest = t[1:]
        kind = name[0].upper()
        # node count by device kind
        nn = {'R': 2, 'C': 2, 'L': 2, 'V': 2, 'I': 2, 'D': 2, 'B': 2,
              'X': None, 'M': 4, 'Q': 4, 'S': 4, 'E': 4, 'G': 4, 'F': 2,
              'H': 2}.get(kind)
        if nn is None:
            # subckt call: '<nodes...> <subcktname> [PARAMS: ...]'
            cut = next((i for i, x in enumerate(rest)
                        if x.lower().startswith('params:')), len(rest))
            body = rest[:cut]
            nodes, tail = body[:-1], body[-1:] + rest[cut:]
        else:
            nodes, tail = rest[:nn], rest[nn:]
        val = ' '.join(tail).replace('µ', 'u').replace('μ', 'u')
        els[name.lower()] = (sorted(nodes), val)
    return els


def main():
    exported, *decks = sys.argv[1:]
    want = {}
    for d in decks:
        load(ROOT / d)                        # pass 1: gather .param values
        for k, v in parse(load(ROOT / d, params=PASS1)).items():
            want[k] = v
    got = parse(load(ROOT / exported))
    bad = 0
    for k in sorted(set(want) | set(got)):
        if k not in got:
            print(f'MISSING in schematic : {k}  {want[k]}')
            bad += 1
        elif k not in want:
            print(f'EXTRA in schematic   : {k}  {got[k]}')
            bad += 1
        elif want[k] != got[k]:
            print(f'DIFFERENT            : {k}\n    deck      {want[k]}\n'
                  f'    schematic {got[k]}')
            bad += 1
    print(f'{len(want)} elements expected, {len(got)} drawn, {bad} difference(s)')


if __name__ == '__main__':
    main()
