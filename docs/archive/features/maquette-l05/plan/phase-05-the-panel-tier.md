# Phase 5 — The panel tier

D1 ranks layers in three tiers and this phase puts the ranking in force. The panel is the only
layer that takes an address, and only four of the engine's eight distinct producers do.

## The classification, and the reasoning behind it

The operator delegated this choice; the reasoning is therefore recorded here to be contested rather
than assumed.

| Producer | Subject | Tier | Address |
| --- | --- | --- | --- |
| `openFollowSheet(title)` (alias `openDetailSheet`) | a title | 2 | `?panel=follow:<title>` |
| `openJourneySheet(title)` | a title | 2 | `?panel=journey:<title>` |
| `openSetting(id)` | a setting id | 2 | `?panel=setting:<id>` |
| `openActionMaintenance(id)` | a command id | 2 | `?panel=action:<id>` |
| `openUserSheet()` | none — a menu | 3 | none |
| `openMoreSheet()` | none — a menu | 3 | none |
| `openSugSheet(index)` | a POSITION in `SUGGESTIONS` | 3 | none |
| `openAddSheet(index)` | a POSITION in `SEARCH.results` | 3 | none |

**A menu is tier 3 by D1's own example** (« a sort menu, a confirmation »). The navigation drawer
is the same case and stays transient — Back closes it, no URL.

**An index is not an identity.** An address carrying a position designates something else once the
list has moved, so a reload would reopen a panel about a media the operator never asked for — §13
read from its other end. Addressing those two by title instead is available and deliberately
refused: the same title can appear in the suggestions and in the add results, so choosing which
panel opens is a behaviour decision, and it belongs to L09 where the real data arrives.

`openPanel(element)` is a dispatcher and `openDetailSheet` an alias — neither is a producer.
`openSheet()` is the retired tripwire and stays one.

## Steps

1. **One table maps a panel address to its producer**, and it lives where the panel already lives
   (`ui/panel/`), never in a shared module. A `<kind>` the table does not carry is refused the way
   an undeclared block `type` already is — a producer nobody converted fails where it is written.
2. `window.__panel.open(descriptor)` gains the address as part of opening; `.fermer(pop?)`
   removes it. The panel's own store fields (`panelOpen`, `panelDescriptor`) stay the source of
   truth for what is DRAWN — the address says which, not whether.
3. **Cold load reopens.** The address is read once the page it sits on has rendered, and the
   producer is re-invoked. A subject the fixture no longer holds renders the panel's honest empty
   case, never a raise.
4. Back closes the panel and removes its parameter, in one entry — the existing unwinding is kept,
   not replaced.

## The rule that bites

Extend `harness/panel.py` (R56), which already holds the panel's shape — no caller hands markup,
exactly one constructor, every declared block draws, an undeclared one is refused. Its new holds:
a tier-2 panel's address survives a reload and reopens it; a tier-3 layer writes NO address and
Back still closes it.

**Mutation**: drop the panel parameter on a cold load. The rule must fall and say the panel did not
reopen at its address — not merely that a hold is missing.

⚠ `panel.py`'s hold count is **12** since #479 corrected it from 9. A count that moves here must be
the holds this phase adds, and nothing else.

## Done when

- ACC-04 — the hold counts move only by what this phase adds, and the delta is named.
- ACC-07 (R69 — `panel` is a query parameter, so hold 6 must still pass), ACC-08 (the `addressing`
  arm accepts `panel` as a dial and would refuse it as a path segment).
- ACC-03, ACC-05 green.
- The mutation has been seen to fall and been restored.
