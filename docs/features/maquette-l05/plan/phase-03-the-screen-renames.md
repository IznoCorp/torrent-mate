# Phase 3 — The screens are renamed

Four addresses and one query parameter change name. A route path and a route parameter are NAMES
(the operator's ruling, #456), so they are written in English like any other name.

| Today | Becomes | Why |
| --- | --- | --- |
| `/fiche/$titre` | `/media/:provider/:id` | DOIT-11 writes that address literally, and `media-screen.tsx:397` already DISPLAYS it while serving something else |
| `/resolution/$dossier` | `/resolution/:folder` | a parameter is a name |
| `/releases/$titre` | `/releases/:title` | a parameter is a name |
| `/profile/$title` | `/quality/:name` | it is the QUALITY profile; `/account` is the operator's. One word answering for two subjects is how a reader learns to distrust a name |
| `?rub=` | `?topic=` | a parameter is a name |

## The one that is more than a rename

`/media/:provider/:id` changes what the address KEYS ON — a title becomes a provider and an id.
The ids exist in the fixture (`sheet.ids.tvdb`, `sheet.ids.tmdb`); what the route needs is the
reverse lookup, and `window.__screens.mediaSheet(title)` keeps its title-shaped door so no caller
changes.

**A media with no provider id has no sheet.** That is §11's single exception, not a gap: the
surface must lead to resolution instead. The route cannot address it, and that is the wanted
behaviour — a dead link would be the defect.

## Steps

1. Each rename goes through `scripts/rename-identifiers.py`. Never by hand, never by an ad-hoc
   regex: the same short name means different things in different scopes.
2. **The tool is not the proof.** Its read-back check is skipped for `--values` runs and for Python
   files, and `--values` is the mode that rewrites prose. So each batch is verified by an oracle
   OUTSIDE the tool: re-read the diff — not the « N file(s) touched » line — and re-run the rule
   suite. Two corruptions in this repository were found exactly that way.
3. Every `data-*` contract touched moves its **three ends in one commit**: the markup that emits
   it, the `dataset.x` that reads it, and the rule that taps it.
4. The title → ids lookup lands with the route, in the media feature that owns the concept — never
   in a shared module (L04's corollary).

## The rule that bites

R75 (`harness/screen_addresses.py`) extends to the four renamed addresses: cold deep entry for
each, one Back landing where the walk started, and an unknown subject rendering the screen's own
honest empty case instead of raising. Its existing hold on a dossier name carrying its own dots —
the shape a real staging folder has — is kept and re-run against `:folder`.

**Mutation**: point one renamed route at its old path. The rule must fall and say the address is
declared on one side only — the exact defect `logout.py` was written for after a route was renamed
on one side.

## Done when

- ACC-10 (R75 including the four renames), ACC-18 (`check-no-french.py`), ACC-19 (the contracts
  tier — `screen_addresses.py` and `logout.py` are both in it).
- ACC-03, ACC-04, ACC-05 green.
- The diff of every rename batch has been re-read by hand, and that reading is reported rather
  than asserted.
