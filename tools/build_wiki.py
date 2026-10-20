#!/usr/bin/env python3
"""Builds the Football 501 data from English Wikipedia (CC BY-SA).

Input: players.jsonl.gz made by tools/wiki_parse.py from the Wikipedia dump.
Writes: players/players.json.gz, game/names.json, game/cats.json, game/meta.json

League totals come from each player's season-by-season career table (league matches only).
Players with no table fall back to their infobox club spells, counted only where every season
of the spell is known (from other players' tables) to be in that league.
International caps and goals are senior men's caps from the infobox.
"""
import sys, json, gzip, re, pathlib, datetime, collections

SRC = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(__file__).resolve().parent.parent
THIS_SEASON = int(sys.argv[2]) if len(sys.argv) > 2 else (datetime.date.today().year if datetime.date.today().month >= 7 else datetime.date.today().year - 1)

# Wikipedia link target -> game league name
LEAGUE_TARGETS = {
    'Premier League': 'Premier League', 'FA Premier League': 'Premier League',
    'La Liga': 'LaLiga', 'Primera División': 'LaLiga', 'La Liga (Spain)': 'LaLiga', 'Spanish La Liga': 'LaLiga',
    'Serie A': 'Serie A', 'Serie A (Italy)': 'Serie A',
    'Bundesliga': 'Bundesliga', 'Fußball-Bundesliga': 'Bundesliga',
    'Ligue 1': 'Ligue 1', 'French Division 1': 'Ligue 1', 'Division 1 (France)': 'Ligue 1', 'French Division 1 (football)': 'Ligue 1',
}
# unlinked division text, used only if the page never linked it
LEAGUE_TEXT = {'Premier League': 'Premier League', 'FA Premier League': 'Premier League', 'La Liga': 'LaLiga', 'LaLiga': 'LaLiga',
               'Serie A': 'Serie A', 'Bundesliga': 'Bundesliga', 'Ligue 1': 'Ligue 1', 'Division 1': 'Ligue 1'}
FIRST = {'Premier League': 1992, 'LaLiga': 1929, 'Serie A': 1929, 'Bundesliga': 1963, 'Ligue 1': 1932}
LEAGUES = ['Premier League', 'LaLiga', 'Serie A', 'Bundesliga', 'Ligue 1']

# national team -> (name shown, adjective, weight). Weight: how often it comes up in the random draw.
NATIONS = {
    'England': 2.0, 'Scotland': 1.2, 'Wales': 1.2, 'Northern Ireland': 0.8, 'Republic of Ireland': 0.9,
    'France': 0.7, 'Spain': 0.7, 'Germany': 0.7, 'Italy': 0.7, 'Brazil': 0.7, 'Argentina': 0.7, 'Netherlands': 0.7,
    'Portugal': 0.6, 'Belgium': 0.5, 'Denmark': 0.4, 'Sweden': 0.4, 'Norway': 0.3, 'Croatia': 0.4, 'Uruguay': 0.4,
    'United States': 0.4, 'Mexico': 0.3, 'Nigeria': 0.3, 'Ivory Coast': 0.3, 'Ghana': 0.3, 'Senegal': 0.3, 'Egypt': 0.3,
    'Cameroon': 0.3, 'Japan': 0.3, 'South Korea': 0.3, 'Australia': 0.3, 'Poland': 0.3, 'Switzerland': 0.3, 'Austria': 0.3,
    'Czech Republic': 0.3, 'Colombia': 0.3, 'Chile': 0.3, 'Turkey': 0.3, 'Greece': 0.3, 'Russia': 0.3, 'Morocco': 0.3,
}
TEAM_ALIASES = {"Côte d'Ivoire": 'Ivory Coast', 'Ireland': 'Republic of Ireland', 'West Germany': 'Germany', 'Czechoslovakia': None,
                'Soviet Union': None, 'Yugoslavia': None, 'Türkiye': 'Turkey', 'Korea Republic': 'South Korea'}


def team_nation(team):
    t = re.sub(r'\s+(men\'s\s+)?national\s+(association\s+)?(football|soccer)\s+team.*$', '', team or '', flags=re.I).strip()
    t = TEAM_ALIASES.get(t, t)
    return t if t in NATIONS else None


def short_name(rec):
    n = rec.get('name') or ''
    t = re.sub(r'\s*\(.*\)$', '', rec['title']).strip()
    # the infobox name is sometimes a full legal name; prefer the page title when it is shorter and contained
    if not n or len(n) > 40 or (len(t) < len(n) and t.split()[-1] in n):
        n = t
    return n


def club_key(c):
    c = re.sub(r'\s*\((loan|on loan)\)', '', c or '', flags=re.I).replace('→', '').strip()
    return c


players = [json.loads(l) for l in gzip.open(SRC, 'rt', encoding='utf-8')]
print('pages', len(players))

# 1) resolve each season row's league from linked division names (a link carries forward to later
#    unlinked rows with the same text on that page); learn which league each club was in each season
club_season = collections.defaultdict(collections.Counter)
for p in players:
    seen = {}
    for row in p['seasons']:
        club, season, tgt, txt, a, g = row
        if tgt:
            seen[txt] = tgt
        t = tgt or seen.get(txt)
        if t:  # "2004–05 La Liga" -> "La Liga"
            t = re.sub(r'^\d{4}(?:[–\-]\d{2,4})?\s+', '', t)
        lg = LEAGUE_TARGETS.get(t) if t else None
        if lg and season < FIRST[lg]:
            lg = None
        row.append(lg if t else '?')
        if t:
            club_season[(club_key(club), season)][lg or 'other'] += 1


def league_of(club, season):
    c = club_season.get((club, season))
    if not c:
        return '?'
    lg, n = c.most_common(1)[0]
    tot = sum(c.values())
    return lg if n >= 3 and n >= 0.85 * tot else '?'


# rows whose division was never linked on the page: trust them only if other players' tables
# put that club in that league that season
for p in players:
    for row in p['seasons']:
        if row[6] == '?':
            lg = league_of(club_key(row[0]), row[1]) if LEAGUE_TEXT.get(row[3]) else None
            row[6] = lg if lg in FIRST and lg == LEAGUE_TEXT.get(row[3]) else None


# 2) per-player totals
out_players, names, stats = [], [], []
fallback_used = 0
for p in players:
    if p.get('female'):
        continue
    lt = collections.defaultdict(lambda: [0, 0])
    first_season, last_season = 9999, 0
    if p['seasons']:
        for club, season, tgt, txt, a, g, lg in p['seasons']:
            first_season = min(first_season, season); last_season = max(last_season, season)
            if lg and g <= 2 * a + 1:
                lt[lg][0] += a; lt[lg][1] += g
    else:
        for c in p['clubs']:
            if c['y0'] is None or c['apps'] is None:
                continue
            y1 = c['y1'] if c['y1'] is not None else THIS_SEASON + 1
            seasons = list(range(c['y0'], max(c['y0'] + 1, y1)))
            first_season = min(first_season, c['y0']); last_season = max(last_season, seasons[-1])
            lgs = {league_of(club_key(c['club']), s) for s in seasons}
            if len(lgs) == 1:
                lg = lgs.pop()
                if lg in FIRST and (c['goals'] or 0) <= 2 * c['apps'] + 1:
                    lt[lg][0] += c['apps']; lt[lg][1] += c['goals'] or 0
                    fallback_used += 1
    intl = {}
    for t in p['intl']:
        n = team_nation(t['team'])
        if n and t['caps']:
            cur = intl.get(n, [0, 0])
            intl[n] = [cur[0] + t['caps'], cur[1] + (t['goals'] or 0)]
    if not lt and not intl:
        continue
    nation = max(intl, key=lambda k: intl[k][0]) if intl else ''
    name = short_name(p)
    rec = {'name': name, 'wiki': p['title'], 'born': p.get('birth'), 'nation': nation,
           'leagues': {k: v for k, v in lt.items()}, 'intl': intl,
           'active': last_season >= THIS_SEASON - 1}
    out_players.append(rec)

# order: most league apps + caps first (autocomplete shows famous players first)
out_players.sort(key=lambda r: -(sum(v[0] for v in r['leagues'].values()) + 2 * sum(v[0] for v in r['intl'].values())))
idx = {id(r): i for i, r in enumerate(out_players)}
print('players kept', len(out_players), 'infobox fallback spells', fallback_used)

(OUT / 'players').mkdir(exist_ok=True); (OUT / 'game').mkdir(exist_ok=True)
with gzip.open(OUT / 'players/players.json.gz', 'wt', encoding='utf-8') as f:
    json.dump(out_players, f, ensure_ascii=False, separators=(',', ':'))
names = [[r['name'], r['nation'], r['born'] or 0] for r in out_players]
json.dump(names, open(OUT / 'game/names.json', 'w'), ensure_ascii=False, separators=(',', ':'))

# 3) categories
TIERS = [(501, 180), (301, 180), (201, 180), (101, 180), (51, 180)]  # darts rules: max 180 a turn


def tier(vals):
    for start, mx in TIERS:
        e = sorted(v for v in vals if 1 <= v <= mx)
        if len(e) >= 20 and sum(e[-8:]) >= start * 1.15:
            return start
    return None


cats = []


def add(cid, kind, label, sub, stat, pairs, weight, note=''):
    vals = {i: v for i, v in pairs if v > 0}
    st = tier(list(vals.values()))
    if not st:
        print('  skipped', label, sub); return
    cats.append({'id': cid, 'kind': kind, 'stat': stat, 'label': label, 'sub': sub, 'note': note, 'start': st, 'w': round(weight, 2),
                 'p': sorted([[k, v] for k, v in vals.items()], key=lambda x: -x[1])})


SINCE = {'Premier League': 'since 1992/93'}
for lg in LEAGUES:
    for si, stat, cap in [(0, 'apps', 'Most appearances'), (1, 'goals', 'Most goals')]:
        add(f'w{lg[:3]}{stat[0]}', 'league', lg, cap, stat,
            [(i, r['leagues'][lg][si]) for i, r in enumerate(out_players) if lg in r['leagues']], 2.0,
            SINCE.get(lg, 'all seasons'))
for si, stat, cap in [(0, 'apps', 'Most appearances'), (1, 'goals', 'Most goals')]:
    add(f'wall{stat[0]}', 'all', 'All five leagues', cap, stat,
        [(i, sum(v[si] for v in r['leagues'].values())) for i, r in enumerate(out_players)], 1.5,
        'Premier League, LaLiga, Serie A, Bundesliga and Ligue 1 together')
HOME = {'England', 'Scotland', 'Wales', 'Northern Ireland', 'Republic of Ireland'}
for n, w in NATIONS.items():
    w = w if n in HOME else w * 0.5
    for si, stat, cap in [(0, 'apps', 'Most caps'), (1, 'goals', 'Most international goals')]:
        add(f'wn{re.sub("[^A-Za-z]", "", n)[:6]}{stat[0]}', 'nation', n, cap, stat,
            [(i, r['intl'][n][si]) for i, r in enumerate(out_players) if n in r['intl']], w,
            'senior international caps and goals')

meta = {'version': 2, 'built': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'seasons': 'All',
        'leagues': LEAGUES,
        'coverage': 'Career league stats from Wikipedia: Premier League (since 1992/93), LaLiga, Serie A, Bundesliga and Ligue 1 (league matches only), plus senior international caps and goals.',
        'players': len(names), 'categories': len(cats), 'source': 'English Wikipedia (CC BY-SA 4.0)'}
json.dump(cats, open(OUT / 'game/cats.json', 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(meta, open(OUT / 'game/meta.json', 'w'), ensure_ascii=False, indent=1)
print(meta)
print(collections.Counter((c['kind'], c['stat'], c['start']) for c in cats))
