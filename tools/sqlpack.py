"""sqlpack: makes SQL files small without changing the rows they make. Merges consecutive INSERTs into the same table
(same verb, same columns) into multi-row INSERTs, groups rows by which columns are at the table default and leaves
those columns out, writes numbers short (1 not 1.0000) and leaves out spaces. For tables without an auto-increment
column, big groups go through a temporary copy of the table: @VAR+number columns get only the number (the variable is
added there), and columns with one value, or the same value as an earlier column, in every row are filled by an
UPDATE. Everything that is not an INSERT ... VALUES stays as it is.
defaults.json: table -> column -> [kind ('num', 'str' or 'auto'), default literal or null], from information_schema.
usage: sqlpack.py defaults.json in.sql out.sql   (or import it: Shrinker(defaults).pack(table, cols, rows))"""
import json, re, sys

MAXSTMT = 900_000   # bytes per statement (well under any max_allowed_packet)
VAR = re.compile(r'^@(\w+)\+(\d+)$')
NUM = re.compile(r'^-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$')


def statements(s):
    """Yield (kind, text): 'stmt' up to and with ';' or 'gap' (whitespace and comments between statements)."""
    i, n = 0, len(s)
    start = 0
    in_stmt = False
    while i < n:
        c = s[i]
        if not in_stmt:
            if c in ' \t\r\n':
                i += 1; continue
            if s.startswith('--', i) or c == '#':
                j = s.find('\n', i); i = n if j < 0 else j + 1; continue
            if s.startswith('/*', i):
                j = s.find('*/', i); i = n if j < 0 else j + 2; continue
            if i > start:
                yield 'gap', s[start:i]
            start = i; in_stmt = True
        if c == "'" or c == '"' or c == '`':
            q = c; i += 1
            while i < n:
                if s[i] == '\\' and q != '`': i += 2; continue
                if s[i] == q:
                    if i + 1 < n and s[i + 1] == q: i += 2; continue
                    break
                i += 1
            i += 1; continue
        if c == '-' and s.startswith('-- ', i):
            j = s.find('\n', i); i = n if j < 0 else j + 1; continue
        if c == ';':
            i += 1
            yield 'stmt', s[start:i]
            start = i; in_stmt = False
            continue
        i += 1
    if start < n:
        yield ('stmt' if in_stmt else 'gap'), s[start:]


def split_top(s, sep=','):
    """Split at top-level sep (outside quotes and parentheses)."""
    out, depth, i, last, n = [], 0, 0, 0, len(s)
    while i < n:
        c = s[i]
        if c in "'\"":
            q = c; i += 1
            while i < n:
                if s[i] == '\\': i += 2; continue
                if s[i] == q:
                    if i + 1 < n and s[i + 1] == q: i += 2; continue
                    break
                i += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == sep and depth == 0:
            out.append(s[last:i]); last = i + 1
        i += 1
    out.append(s[last:])
    return out


def tuples(s):
    """The (...) groups of a VALUES list."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '(':
            depth, j = 0, i
            while j < n:
                cj = s[j]
                if cj in "'\"":
                    q = cj; j += 1
                    while j < n:
                        if s[j] == '\\': j += 2; continue
                        if s[j] == q:
                            if j + 1 < n and s[j + 1] == q: j += 2; continue
                            break
                        j += 1
                elif cj == '(':
                    depth += 1
                elif cj == ')':
                    depth -= 1
                    if depth == 0: break
                j += 1
            out.append(s[i + 1:j]); i = j + 1
        elif c in ' \t\r\n,':
            i += 1
        elif s.startswith('/*', i):
            i = s.index('*/', i) + 2
        else:
            raise ValueError('bad VALUES near: ' + s[i:i + 80])
    return out


INS = re.compile(r'^(INSERT(?:\s+IGNORE)?|REPLACE)\s+INTO\s+`?(\w+)`?\s*\(([^)]*)\)\s*VALUES\s*(.*);$', re.S | re.I)


def short_num(v):
    if not NUM.match(v) or 'e' in v.lower():
        return v
    if '.' in v:
        v = v.rstrip('0').rstrip('.')
        if v in ('', '-'): v = '0'
        if v.startswith('-.'): v = '-0' + v[1:]
        if v.startswith('.'): v = '0' + v
    if v == '-0':
        return None   # keep the original form: negative zero
    return v


class Shrinker:
    def __init__(self, defaults):
        self.defaults = defaults   # table -> column -> (kind, default literal or None)

    def is_default(self, table, col, v):
        d = self.defaults.get(table, {}).get(col)
        if not d:
            return False
        kind, lit = d
        if lit is None:
            return False
        if lit == 'NULL':
            return v.upper() == 'NULL'
        if kind in ('num', 'auto'):
            if not NUM.match(v):
                return False
            try:
                return float(v) == float(lit)
            except ValueError:
                return False
        return v == lit   # strings: exact literal

    def norm(self, table, col, v):
        v = v.strip()
        d = self.defaults.get(table, {}).get(col)
        if d and d[0] == 'num' and NUM.match(v):
            s = short_num(v)
            return v if s is None else s
        return v

    def emit(self, verb, table, cols, rows):
        """Rows grouped by which of the mostly-default columns are at their default (rows of a group share one column
        list). Tables with an auto-increment column keep their row order (one group)."""
        tdef = self.defaults.get(table, {})
        n = len(rows)
        isdef = [[self.is_default(table, c, r[k]) for k, c in enumerate(cols)] for r in rows]
        cand = []
        if not any(v[0] == 'auto' for v in tdef.values()) and n >= 40:
            cand = [k for k in range(len(cols)) if sum(d[k] for d in isdef) * 2 > n]
        groups = {}
        for r, d in zip(rows, isdef):
            groups.setdefault(tuple(k for k in cand if d[k]), []).append(r)
        small = [m for m, g in groups.items() if len(g) < 30 and m]
        if small:
            rest = groups.setdefault((), [])
            for m in small:
                rest.extend(groups.pop(m))
        out = []
        for m, g in groups.items():
            out.append(self.emit_group(verb, table, cols, g))
        return '\n'.join(x for x in out if x)

    def emit_group(self, verb, table, cols, rows):
        out, chunk, size = [], [], 0
        def flush():
            if not chunk: return
            keep = [k for k, c in enumerate(cols) if not all(self.is_default(table, c, r[k]) for r in chunk)]
            if not keep: keep = [0]
            # Through a temporary copy of the table (not for tables with an auto-increment column): columns that are
            # @VAR+number in every row get only the number, and the variable is added there; columns with one value
            # in every row, or the same value as an earlier column in every row, are filled there by an UPDATE.
            tdef = self.defaults.get(table, {})
            var, const, copy = {}, {}, {}
            if len(chunk) >= 50 and not any(v[0] == 'auto' for v in tdef.values()):
                for k in keep:
                    ms = [VAR.match(r[k]) for r in chunk]
                    if all(ms) and len({m.group(1) for m in ms}) == 1:
                        var[k] = ms[0].group(1)
                hasdef = lambda k: tdef.get(cols[k], (None, None))[1] is not None
                for k in keep:
                    if k in var or not hasdef(k):
                        continue
                    first = chunk[0][k]
                    if all(r[k] == first for r in chunk):
                        const[k] = first
                        continue
                    for j in keep:
                        if j >= k: break
                        if j in var or j in const or j in copy: continue
                        if all(r[k] == r[j] for r in chunk):
                            copy[k] = j; break
            if var or const or copy:
                ins = [k for k in keep if k not in const and k not in copy]
                body = ',\n'.join('(' + ','.join(VAR.match(r[k]).group(2) if k in var else r[k] for k in ins) + ')' for r in chunk)
                sets = ['`%s`=`%s`+@%s' % (cols[k], cols[k], v) for k, v in var.items()]
                sets += ['`%s`=%s' % (cols[k], v) for k, v in const.items()]
                sets += ['`%s`=`%s`' % (cols[k], cols[j]) for k, j in copy.items()]
                out.append('CREATE TEMPORARY TABLE `tmp_shrink` LIKE `%s`;\n' % table
                           + 'INSERT INTO `tmp_shrink` (%s) VALUES\n' % ','.join('`%s`' % cols[k] for k in ins) + body + ';\n'
                           + 'UPDATE `tmp_shrink` SET ' + ','.join(sets) + ';\n'
                           + '%s INTO `%s` SELECT * FROM `tmp_shrink`;\nDROP TEMPORARY TABLE `tmp_shrink`;' % (verb, table))
                return
            head = '%s INTO `%s` (%s) VALUES\n' % (verb, table, ','.join('`%s`' % cols[k] for k in keep))
            out.append(head + ',\n'.join('(' + ','.join(r[k] for k in keep) + ')' for r in chunk) + ';')
        for r in rows:
            ln = sum(len(x) + 1 for x in r) + 3
            if chunk and size + ln > MAXSTMT:
                flush(); chunk, size = [], 0
            chunk.append(r); size += ln
        flush()
        return '\n'.join(out)

    def pack(self, table, cols, rows, verb='INSERT'):
        """rows: lists of SQL literals (strings). Returns the statements, ending with a newline."""
        return self.emit(verb, table, cols, [[self.norm(table, c, v) for c, v in zip(cols, r)] for r in rows]) + '\n'

    def run(self, src):
        out = []
        pend = None      # (verb, table, cols, rows)
        pend_gaps = []
        def close():
            nonlocal pend
            if pend:
                out.extend(pend_gaps_before)
                out.append(self.emit(*pend))
                pend = None
        pend_gaps_before = []
        for kind, text in statements(src):
            if kind == 'gap':
                g = text.strip('\n')
                if pend is not None:
                    if g.strip(): pend_gaps.append(g)   # comment between two INSERTs: keep it, before the merge
                else:
                    if g.strip(): out.append(g)
                continue
            m = INS.match(text.strip())
            if m:
                verb = ' '.join(m.group(1).upper().split())
                table = m.group(2)
                cols = [c.strip().strip('`') for c in m.group(3).split(',')]
                rows = []
                for t in tuples(m.group(4)):
                    vals = split_top(t)
                    assert len(vals) == len(cols), (table, len(vals), len(cols), t[:200])
                    rows.append([self.norm(table, c, v) for c, v in zip(cols, vals)])
                if pend and pend[0] == verb and pend[1] == table and pend[2] == cols:
                    pend[3].extend(rows)
                    out.extend(pend_gaps); pend_gaps.clear()
                else:
                    if pend:
                        out.append(self.emit(*pend)); pend = None
                    out.extend(pend_gaps); pend_gaps.clear()
                    pend = (verb, table, cols, rows)
                continue
            if pend:
                out.append(self.emit(*pend)); pend = None
            out.extend(pend_gaps); pend_gaps.clear()
            out.append(text.strip())
        if pend:
            out.append(self.emit(*pend))
        out.extend(pend_gaps)
        return '\n'.join(out) + '\n'


if __name__ == '__main__':
    defaults = {t: {c: tuple(v) for c, v in cs.items()} for t, cs in json.load(open(sys.argv[1])).items()}
    src = open(sys.argv[2], encoding='utf8').read()
    res = Shrinker(defaults).run(src)
    open(sys.argv[3], 'w', encoding='utf8').write(res)
    print(sys.argv[2], len(src.encode()), '->', len(res.encode()))
