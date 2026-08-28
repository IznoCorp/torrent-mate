# Phase 11 — Configuration, and B-090

**Its families**: `SETTINGS` (1 454 lines), `SECRETS`. `SETTINGS_STATE` is `interface`.

**B-090 is repaired here** (D-L09-3), and it is repaired because it can no longer be avoided: a
pre-formatted French value cannot feed a control, and this surface has eight field kinds that all
need one.

### The repair

`displayedValue` leaves the contract. The surface reads `raw` and formats it. The formatter lives
in this feature — it knows the domain — and its French lives in `i18n/fr.json`.

### What it must reproduce, measured

Over the **159** fields: **110** differ from `raw`, **95 of those are reproducible**:

| Kind | Rule |
| --- | --- |
| boolean | « oui » / « non » |
| empty | « non défini » |
| short list of strings | joined on « , » |
| list of ≥ 4 strings | first three, then « +N » |
| list of objects | « N entrées » |
| empty list | « aucun » |
| cron | a French phrase — the one real renderer, and the first true client of phase 2's runner |

### The one thing that stays a demand

**Seven number fields** render a decimal `raw` does not carry (`4` → « 4.0 »). JSON has no
float-ness to read. The contract gains a precision field and
`docs/reference/frontend-backend-demands.md` records the demand (D7). This is not a workaround: it
is the shape D7 prescribes — carry what is knowable, record what is not.

### What is forbidden outright

Re-deriving a truncated list's hidden elements from anywhere but `raw`. `raw` holds all four
`profile_priority` entries and all eighteen `overlays`; the RENDERER dropped them. Reading `raw`
is recovery. Inventing them is B-087.

### The test

Assert the formatter against the **159** `displayedValue` strings **committed in the seed** —
extracted from `legacy.js`, held byte for byte by `check-mock-seeds.py --arm correspondence`.
That is an oracle outside the tool. The 7 number fields are asserted as the known exception, by
name, so the exception is a list somebody reads and not a tolerance.

### Done when

- `grep -c 'displayedValue' frontend/maquette/contract/openapi.json` → 0.
- The formatter reproduces 152 of 159 exactly; the 7 are named in the test.
- `python3 scripts/compare-contracts.py --check` exit 0, the precision demand present.
- B-090's register entry moves to `fixed #NNN` with the rule named.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`. If the formatter is exact,
  nothing moves; a movement here means the formatter is wrong, not the data.

## What every surface phase carries

Four things, and none is optional:

1. **Its reads go through the cache**, never through `window.__referentiel`.
2. **Its mutations carry an optimistic path and a rollback**, or a written reason why one cannot
   exist. An action answers the finger before the network does — this is the largest single lever
   on how native the interface feels, and no animation later repairs a tap that waits for a round
   trip (DOIT-4).
3. **Its share of the fixture dies in the same commit** (D5). The engine is touched only by
   subtraction; its part is removed, never rewritten.
4. **A rule that bites**, mutation-tested: break the behaviour on purpose, see the rule fall and
   name the right defect, restore.

## The gate

`frontend/maquette/harness/run.sh --contracts`, then `--oracle`. Run **after** the phase, not
after a commit inside it.

## Done when

- `grep -rn "__referentiel" <this surface's files>` → 0.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`, or every divergence named,
  understood and accepted with its reason (D-L09-7). Never « the data changed ».
- The invariant-4 arm's count has fallen by this surface's share, and the arm says so.
