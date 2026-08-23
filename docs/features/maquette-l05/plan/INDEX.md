# L05 — Routing · implementation plan

**Design**: `docs/features/maquette-l05/DESIGN.md`
**Lot contract**: `docs/reference/frontend-architecture.md` § « L05 — Routing », Phase 1
**Branch**: `refactor/maquette-l05` · **version**: 0.98.23 → 0.98.24

---

## The order, and why it is this one

**Phase 1 comes first because nothing after it is measurable otherwise.** The harness reads
`http://127.0.0.1:8899/wrapped.html`, served by a plain `http.server`. The moment a page has a
real path, that pathname matches no route and the router renders the not-found page — every rule,
the oracle's 2 739 measurements and the accessibility audit collapse together, for a reason that
has nothing to do with the change under test. So the instruments move to a host that folds unknown
addresses onto the document, and they move **while nothing else has changed**, which is what makes
that phase provable on its own.

**Phase 2 is the lot.** Everything before it prepares; everything after it extends the same rule to
one more surface.

**Each phase carries its own rule, mutation-tested** (invariant 11). A rule that never bit proves
nothing.

| #   | Phase                                  | File                                        | Status |
| --- | -------------------------------------- | ------------------------------------------- | ------ |
| 1   | The harness's ground                   | `phase-01-the-harness-ground.md`            | [ ]    |
| 2   | The pages take their paths             | `phase-02-pages-take-paths.md`              | [ ]    |
| 3   | The screens are renamed                | `phase-03-the-screen-renames.md`            | [ ]    |
| 4   | The sign-in screen gets its address    | `phase-04-login.md`                         | [ ]    |
| 5   | The panel tier                         | `phase-05-the-panel-tier.md`                | [ ]    |
| 6   | The offline guard, and one subtraction | `phase-06-the-guard-and-the-subtraction.md` | [ ]    |
| 7   | The records, and the gate              | `phase-07-the-records.md`                   | [ ]    |

---

## ACCEPTANCE — every criterion is an executable command with its expected output

Run from the repository root unless stated. `run.sh` builds and re-copies the prototype first, so
none of these measures a stale build.

| ID     | Command                                                                                                                                                     | Expected                                                                                                         |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| ACC-01 | `python3 -c "import pathlib,re;p=pathlib.Path('frontend/maquette/harness/common.py').read_text();print(re.search(r'PROTOTYPE = \"([^\"]+)\"',p).group(1))"` | `http://127.0.0.1:8899/` — no `wrapped.html`                                                                     |
| ACC-02 | `grep -rl "wrapped.html" frontend/maquette/harness/*.py frontend/maquette/oracle.py frontend/maquette/a11y.py \| wc -l`                                     | a number the phase records, and every remaining occurrence is the FILE COPY operation, never a navigation target |
| ACC-03 | `frontend/maquette/harness/run.sh`                                                                                                                          | `harness: N rule(s), no violation.`, exit 0                                                                      |
| ACC-04 | `python3 scripts/harness-hold-counts.py --compare`                                                                                                          | no movement, exit 0                                                                                              |
| ACC-05 | `make maquette-oracle`                                                                                                                                      | `0 divergence` over 83 states × 33 regions, exit 0                                                               |
| ACC-06 | `curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8899/media`                                                     | `200` — the host folds an unknown address onto the document                                                      |
| ACC-07 | `python3 frontend/maquette/harness/url_state.py`                                                                                                            | R69's six holds, exit 0                                                                                          |
| ACC-08 | `python3 scripts/check-frontend-boundaries.py --arm addressing`                                                                                             | `addressing: … 0 violation(s)`, exit 0                                                                           |
| ACC-09 | `python3 scripts/check-frontend-boundaries.py`                                                                                                              | all nine arms, 0 violations, exit 0                                                                              |
| ACC-10 | `python3 frontend/maquette/harness/screen_addresses.py`                                                                                                     | R75 including the four renamed addresses, exit 0                                                                 |
| ACC-11 | `python3 frontend/maquette/harness/navigation.py`                                                                                                           | R76 — exactly one `navigate()` call site, exit 0                                                                 |
| ACC-12 | `python3 frontend/maquette/harness/back.py && python3 frontend/maquette/harness/screens.py && python3 frontend/maquette/harness/bridge.py`                  | R59, R71, R74 green at unchanged ASSERTIONS (see ACC-21), exit 0                                                               |
| ACC-13 | `grep -c "urlFromState\|stateFromUrl\|URL_DEFAULTS\|function openScreen" frontend/maquette/design/src/engine/legacy.js`                                     | `0`                                                                                                              |
| ACC-14 | `grep -rn "page=" frontend/maquette/design/src frontend/maquette/harness/*.py \| grep -v "data-page" \| wc -l`                                              | `0` — no page identity survives in a query                                                                       |
| ACC-15 | `make lint`                                                                                                                                                 | 0 error                                                                                                          |
| ACC-16 | `make test`                                                                                                                                                 | `NNNN passed`, 0 failed **and 0 error**                                                                          |
| ACC-17 | `make check`                                                                                                                                                | exit 0                                                                                                           |
| ACC-18 | `python3 scripts/check-no-french.py`                                                                                                                        | 0 violation, exit 0                                                                                              |
| ACC-19 | `frontend/maquette/harness/run.sh --contracts`                                                                                                              | 5 rules, no violation, exit 0                                                                                    |
| ACC-20 | `python3 frontend/maquette/a11y.py --check`                                                                                                                 | hard zero, exit 0                                                                                                |
| ACC-21 | `git diff main..HEAD -- frontend/maquette/harness/back.py frontend/maquette/harness/screens.py frontend/maquette/harness/bridge.py` | only the itemised address moves — **not one changed `check(...)` assertion** |

**ACC-21 is the one that says the wave did not cheat.** R59, R71 and R74 are the behaviour
invariants the bridge must keep; passing them by editing them proves nothing.

⚠ **It was first written as « byte-identical » and that was unsatisfiable**, found before executing
rather than at the gate. The host moves in phase 1, so a rule navigating to `.../wrapped.html`
cannot keep that literal and still load the page. The line the criterion holds is therefore not
« no edit » but « **no edited assertion** »:

- **May move**, each occurrence itemised in the phase report: the navigation target (`pg.goto(...)`,
  a module-level `URL` / `PROTOTYPE` constant), and the origin test standing in for « the document
  was left ».
- **May not move**: any `check(...)` / `journal.check(...)` call — its name, its condition, its
  detail.

The origin test is a defect being repaired, not a convenience. `back.py:32` and `back.py:140`
assert `"wrapped.html" not in pg.url`, which under D1 reads « the document was left » about an
address that never left it. `harness/ident.py:22-28` already met this and wrote the answer down —
« the test is the origin, never the file name: a router-owned address (`/`, `/add`) is served by
the same document and carries no « wrapped.html » anywhere in it ». `back.py` adopts the form its
sibling already proved, and the reason travels with it.

---

## The mutation tests — each rule is broken on purpose, once

A rule lands only after it has been seen to fall AND to name the right defect. Per the repo's
rule, the fix is **committed first**, then the mutation is applied, observed, and restored.

| Rule                                          | The mutation                                         | It must say                                   |
| --------------------------------------------- | ---------------------------------------------------- | --------------------------------------------- |
| R69 hold « no page identity in a query »      | re-add `page` to the search params of the page route | the address carries a page id                 |
| R69 hold « a deep address lands cold »        | make the page route's loader ignore the match        | the cold address landed on the wrong page     |
| R69 hold « a wrong address is left as typed » | derive the address from the 404 state                | the address was rewritten behind the operator |
| `addressing` arm                              | declare a dial (`sort`) as a path segment            | the dial is in the path                       |
| R75 (renames)                                 | point one renamed route at its old path              | the address is declared on one side only      |
| panel tier                                    | drop the panel param on a cold load                  | the panel did not reopen at its address       |

---

## What this plan refuses to do

Convert the 116 `__go(` call sites across 32 rule files — the lot asks that driving by URL become
POSSIBLE and be proved, not that every rule move in the wave that also moves navigation. A rule
that fell would then have two possible causes, which is precisely what L02 was separated to avoid.

Touch the backend, the bundle split (L12), the 42 contrast findings or the 13 px search field
(L06), B-036, B-040.
