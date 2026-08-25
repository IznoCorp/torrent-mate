# Abbreviations in code names

**A name is written out in full.** `configuration`, not `cfg`. `message`, not `msg`. The
objective is reading: a name is read far more often than it is typed, and a mutilated word
costs its reader a translation every time.

> ✅ **ARMED on 2026-08-25**, by the wave that follows the one that wrote this file.
> `scripts/check-code-abbreviations.py` runs in `make check` and in CI's `guards` job, with
> two arms — `lists` (the two word files, well formed and not contradicting each other) and
> `names` (a declared name built from a refused word, held against the per-file record; a count
> and the record it is compared with are one reading, so the ratchet is not a third arm). The
> blacklist is `scripts/code-abbreviations.txt`, the words considered and KEPT are
> `scripts/code-abbreviations-allowed.txt`, and the frozen debt is
> `scripts/code-abbreviations-baseline.json`. **The rule binds agents from today.**
>
> This banner used to say the opposite, and the sentence it carried is worth keeping: until a
> guard runs, a naming rule is precisely what § Language warns against — a sentence in a file.
> The steward wrote that about its own document rather than waiting to be found out.

This file is the rule, its guard, and the debt the guard freezes. It exists because the
repository already learned, with French, that **a naming rule without an arm is a sentence in a
file** — `data-*` names were brought under the English rule and four of them simply stayed.

---

## 1. What is refused

A declared name is refused when one of its words — split on camelCase, snake_case and flat
alike — is a **mutilated word**: an English word someone shortened, with the full word obvious
behind it.

The list lives in `scripts/code-abbreviations.txt`, one line per word — `abbreviation = the
word it mutilates`. **A line with no full word is itself a violation**, the same discipline the
`french-ok:` pragma is held to: a refusal that cannot say what the name SHOULD be is a refusal
nobody can act on. It is deliberately a BLACKLIST and not a vocabulary, and that is a departure from
`code-vocabulary.txt` that has a measured reason: extending the vocabulary arm to Python would
have to admit **2 230** unknown words — `self` and `client` among them — against a file that
holds 802, and a vocabulary that must quadruple to go green is no longer a control. (`source`
was named as a third example when this was first written; it is already in the file.)

<sub>`python3 - <<'PY'` … the measurement is in § 7</sub>

**Words of one letter are never read.** `i`, `j`, `n`, `x` are short names, not mutilated ones,
and the distinction is the whole of the exemption Clean Code grants to a short scope: it
licenses a name that is BRIEF, never a word with its middle removed. The guard skips any word
under two letters, exactly as `check-no-french.py`'s vocabulary arm already does.

## 2. What is NOT an abbreviation

Three families, and each is listed in `scripts/code-abbreviations-allowed.txt` with the reason
it was kept. **A line with no reason is itself a violation** — the same discipline the
`french-ok:` pragma is held to. A word may not sit in both files: the guard refuses the
contradiction rather than letting one of them quietly win.

**Language conventions.** `self`, `cls`, `args`, `kwargs`, `argv`, `__init__`, `str`, `dict`,
`int`, `repr`, `enum`, `min`, `max`. Renaming them fights the language, not the reader.

**And `exc` joined them when the guard was built, on evidence.** It is the STANDARD LIBRARY's own
spelling — `sys.exc_info`, `exc_type`, `exc_value`, and `except … as exc` throughout the
language's documentation — and it carries **544** occurrences here, more than any other word in
either file. Refusing it would fight the language rather than the reader, which is exactly what
this family is for. It is named with its count because it is the single largest arbitration in
these two files.

**Established acronyms.** `api`, `url`, `uri`, `http`, `html`, `css`, `svg`, `json`, `xml`,
`sql`, `cli`, `id`, `db`, `io`, `os`. An acronym is not a mutilated word: nobody reads `url` as
a shortened `uniform resource locator`, it IS the word.

**Domain terms.** `nfo`, `tmdb`, `tvdb`, `omdb`, `plex`, `torrent`, `infohash`. Written as the
domain writes them.

**And one exemption that is neither, kept on evidence:** `dir` / `dirs`. Measured with the guard's
own reader over the guard's own corpus, `dir` appears **500 times and twice as a bare name** —
almost always a type suffix inside a longer name (`media_dir`, `category_dir`, `_walk_dir`). A
suffix that qualifies a noun reads without translation, and `media_directory` buys nothing for
four more characters. `dirs` is the same shape, **56 of 58 compound**.

**The figures moved when the guard was built, and the load-bearing half survived.** They were
first written as 488 and « never once bare », and 55 of 57 — measured before there was a reader
to measure with. What matters is that `dir` is compound in 498 of 500 cases, and it is; the two
bare ones are the reason this paragraph no longer says « never ». **This is the most contestable
line in this file**, and it is written here with its measurement so that overturning it is a
decision someone takes on the evidence rather than a preference.

## 3. Scope

`personalscraper/`, `scripts/`, `frontend/maquette/` — every declared name: classes, functions,
methods, **parameters and locals alike**.

Locals are in scope on purpose. Public names were measured at 93 occurrences with a debt that
has not moved in a month: a guard restricted to them would be green from day one and would
change nothing about what a reader actually reads, which is function bodies.

`tests/` is **out of scope for now** — **8 692** occurrences in 566 files, measured with the
shipped blacklist, a separate decision. (12 774 was the figure before the list existed.)

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

**Per file, not one global count**, and the reason is a hole the global form leaves open: a change
that removes one `tmp` in one file and adds another in a second leaves a global total unchanged
and passes. The per-file form costs **347** entries and closes THAT. It does not close the swap
WITHIN one file, and the count is of assignment SITES rather than of distinct names — both are
written into the guard's own docstring rather than implied away.

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

Three words carry **779 of the 1 789** occurrences and are overwhelmingly **bare names**, which is
exactly the opaque form the rule targets — and each is a mechanical rename through
`scripts/rename-identifiers.py`, verified by an oracle OUTSIDE the tool as § Code Conventions
requires.

| # | Campaign | Occurrences | Where | Note |
| - | -------- | ----------- | ----- | ---- |
| 1 | `pg` → `page` | 135 | `frontend/maquette/` only | 123 of 135 bare. Not even Playwright's own spelling, which is `page` |
| 2 | The shell vocabulary | 61 | `design/src/**` | No new guard: remove the words from `code-vocabulary.txt` and arm 6 bites |
| 3 | `ctx` → `context` | 260 | package + harness | 247 of 260 bare |
| 4 | `conn` → `connection` | 384 | package + scripts | 355 of 384 bare. The DB-API convention, and the most likely to be contested |
| — | The residue | **1 010**, in 272 files | everywhere | Frozen by the ratchet, never rewritten wholesale |

The residue is diffuse and stays that way: `ref`×105, `rel`×81, `dest`×66, `params`×58, `cfg`×56,
`msg`×48, `pos`×47, `num`×47, `idx`×38, `cur`×34 — some fifty words with a long tail. It is paid
down when a file is touched for another reason, and the ratchet makes sure it never grows.

## 7. The figures, and how they moved when the guard was built

**The rates were confirmed. The standing totals were not, and the difference is the list.** § 6's
figures were first written against a blacklist this document described and did not contain; the
guard that arms it holds **56** refused words. Three it holds — `ref`, `dest`, `params` — were not
in the measurement that produced 1 507, and `temp`/`func`/`prop`/`props` joined later because each
was a one-character escape route from a word already refused. `exc` went the other way: 544
occurrences, moved to the KEPT list on the evidence that it is the standard library's own spelling
(§ 2).

Re-measured on the armed guard's own corpus, at `9f2a90c1` — the commit that closes the
adversarial review, and the first at which the reader sees an attribute assignment:

| Figure | First measured | Armed guard | |
| ------ | -------------- | ----------- | - |
| Debt under this rule | 1 507 | **1 789** | a wider list, `exc` kept, and `self._connection = …` finally read |
| Cleared by campaigns 1, 3, 4 | 762 | **779** | `conn` re-counts at 384 once attributes are read |
| Frozen residue | 745, in 322 files | **1 010, in 272 files** | 272 is the residue's file count; the RECORD freezes the whole debt, 1 789 over 347 files |
| `conn` bare | 339 of 368 | **355 of 384** | twelve of the new ones are `self._conn` |
| `pg` bare | 123 of 135 | **123 of 135** | identical |
| New per day, residue only (23 days) | ≈ 3 | **3.7** | (1 010 − 925) ÷ 23 |
| New per day, campaigns refused too | ≈ 14.5 | **15.1** | (1 789 − 1 441) ÷ 23 |
| Public names alone (the rejected narrow scope) | 93, flat for a month | not re-measured | the scope was rejected; the figure decides nothing |
| Locals in a scope of five lines or fewer | 57 % | not re-measured | as above |

**The rate is the figure that mattered, and it holds.** A debt figure says what is owed; a rate
says what the guard costs every day, and it is the rate that decided the scope — 3.7 against a
forecast of ≈ 3, 15.1 against ≈ 14.5, both measured against `1ecfe794` (2026-08-02, 23 days back),
the same window the first measurement used, and both re-derived with the SAME list on both ends.

**Twice now these figures have been asserted from a list that was not the one shipping**, which is
the whole subject of B-074 and the reason both columns stand here instead of one being overwritten.

Clean Code licenses a **brief** name in a brief scope, and most of this debt sits in such scopes
— which is why § 1 draws the line at mutilation rather than at length, and why the guard never
reads a one-letter word.

<sub>`python3 scripts/check-code-abbreviations.py --list-baseline` re-derives the per-file record
and the whole-debt total. The residue split, the bare-name shares and the two per-day figures come
from running the guard's own `declared_names()` and `words_of()` over the corpus and over
`git ls-tree` at the older commit — twenty lines, not committed, because a figure is re-derived
rather than trusted.</sub>
