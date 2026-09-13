# Phase a·2 — The seams become imports

A CONVERSION: product code stops reading the shell's own `window.__` names and imports their owners instead,
and the window publications a rule reads move to `harness/publish.ts` (new file) (DESIGN § 4.2; § 3, rows
6–8).

## The proof FIRST

- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST. No movement
  is expected: the rules read the same names on `window`, now published by `harness/publish.ts` (new file).
- **`identity.py` is RE-AIMED.** Today it reads the inline `window.__servedIdentity=` marker in the served
  HTML (`identity.py:122`). It will read the `<script type="application/json" id="served-identity">` element
  instead, with its count unchanged, said in its docstring.
- **`outbox.py` is unchanged.** A named-state reset still clears the IndexedDB outbox, now through an
  import. Only its wording changes, and only where its docstring names the window read.
- **The oracle**: zero divergence.
- **The closing reading.** Re-run the Python pass of DESIGN § 2.4. Product code outside `engine/` now reads
  only the engine's six names: `__referentiel`, `__navigationState`, `__closeLayers`, `__derouler`,
  `__announcePops`, `__startEngine`.

## The move

- **`harness/publish.ts` (new file).** It publishes every seam a rule reads that the product owns,
  under its existing name, and `installHarness` calls it.
- **The 19 names become imports of their owners** (DESIGN § 4.2):
  - `store` from a boot singleton in `app/store.ts`;
  - `toast` from `app/toast-host.ts`;
  - `bridge` and `screens` from `app/history-bridge.ts`;
  - `panel` from `app/panel-host.ts`;
  - the query client from `lib/query-client.ts`;
  - each feature-published name from its own module.

  The phase re-takes the per-name reader list (the § 2.4 pass prints it) before it moves anything.
- **One reader crosses a feature, and it composes in the route** (DESIGN § 4.2).
  `features/media/media-screen.tsx:74` reads `window.__followActions`, which
  `features/acquisition/queries.ts` publishes. Invariant 7 forbids the import, so the route that mounts the
  media screen passes the follow actions in as a property. The layering arm of
  `scripts/check-frontend-boundaries.py` reads clean on it.
- **The engine's own `window` reads become imports through `engine/seams.ts` in this same phase**
  (DESIGN § 4.2): `harness/publish.ts` publishes only what a RULE reads, so a build with
  `__MOCKS_BUILT_IN__` off must start an engine that reads no publication.
- **`__servedIdentity`.** `serve.py` writes the JSON element through `host_identity.py`
  (`with_served_identity`) instead of an inline script, and `lib/served-identity.ts` reads the element.
- **`__mocks`.** `app/outbox-wiring.ts:85` imports the mock layer's reset behind `__MOCKS_BUILT_IN__`.
- **`__navEchec`.** Product code writes it in six places (the § 2.4 pass lists them), and a·1 gave the reset
  to `harness/drive.ts` (new file, a·1). The phase re-takes those writes before moving them.
- **Nothing stays published for the engine's sake.** The engine's reads were made imports above; what
  `publish.ts` (new file) publishes is exactly the set a rule reads, and the commit body lists it.
- **Invariant 10.** `lib/` imports `app/` only where the name is shape rather than domain
  (`lib/store-access.ts` already works this way). `ui/` never imports a feature.
- **`legacy.js` does not grow.** If an engine read changes, the ledger is re-recorded DOWNWARD.

## Gate

Per INDEX « Gates ». In addition: the § 2.4 pass's closing reading goes in the report, and a build with
`__MOCKS_BUILT_IN__` off boots to the entry page with no error in the console. STOP D if the layering arm
refuses the route composition of `__followActions`.

## Commit

`refactor(maquette-l13): product code imports the shell's seams and the harness publishes them`

## Amended 2026-09-13 — the steward's ruling on STOP D

**Measured before anything moved.** A projection of `check-frontend-boundaries.py`'s fan-in arm (its own
`build_graph`, one edge per reader to the owner this file named) put five modules over the ceiling of 4:
`app/history-bridge.ts` 1 → 9, `app/toast-host.ts` 1 → 9, `app/panel-host.ts` 1 → 7, `app/store.ts` 3 → 7,
`features/acquisition/queries.ts` 2 → 5 (one feature; the rest are buckets).
Re-run it rather than believe it — on a·1's head, extracted anywhere:

    mkdir /tmp/l13a-projection
    git archive 79db420b3 scripts frontend/maquette/design/src | tar -x -C /tmp/l13a-projection
    python3 docs/features/maquette-l13/plan/fanin_projection.py /tmp/l13a-projection

**Void: the app hosts as import owners of the four shell doors and of the store.** R1: `toast`, `panel`,
`bridge` and `screens` live in ONE door module, `lib/shell-doors.ts`, declared as `let` bindings and filled
by their app host at install (`engine/seams.ts`'s pattern); `store` lives beside the existing door in
`lib/store-access.ts`, filled by the boot (`installStore`). The query client is `lib/query-client.ts`'s
`sharedQueryClient` (`installSharedQueryClient`); the address model the engine asks is `lib/addresses.ts`'s
`addressSeam`. Features, `engine/seams.ts` and `harness/publish.ts` import the doors; no
`lib/` module imports an `app/` value.

**R2: one `FAN_IN_EXEMPT` entry, `features/acquisition/queries.ts`**, carrying its lifetime in its comment.
**The L13b phase that deletes the engine's edge to it** — the acquisition verbs leaving (b·5) or
`engine/seams.ts` dying (b·11), whichever removes the last engine read of `followActions`/`suggestions` —
**removes the entry in the same commit.**

**The six `window.__navEchec = true` WRITES stay as they are.** The move this file planned rested on « a·1
gave the reset to `harness/drive.ts` », which RESUME's ruling 6 made void; a write is not a read, and no home
was named for them.

**Found while moving, and done in this phase:**
- The engine read `__bridge` as a BARE global on 13 code lines, invisible to the `window.__` pass; they call
  the `bridge` it already imports.
- `window.__mocks` stays published by the mock layer itself: `check-frontend-boundaries.py`'s `mocks` arm lets
  only `app/` import `mocks/`, so neither the harness nor `engine/seams.ts` may. `app/outbox-wiring.ts`
  imports `mockLayer` behind the constant; the engine's `resetSettings` — called only by the harness — keeps
  its `window.__mocks?.` read.
- The engine's other twenty reads go through `seam`, a getter object in `engine/seams.ts` (the engine has
  locals named `toast`, `entry`, `suggestions`).
