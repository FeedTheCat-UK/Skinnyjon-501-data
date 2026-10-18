# Skinny Jon Football 501 — player data

Data for **Football 501** in the Skinny Jon Customs Entertainment Centre.

**Coverage:** league matches in the Premier League, LaLiga, Serie A, Bundesliga and Ligue 1,
seasons **2012/13 to 2025/26** (see `game/meta.json`). Cup, European and international matches are not counted.
International caps are **not** included: the source mixes youth and senior caps, so they can't be trusted.

**Source:** [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) by David Cariboo (CC0).
Its automatic updates paused in July 2026; when they restart, the monthly task rebuilds these files.

## Files
- `players/current.json` — players in the 2025/26 squad data (updated when the source updates).
- `players/former.json` — everyone else (retired or moved out of these leagues). Static.
  Each player: name, nation, birth year, position, and per club: league, seasons, apps, goals, yellow and red cards.
- `game/names.json` — every player name for the phone autocomplete (most-played first).
- `game/cats.json` — the categories the game draws from (club, whole league, nationality-in-a-league × apps/goals/cards),
  each with its start score (501/301/201/101/51) and every eligible player's value.
- `game/meta.json` — build date, seasons covered and the coverage line shown in the game.

## Rebuild
Download the CSVs (`appearances`, `games`, `players`, `clubs`) from the source into a folder, then:
`python3 tools/build.py /path/to/folder`
