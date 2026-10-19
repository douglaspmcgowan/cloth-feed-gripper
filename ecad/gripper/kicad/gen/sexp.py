"""Minimal S-expression reader/writer for KiCad files (symbols, schematics).

parse(text) -> nested lists; atoms are str. Quoted strings keep their quotes stripped but are
wrapped in Q so the writer can re-quote them. dump(tree) writes KiCad-style indented text.
"""


class Q(str):
    """A quoted string atom."""


def parse(text):
    stack, cur, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '(':
            stack.append(cur)
            cur = []
            i += 1
        elif c == ')':
            done = cur
            cur = stack.pop()
            cur.append(done)
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == '\\':
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            cur.append(Q(''.join(buf)))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()':
                j += 1
            cur.append(text[i:j])
            i = j
    return cur[0] if len(cur) == 1 else cur


def fmt_atom(a):
    if isinstance(a, Q):
        return '"' + a + '"'
    if isinstance(a, float):
        s = ('%.4f' % a).rstrip('0').rstrip('.')
        return '0' if s in ('-0', '') else s
    return str(a)


def dump(tree, indent=0):
    if not isinstance(tree, list):
        return fmt_atom(tree)
    simple = all(not isinstance(x, list) for x in tree)
    if simple:
        return '(' + ' '.join(fmt_atom(x) for x in tree) + ')'
    pad = '\t' * (indent + 1)
    head = []
    rest = []
    for k, x in enumerate(tree):
        if not rest and not isinstance(x, list):
            head.append(fmt_atom(x))
        else:
            rest.append(x)
    out = '(' + ' '.join(head)
    for x in rest:
        out += '\n' + pad + dump(x, indent + 1)
    out += '\n' + '\t' * indent + ')'
    return out


def find(tree, key):
    """First child list whose head is key."""
    for x in tree:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(tree, key):
    return [x for x in tree if isinstance(x, list) and x and x[0] == key]


def load_symbol(lib_path, name):
    """Return the (symbol "name" ...) list from a .kicad_sym file, resolving one level of extends."""
    with open(lib_path, encoding='utf-8') as f:
        lib = parse(f.read())
    syms = {s[1]: s for s in find_all(lib, 'symbol')}
    return _resolve(syms, name)


def _resolve(syms, name):
    sym = syms[name]
    ext = find(sym, 'extends')
    if ext is not None:
        base = [list(x) if isinstance(x, list) else x for x in _resolve(syms, ext[1])]
        base[1] = Q(name)
        # replace properties of the base with the derived ones
        props = {p[1]: p for p in find_all(sym, 'property')}
        merged = []
        for x in base:
            if isinstance(x, list) and x and x[0] == 'property' and x[1] in props:
                merged.append(props.pop(x[1]))
            elif isinstance(x, list) and x and x[0] == 'symbol':
                sub = list(x)
                sub[1] = Q(name + sub[1][sub[1].rfind('_', 0, sub[1].rfind('_')):])
                merged.append(sub)
            elif isinstance(x, list) and x and x[0] == 'extends':
                continue
            else:
                merged.append(x)
        for p in props.values():
            merged.append(p)
        sym = merged
    return sym


def symbol_pins(sym):
    """[(number, name, x, y, angle, length, etype)] in symbol coordinates (y up)."""
    pins = []

    def walk(t):
        for x in t:
            if isinstance(x, list) and x:
                if x[0] == 'pin':
                    at = find(x, 'at')
                    ln = find(x, 'length')
                    nm = find(x, 'name')
                    nb = find(x, 'number')
                    pins.append((str(nb[1]), str(nm[1]), float(at[1]), float(at[2]),
                                 float(at[3]) if len(at) > 3 else 0.0, float(ln[1]), x[1]))
                elif x[0] == 'symbol':
                    walk(x)
    walk(sym)
    return pins
