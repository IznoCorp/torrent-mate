# Phase 03 — Maintenance: the action panel

## Objective

`openActionMaintenance` (`legacy.js:5822–5878`, 57 lines, one caller through `data-maintact`)
moves to `features/maintenance/panel-action.ts`, kind `action`, address `action:<id>`.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- It reads `MAINT_ACTIONS`; the feature already asks for it —
  `features/maintenance/queries.ts`'s `useMaintenanceActions()` caches
  `["/api/maintenance/actions"]`. The producer reads that key from the cache, so the engine's
  copy of the family loses its producer reader.
- **`MAINT_ACTIONS` leaves `app/engine-data.ts`'s `NEEDED`** — the file's own header says why
  that list exists (« what the dying engine reads with no component to ask for it ») and a React
  producer asks for what it draws. What remains in `NEEDED` after this phase is written below.
- `legacy.js:32359` still validates a `action:<id>` address against the family. That is the
  LADDER's, which is L13's, not a producer's: it stays, and this phase says so rather than
  moving a second subject.
- `MAINT_TOPICS` and `RISQUES` do **not** move: the register classes them `interface` — a
  rubric's name and the sentence warning what it deletes are the interface's own words.
- R100 hold (f) gains `maintenance-topic`.

## The rule that bites

`harness/producers.py` gains the `action` kind: the panel is opened through the seam by address
and its title is the action's own. The mutation removes the registration and reads it fall.

Second mutation, on the DATA path rather than the seam: the producer's cache read is pointed at a
key nothing fills, and the hold must fall saying the panel drew nothing — a producer reading the
engine's accessor instead of the cache would survive the first mutation and not the second.

## Verdict

**Landed**, over three commits — the move, and two rules the move's own mutations demanded.

### What the phase changed beyond its own producer

**A registration is an OBJECT now** — `registerProducer(kind, { produce, needs, holds })`. A
positional third argument is a positional fourth waiting to happen, and the three answers are
about one subject.

**`holds` exists because the engine answered « does this interface hold this subject » from its
own fixture**, and that is exactly what keeps a fixture alive after its producer has left. The
addressed-panel table asks it before opening a panel from an address a reader can type — a
producer answers for anything, which is right inside the application and wrong for a typed
address. `REOPEN`'s `action` entry now reads the feature for both halves.

**`RISQUES` left the engine entirely**, the producer having been its last reader there, and it is
split on the line the language rule draws: the WORD is interface text (`fr.json`), the TONE is a
token name and is code (`features/maintenance/risks.ts`). `page.tsx` reads the same derivation,
so the page and the panel answer one question once (§13). The register records the conversion;
the reference slice drops the member.

**`app/panel-contributions.ts`** — the boot list left the shell, because it gains an entry per
feature converted and the shell may only lose lines. 397 → **392**.

### The mutations, and the two rules they forced

| # | Mutation | Rule | Outcome |
| --- | --- | --- | --- |
| 1 | `holds: () => true` | `producers.py` | fell — « and refuses one it does not (action) — no-such-command » |
| 2 | `destructive: "danger"` → `"success"` | `machine.py` | **fell NOTHING.** See below |
| 2-bis | the same, after the repair | `producers.py` | fell — « {'tone': 'success', 'text': 'supprime'} · expected tone 'danger' » |

**Mutation 2 is the phase's finding, and it is a guard-green-over-what-it-does-not-read.** A
destructive command announced in the SUCCESS tone fell no rule at all: `machine.py` walks that
very panel and reads its ACTIONS; the oracle measures a region ROOT and a chip is a child of one;
nothing anywhere asked what colour a command that deletes is announced in. It is a reassuring lie
about the one thing that panel exists to say, and the risk vocabulary had just been split in two
by this phase — so the half nobody read was the half that had just moved.

R120 reads the drawn chip's `data-tone` now, and one line further, that the chip's WORD is a word
and not an unresolved `panels.` key — the failure mode a copy move introduces, which renders like
a label until somebody looks.

### Readings

| Gate | Reading |
| --- | --- |
| **oracle** | 2 958 measurements, **NO DIVERGENCE** |
| `run.sh --contracts` | 14 rules, 26 guards, no violation |
| `producers.py` alone | **14 holds, no violation** |
| `machine.py` alone | 89 holds, **1 violation — B-308, pre-existing** |
| `app/shell.tsx` | 397 → **392** |
| `engine/legacy.js` | 32 436 → **32 376**, re-recorded |
| `check-frame-domain.py` | `app/` 129 → **126**, ceiling lowered in the same commit |
| `engine-data.ts` `NEEDED` | one entry fewer |

### B-308 — filed, not repaired

`machine.py` reads « 6 schedulers drawn vs 7 real » since `personalscraper-index-full` was
scheduled on `main` (`4c0e274a7`, #557). **Measured as pre-existing**: this branch touches
neither the rule nor the `SCHEDULERS` fixture (`git diff origin/main...HEAD` on both is empty).
Drawing the seventh row is a surface change this lot's contract forbids, and the first review
rule forbids a conversion wave from carrying it. The larger finding is in the entry: the fixture
and the machine are one contract, and only one end has a guard a backend pull request passes.

### Deviation

**`MAINT_ACTIONS`'s fixture does NOT die with its producer**, and saying so is the point. The
engine's ladder still reads it — `REOPEN`'s validation now asks the feature, but the family is
also published to the maintenance PAGE through the reference. It dies when that reader goes,
which is L13's. The producer's own reading of it is gone, which is what this phase owed.
