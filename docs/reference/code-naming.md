# Abbreviations in code names

**A name is written out in full.** `configuration`, not `cfg`. `message`, not `msg`. The
objective is reading: a name is read far more often than it is typed, and a mutilated word
costs its reader a translation every time.

> ⚠ **THIS RULE IS NOT ARMED YET, and saying so is the point.** Written 2026-08-25. The guard
> `scripts/check-code-abbreviations.py`, its blacklist file, its exemption file and its baseline
> **do not exist**: this document specifies them, and a wave has to build them. Until that lands,
> this file is precisely what § Language warns against — a sentence in a file — and it is the
> steward that wrote it, so it says so itself rather than waiting to be found out. The rule binds
> agents from the day the guard runs in `make check` and in CI's `guards` job, not from the day
> it was written down.

This file is the rule, its guard, and the debt the guard freezes. It exists because the
repository already learned, with French, that **a naming rule without an arm is a sentence in a
file** — `data-*` names were brought under the English rule and four of them simply stayed.

---

## 1. What is refused

A declared name is refused when one of its words — split on camelCase, snake_case and flat
alike — is a **mutilated word**: an English word someone shortened, with the full word obvious
behind it.

The list lives in `scripts/code-abbreviations.txt`, one word per line with the word it
mutilates. It is deliberately a BLACKLIST and not a vocabulary, and that is a departure from
`code-vocabulary.txt` that has a measured reason: extending the vocabulary arm to Python would
have to admit 1 665 unknown words, `self`, `client` and `source` among them, and a vocabulary
that must triple to go green is no longer a control.

<sub>`python3 - <<'PY'` … the measurement is in § 7</sub>

**Words of one letter are never read.** `i`, `j`, `n`, `x` are short names, not mutilated ones,
and the distinction is the whole of the exemption Clean Code grants to a short scope: it
licenses a name that is BRIEF, never a word with its middle removed. The guard skips any word
under two letters, exactly as `check-no-french.py`'s vocabulary arm already does.

## 2. What is NOT an abbreviation

Three families, and each is listed in the file with the reason it was kept. **A line with no
reason is itself a violation** — the same discipline the `french-ok:` pragma is held to.

**Language conventions.** `self`, `cls`, `args`, `kwargs`, `__init__`. Renaming them fights the
language, not the reader.

**Established acronyms.** `api`, `url`, `uri`, `http`, `html`, `css`, `svg`, `json`, `xml`,
`sql`, `cli`, `id`, `db`, `io`, `os`. An acronym is not a mutilated word: nobody reads `url` as
a shortened `uniform resource locator`, it IS the word.

**Domain terms.** `nfo`, `tmdb`, `tvdb`, `omdb`, `plex`, `torrent`, `infohash`. Written as the
domain writes them.

**And one exemption that is neither, kept on evidence:** `dir` / `dirs`. Measured over the whole
repository, `dir` appears **488 times and never once as a bare name** — it is always a type
suffix inside a longer name (`media_dir`, `category_dir`, `staging_dirs`, `_walk_dir`). A
suffix that qualifies a noun reads without translation, and `media_directory` buys nothing for
four more characters. `dirs` is the same shape (55 of 57 compound). **This is the most
contestable line in this file**, and it is written here with its measurement so that overturning
it is a decision someone takes on the evidence rather than a preference.

## 3. Scope

`personalscraper/`, `scripts/`, `frontend/maquette/` — every declared name: classes, functions,
methods, **parameters and locals alike**.

Locals are in scope on purpose. Public names were measured at 93 occurrences with a debt that
has not moved in a month: a guard restricted to them would be green from day one and would
change nothing about what a reader actually reads, which is function bodies.

`tests/` is **out of scope for now** — 12 774 occurrences, a separate decision.

**TypeScript and TSX are NOT covered by this guard.** `check-no-french.py`'s vocabulary arm
(arm 6) already refuses any name built from a word absent from `scripts/code-vocabulary.txt`,
and it accepts `btn`, `idx`, `skel`, `sug`, `dlg`, `surf` only because that file was seeded FROM
the code — the trap the vocabulary file documents about itself. Removing those words from the
vocabulary arms the existing check over **61 shell names**, with no new machinery at all. That
is the whole of the frontend side of this rule.

## 4. The ratchet

`scripts/code-abbreviations-baseline.json`, on the pattern of
`scripts/french-exemption-baseline.json`: **a count per file**, which the guard refuses to see
go UP. It may go down, and a file that reaches zero leaves the baseline.

**Per file, not one global count**, and the reason is a hole the global form leaves open: a pull
request that removes one `tmp` and adds another leaves a global total unchanged and passes. The
per-file form costs 322 entries and closes it.

**Refused, not printed.** `check_app_interface_text` drifted by 7 inside the very pull request
that introduced it as a control, because a number nobody compares is a number nobody reads.

## 5. What this guard cannot do

Said here so it is not discovered later:

- **The list has holes by construction** — it is the objection this repository made to asking
  « is this word French? », and it applies. It is payable here only because the distribution is
  short: twenty words cover most of the debt. A missing word is one line, added under review.
- **It cannot tell a mutilated word from a domain term** — only the exemption list can, and that
  list is maintained by hand.
- **It reads declarations, not usage.** A name imported from a third-party library keeps that
  library's spelling, and the guard has nothing to say about it.

## 6. The campaigns, in the order they cost least

Three words carry 762 of the 1 507 occurrences and are **bare names**, which is exactly the
opaque form the rule targets — and each is a mechanical rename through
`scripts/rename-identifiers.py`, verified by an oracle OUTSIDE the tool as § Code Conventions
requires.

| # | Campaign | Occurrences | Where | Note |
| - | -------- | ----------- | ----- | ---- |
| 1 | `pg` → `page` | 135 | `frontend/maquette/` only | 123 of 135 bare. Not even Playwright's own spelling, which is `page` |
| 2 | The shell vocabulary | 61 | `design/src/**` | No new guard: remove the words from `code-vocabulary.txt` and arm 6 bites |
| 3 | `ctx` → `context` | 260 | package + harness | 247 of 260 bare |
| 4 | `conn` → `connection` | 368 | package + scripts | 339 of 368 bare. The DB-API convention, and the most likely to be contested |
| — | The residue | **745**, in 322 files | everywhere | Frozen by the ratchet, never rewritten wholesale |

The residue is diffuse and stays that way: `rel`×81, `cfg`×56, `msg`×48, `num`×47, `pos`×47,
`idx`×38, `cur`×34 — some seventy words with a long tail. It is paid down when a file is touched
for another reason, and the ratchet makes sure it never grows.

## 7. The figures, and the commands that produce them

Every number above was measured on `main` at `2a3f2576`, and re-measured over four months of
history to establish the RATE rather than the standing total — a debt figure says what is owed,
a rate says what the guard will cost every day.

| Figure | Value |
| ------ | ----- |
| Debt under this rule | 1 507 |
| Cleared by campaigns 1, 3, 4 | 762 |
| Frozen residue | 745, in 322 files |
| New occurrences per day, residue only (last 23 days) | ≈ 3 |
| New occurrences per day, had `dir`/`conn`/`ctx`/`pg` been refused too | ≈ 14.5 |
| Public names alone (the rejected narrow scope) | 93, and flat for a month |
| Locals living in a scope of five lines or fewer | 57 % |

That last figure is the one to keep in view. Clean Code licenses a **brief** name in a brief
scope, and 57 % of the debt sits in such scopes — which is why § 1 draws the line at mutilation
rather than at length, and why the guard never reads a one-letter word.

<sub>The measuring scripts are not committed: they are twenty lines of `ast.walk` over the three
roots, and a figure is re-derived rather than trusted. The shapes are in this file's own pull
request.</sub>
