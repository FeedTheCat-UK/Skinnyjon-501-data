# Skinny Jon Football 501 — player data

Data for **Football 501** in the Skinny Jon Customs Entertainment Centre.

**Source:** English Wikipedia ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)), read from the
monthly Wikimedia data dump (no scraping of the live site).

**Coverage (see `game/meta.json`):**
- **League stats, whole careers:** Premier League (since 1992/93), LaLiga, Serie A, Bundesliga and Ligue 1.
  League matches only, taken from each player's season-by-season career table. Players without a table use their
  infobox club figures, counted only where the club was in that league for the whole spell.
- **Internationals:** senior men's caps and goals from each player's infobox (youth, Olympic and B teams left out).
- No cards. Women's players are left out for now.

Wikipedia is edited by volunteers: big names are reliable, current players' numbers can lag a few weeks.

## Files
- `players/players.json.gz` — every player: name, Wikipedia page, birth year, main nation, league apps/goals, caps/goals.
- `game/names.json` — every player name for the phone autocomplete (most-played first).
- `game/cats.json` — the categories the game draws from (whole leagues, all five leagues, national teams × apps/goals),
  each with its start score and every eligible player's value.
- `game/meta.json` — build date and the coverage line shown in the game.

## Rebuild (monthly)
```
python3 tools/wiki_extract.py plan                       # needs index.txt.bz2 (the dump's multistream index)
seq 0 39 | xargs -P 2 -I{} python3 tools/wiki_extract.py run {}   # ~45 min, writes out/chunk_NN.jsonl.gz
python3 tools/wiki_parse.py                              # -> players.jsonl.gz
python3 tools/build_wiki.py players.jsonl.gz             # -> players/, game/
```
`tools/build.py` is the old transfermarkt-datasets builder (2012–2026 with cards), kept for reference.
