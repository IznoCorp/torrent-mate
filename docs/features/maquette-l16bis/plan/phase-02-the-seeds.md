# Phase 2 — The seeds

**No STOP C.**

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `python3 -c "import json;print([t['name'] for t in json.load(open('frontend/maquette/design/src/mocks/seeds/trackers.json'))])"`
  → **`['c411', 'tr4ker']`**; `grep -n "providers.lacale.enabled" frontend/maquette/design/src/mocks/seeds/settings.json`
  → line **594** (`raw: false`); the operator's `~/.torrentmate/config/tracker.json5` line 11 — `lacale` off, the
  comment « unreachable (la-cale.space down) »; `downloads.json` → **7** entries, all linked, the longest name **80**.
- **Points ≈ 12.** `lacale` into `trackers.json` from the real config, its failure declared (≈ 10 lines) 1; three
  composed trackers — `v3x.club` active, `draupnirr.xyz` off by the operator, `digitalcore.club` off by failure — and
  their `settings.json` rows (≈ 40 lines) 4, each declared in `frontend/maquette/fixture-register.json` 1; the seven
  entries' `addedAt`, `swarmSeeds`, `swarmLeechers` and down / up, read ONCE, read-only, from the operator's
  qBittorrent (`/api/v2/torrents/info`, `--connect-timeout 10 --max-time 30`), its date in the register (≈ 35 lines
  edited) 4; `python3 scripts/check-mock-seeds.py` by OUTPUT 1; the report 1.
- **Readers.** `harness/trackers_roster.py` counts the roster's entries — it reads « two » today: re-aimed out loud
  at phase 13, not here (the roster draws what it reads).

## Red today

None — seeds have no rule; `check-mock-seeds.py` is the guard.

## Move

1. Add the four trackers from the shapes already there; no entry is added to `downloads.json` (the long name, the
   unlinked and the states are POSED at phase 3 — RULINGS 7's standing rule).
2. A figure qBittorrent does not give stays `null` — never a plausible number (§ 13).

## Mutation

None.

## Register

The fixture register: the three composed trackers « composé — tracker demandé, absent du moteur », `lacale` « réel —
configuration de l'opérateur », the qBittorrent reading and its date.

## Oracle: states that diverge, declared by name

Every state drawing the roster (`trackers-roster` and its kin), declared by script; `trackers-roster-empty` does not
move.

## Commit

`feat(maquette-l16bis): the seeds of six trackers and of what an entry exchanges`
