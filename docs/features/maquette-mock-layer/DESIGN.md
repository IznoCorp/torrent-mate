# maquette-mock-layer — the mock answers the declared code, one season family, two verbs that send

Register: **B-379**, **B-383** (two of its four verbs, plus a fifth of its class this wave files),
**B-396**, **B-380**. Rules **R170**–. Constitution: NE-DOIT-PAS-1 (« ne jamais affirmer ce qui n'a pas
eu lieu »), NE-DOIT-PAS-5 (« ne jamais masquer une erreur »), §13 (real data), §5 (season by season).
Decisions: D7 (the contract is the maquette's and it is what the interface REQUIRES), D8 (the oracle
measures geometry and computed style), D5 (the engine only shrinks).

A micro-wave on the layer the rules measure against, and on its seeds. It is one subject — a mock that
answers what the contract declares, over data that agrees with itself — which is why the four entries
travel together.

## 0. What moved, at a glance

| Entry | What was wrong | What closes it | Rule |
| --- | --- | --- | --- |
| B-379 | the layer answered 200 whatever the contract declared | the declared success code, read off `contract/openapi.json` | R170 |
| B-383 | « Re-scraper les métadonnées » (follow panel AND media sheet) and « Lancer à blanc » said a sentence and sent nothing | each verb calls its operation; the mock moves the state it answers about | R171, R172 |
| B-396 | one queued folder offered candidates, so the undo window's riskiest path had no finger proof | a second ambiguous folder in the seed, and a walk by a real touch | R173 |
| B-380 | the sheet counted the catalogue's total as « aired » | aired is DERIVED from the catalogue's own episode dates; `seasons.json` corrected on five lines | R174 |

---

## 1. B-379 — the mock answers what the contract declares

### The defect, measured

`design/src/mocks/scenario.ts:145` computed every outcome as
`status: armed ? (asked.status ?? 200) : 200`. The contract declares **201** for
`grabSeasonForFollow` and **202** for `requeueJourney` and `rescrapeJourney`; the layer answered **200**
to all three. It was read, not reasoned: R158's first run saw four season grabs and four `status: 200`
in `window.__mocks.answered()`, and every hold written on the literal code was red for a reason that
was not the act.

```
$ python3 - <<'PY'
import json, collections
contract = json.load(open('frontend/maquette/contract/openapi.json'))
codes = collections.Counter()
for path, item in contract['paths'].items():
    for method, operation in item.items():
        if method in ('get','post','put','patch','delete'):
            codes[tuple(k for k in operation['responses'] if k.isdigit() and k.startswith('2'))] += 1
print(codes)
PY
Counter({('200',): 55, ('202',): 2, ('201',): 1})
```

### The repair

`design/src/mocks/declared-status.ts` — a new module that IMPORTS the contract
(`frontend/maquette/contract/openapi.json`, the same artefact
`mocks/contract-conformance.test.ts` already reads) and builds
`operationId → the lowest declared 2xx`, once, at module evaluation. `scenario.ts`'s `outcomeFor`
reads it on **both** branches of its conditional:

```ts
const success = declaredSuccessStatus(operationId);
return { status: armed ? (asked.status ?? success) : success, … };
```

Both branches, because « unarmed » means « answer normally » and normal is what the contract declares;
a repair that touched only the other one would leave an operation with a latency dial answering 200.

**Never a hand-written table.** A map from operation to status declared a second time is the shape of
every drift this repository has paid for: the day the contract gains an operation answering 201, a
table stays right about everything it already knew. **An operation the contract does not declare
answers 200 rather than raising** — this function runs inside the answer path of every request, so
raising would turn a table/contract drift into a page that cannot load, hiding the drift behind a
symptom; the drift itself is R85's, which refuses a route the contract does not declare.

**What it costs**: the contract travels in the bundle, 144 KB beside the 2.1 MB of seeds this layer
already carries, and the whole module is dropped with the layer when `__MOCKS_BUILT_IN__` is false.

**What it does NOT change**: nothing in the application. `lib/query-client.ts` reads `answer.ok` and
names 204/205/304 as the bodiless ones; 201 and 202 were always inside both readings.

### The rule — R170 (`harness/declared_codes.py`), on the `--contracts` tier

| Hold | What it reads |
| --- | --- |
| the families | one operation per declared family is really asked for, and the layer answers the contract's own code — read from `window.__mocks.answered()`, never from the browser's request events (the seam replaces `fetch`, so a mocked call fires none) |
| the record | what `answered()` reports IS what the response carried. A rule reading only the record would be green over a layer that recorded one code and sent another |
| the corpus | every operation the contract declares a non-200 success for is among the ones the rule asks for. The floor that makes the holds above mean something |
| the dial | a scenario asking only for a latency still gets the declared success (the branch a half-repair would leave at 200); a scenario asking for a failure still gets exactly it |

It is on the contracts tier because a declared code is a NAME the contract chose, and B-379 is exactly
one that had moved on one side only. It reads no database and costs one page.

**The mutation**: `const success = declaredSuccessStatus(operationId)` forced to `const success = 200`
in `scenario.ts`.

---
