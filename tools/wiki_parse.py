#!/usr/bin/env python3
"""Turn the extracted footballer pages into per-player records.

For each page with a football biography infobox:
  - senior men's international caps/goals per national team (from the infobox)
  - league apps/goals per season and division (from the 'Career statistics' club table)
  - infobox club spells (fallback when there is no career table)
Writes players.jsonl.gz
"""
import glob, gzip, json, re, sys, html

INFOBOX = re.compile(r'\{\{\s*[Ii]nfobox[ _]football[ _]biography')
REF = re.compile(r'<ref[^>/]*/>|<ref[^>]*>.*?</ref>', re.S)
COMMENT = re.compile(r'<!--.*?-->', re.S)
LINK = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]*))?\]\]')


def strip_refs(s):
    return REF.sub('', COMMENT.sub('', s))


def template_body(x, start):
    """Return the text of the template starting at index start (balanced braces)."""
    depth, i = 0, start
    while i < len(x) - 1:
        two = x[i:i + 2]
        if two == '{{':
            depth += 1; i += 2; continue
        if two == '}}':
            depth -= 1; i += 2
            if depth == 0:
                return x[start:i]
            continue
        i += 1
    return x[start:]


def split_params(body):
    """Top-level |name = value params of a template."""
    body = body[2:-2]
    out, depth, cur = [], 0, []
    i = 0
    while i < len(body):
        c2 = body[i:i + 2]
        if c2 in ('{{', '[['):
            depth += 1; cur.append(c2); i += 2; continue
        if c2 in ('}}', ']]'):
            depth -= 1; cur.append(c2); i += 2; continue
        if body[i] == '|' and depth == 0:
            out.append(''.join(cur)); cur = []; i += 1; continue
        cur.append(body[i]); i += 1
    out.append(''.join(cur))
    params = {}
    for p in out[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            params[k.strip().lower()] = v.strip()
    return params


def num(s):
    if s is None:
        return None
    s = unwrap(strip_refs(s))
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    s = s.replace("'''", '').replace("''", '').replace(',', '')
    m = re.search(r'\(?\s*(\d{1,4})\s*\)?', s)
    return int(m.group(1)) if m else None


def link_target(s):
    m = LINK.search(s or '')
    if m:
        return m.group(1).strip(), (m.group(2) or m.group(1)).strip()
    t = re.sub(r"'''?|\{\{[^{}]*\}\}", '', unwrap(s or '')).strip()
    return None, t


UNWRAP = re.compile(r'\{\{\s*(?:nowrap|nobr|small|big|center|centre|hs)\s*\|([^{}]*)\}\}', re.I)


def unwrap(s):
    for _ in range(3):
        s = UNWRAP.sub(lambda m: m.group(1), s)
    return s


def plain(s):
    s = unwrap(strip_refs(s or ''))
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    return re.sub(r"'''?|<[^>]+>", '', s).strip()


YEAR = re.compile(r'(\d{4})')


def years(s):
    ys = [int(y) for y in YEAR.findall(plain(s))]
    if not ys:
        return None, None
    s2 = plain(s)
    end = ys[-1] if len(ys) > 1 else (None if re.search(r'[–-]\s*$', s2) else ys[0])
    return ys[0], end


YOUTH_TEAM = re.compile(r'under-\d|\bU-?\d{2}\b|\bU\d{2}\b|olympic|\bB\b|amateur|youth|universit|women|futsal|beach|Under \d|semi-pro|\bC\b|XI|League XI|olympique', re.I)


def infobox(x):
    m = INFOBOX.search(x)
    if not m:
        return None
    p = split_params(template_body(x, m.start()))
    rec = {'name': plain(p.get('name', '')), 'birth': None, 'clubs': [], 'intl': []}
    bd = p.get('birth_date', '') + ' ' + p.get('birth date', '')
    bm = re.search(r'(1[89]\d\d|20[0-2]\d)', bd)
    rec['birth'] = int(bm.group(1)) if bm else None
    rec['pos'] = plain(p.get('position', ''))[:40]
    rec['female'] = bool(re.search(r"women's|women ", p.get('nationalteam1', '') + p.get('nationalteam2', '') + p.get('clubs1', ''), re.I))
    for i in range(1, 60):
        c = p.get('clubs%d' % i)
        if c is None:
            if i > 3 and p.get('clubs%d' % (i + 1)) is None:
                break
            continue
        tgt, disp = link_target(c)
        y0, y1 = years(p.get('years%d' % i, ''))
        rec['clubs'].append({'club': tgt or disp, 'loan': '→' in c or '(loan)' in c, 'y0': y0, 'y1': y1,
                             'apps': num(p.get('caps%d' % i)), 'goals': num(p.get('goals%d' % i))})
    for i in range(1, 40):
        t = p.get('nationalteam%d' % i)
        if t is None:
            if i > 3 and p.get('nationalteam%d' % (i + 1)) is None:
                break
            continue
        tgt, disp = link_target(t)
        full = (tgt or '') + ' ' + disp
        if YOUTH_TEAM.search(full):
            continue
        y0, y1 = years(p.get('nationalyears%d' % i, ''))
        rec['intl'].append({'team': tgt or disp, 'disp': disp, 'y0': y0, 'y1': y1,
                            'caps': num(p.get('nationalcaps%d' % i)), 'goals': num(p.get('nationalgoals%d' % i))})
    return rec


# ---- career statistics table ----
SEASON = re.compile(r'(?<!\d)(1[89]\d\d|20[0-2]\d)(?:\s*[–\-/]\s*(\d{2,4}))?(?!\d)')


def club_table(x):
    """Find the club career statistics table: the first wikitable after a 'Career statistics' / 'Club' heading
    whose header mentions League and Apps."""
    h = re.search(r'==+\s*(Career statistics|Club statistics|Statistics|Career stats)\s*==+', x, re.I)
    pos = h.end() if h else 0
    for m in re.finditer(r'\{\|', x[pos:]):
        st = pos + m.start()
        en = x.find('\n|}', st)
        if en < 0:
            return None
        t = x[st:en]
        head = strip_refs(t[:20000])[:2500].lower()
        if 'apps' in head and ('league' in head or 'division' in head):
            return t
        if m.start() > 60000:
            break
    return None


def cells_of(row):
    """Split a wikitext table row into cells, keeping rowspan counts."""
    lines = [l for l in row.split('\n') if l.strip()]
    cells = []
    for l in lines:
        l = l.strip()
        if l.startswith('|+') or l.startswith('{|'):
            continue
        if l[0] in '|!':
            sep = '||' if l[0] == '|' else '!!'
            parts = re.split(r'\|\||!!', l[1:])
            for p in parts:
                cells.append(p)
        elif cells:
            cells[-1] += '\n' + l
    out = []
    for c in cells:
        attrs, val = '', c
        # "attr=... | value" — split on a single | outside links/templates
        depth = 0
        for i, ch in enumerate(c):
            if c[i:i + 2] in ('[[', '{{'):
                depth += 1
            elif c[i:i + 2] in (']]', '}}'):
                depth -= 1
            elif ch == '|' and depth == 0:
                attrs, val = c[:i], c[i + 1:]
                break
        rs = re.search(r'rowspan\s*=\s*"?(\d+)', attrs)
        cs = re.search(r'colspan\s*=\s*"?(\d+)', attrs)
        if not ('=' in attrs and re.search(r'(style|span|class|align|width|bgcolor)\s*=', attrs)):
            val, rs, cs = c, None, None
        out.append({'v': val.strip(), 'rs': int(rs.group(1)) if rs else 1, 'cs': int(cs.group(1)) if cs else 1})
    return out


FILL = '\x00—'


def season_rows(t):
    """Yield (club, season_start, division_target, division_text, apps, goals) for each season row."""
    rows = re.split(r'\n\|-[^\n]*', t)
    carry = []  # [(col, value, remaining)]
    res = []
    for row in rows[1:]:
        cells = cells_of(row)
        if not cells:
            continue
        # rebuild full row with rowspan carry-over
        full, ci, col = [], 0, 0
        carry = [c for c in carry if c[2] > 0]
        cmap = {c[0]: c for c in carry}
        while ci < len(cells) or col in cmap:
            if col in cmap:
                c = cmap[col]; full.append(c[1]); c[2] -= 1; col += 1; continue
            c = cells[ci]; ci += 1
            for k in range(c['cs']):
                full.append(c['v'] if k == 0 else FILL)
                if c['rs'] > 1:
                    carry.append([col, c['v'], c['rs'] - 1])
                col += 1
        res.append(full)
    out = []
    for full in res:
        # find a season cell then a division cell followed by two numbers
        si = None
        for i, v in enumerate(full[:4]):
            if v is FILL:
                continue
            pv = plain(re.sub(r'^!\s*(?:colspan|rowspan)\s*=\s*"?\d+"?\s*\|', '', v.lstrip('!')))
            if SEASON.fullmatch(pv.strip()) or re.fullmatch(r'\s*(1[89]\d\d|20[0-2]\d)\s*[–\-/]\s*\d{2,4}\s*', pv) or re.fullmatch(r'\s*(1[89]\d\d|20[0-2]\d)\s*', pv):
                si = i; break
        if si is None:
            continue
        sm = SEASON.search(plain(full[si]))
        season = int(sm.group(1))
        rest = [v for v in full[si + 1:si + 7] if v is not FILL]
        if len(rest) < 3:
            continue
        div = rest[0]
        a, g = num(rest[1]), num(rest[2])
        if a is None:
            continue
        tgt, disp = link_target(div)
        prev = [v for v in full[:si] if v is not FILL]
        club = plain(prev[-1]) if prev else ''
        ctgt, _ = link_target(prev[-1]) if prev else (None, '')
        out.append([ctgt or club, season, tgt, plain(div), a, g or 0])
    return out


def main():
    files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else 'out/chunk_*.jsonl.gz'))
    n = kept = withtab = 0
    with gzip.open('players.jsonl.gz', 'wt', encoding='utf-8') as out:
        for f in files:
            for line in gzip.open(f, 'rt', encoding='utf-8'):
                n += 1
                r = json.loads(line)
                x = r['x']
                try:
                    ib = infobox(x)
                except Exception:
                    ib = None
                if not ib:
                    continue
                rec = {'title': r['t'], **ib}
                try:
                    t = club_table(x)
                    rec['seasons'] = season_rows(t) if t else []
                except Exception:
                    rec['seasons'] = []
                if rec['seasons']:
                    withtab += 1
                out.write(json.dumps(rec, ensure_ascii=False) + '\n')
                kept += 1
    print('pages', n, 'footballers', kept, 'with season table', withtab)


if __name__ == '__main__':
    main()
