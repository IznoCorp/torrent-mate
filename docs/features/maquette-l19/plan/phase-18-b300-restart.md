# Phase 18 — B-300: the restart is confirmed

## **This is a BEHAVIOUR phase. It is alone in its commit, and its rule is seen RED first.**

## Objective

`legacy.js:9590` sets `redemarrage = true` on a setting's save, and the `dataset.restart` branch
drops the flag and toasts « Service redémarré ». **There is no confirmation.**

**§17 is the clause**: a restart cuts the service for every account of the household — the case
NE-DOIT-PAS-6's spirit covers even though nothing is destroyed. Production confirms first.

## What changes

- The confirmation is `ui/dialog` — its paragraph colour and its danger contrast held by R116
  since L12, so the surface is already proved and this phase adds no drawing primitive.
- The copy lands in `fr.json`.
- **Nothing else changes**: no verb is added, the restart itself is untouched, and the flag's
  lifecycle is the same on the confirmed path.

## The rule that bites — RED FIRST

Written and run **before** the confirmation exists: it walks the tap, expects a dialog, and
**must fall** saying the restart happened on the tap. That reading is written into this file
before the repair.

Then the repair, and the rule walks the whole path:

1. tap « Redémarrer maintenant »;
2. read the dialog;
3. **cancel** — and read the flag STILL UP and no toast. *(This is the half that separates a
   confirmation from a delay, and the half a cheaper hold would skip.)*
4. tap again, confirm, and read the toast.

The mutation removes the confirmation and the hold falls at step 2. Restored.

## Gates

The oracle — a new dialog on a new path; the divergence is described · `--a11y` on the state that
raises it (a modal's `inert` background and its focus trap are `app/focus.ts`'s and already
held) · `--contracts`.

## Verdict

**Landed**, alone in its commit, its rule seen RED first (five holds, before the confirmation
existed).

### A rule was asserting the defect

`harness/page_host.py` held « and a real tap on the restart offer **TAKES** it » — the behaviour
B-300 calls a defect, written down as a requirement. **B-085's species from the closest possible
range**: a rule can certify the defect, and this one did for as long as the defect stood. It reads
« ASKS before it takes it » now.

Its three neighbours then failed for a reason that was not theirs — a modal left up makes every
later tap « present but not tappable » — so the walk dismisses the confirmation before going on.
Worth naming: **a repair's first symptom was three unrelated holds falling.**

### The sentence says what §17 makes it a confirmation FOR

Unavailable **for every account of the household, not only for you**, and an acquisition in flight
resumes where it stopped. « Êtes-vous sûr ? » would have been a dialog that says nothing — and it
is what a confirmation added without reading §17 would have said.

### The cancel is the half that matters

A build that raised a dialog and restarted anyway satisfies every check that only taps through.
Cancelling leaves the restart OWED and says nothing about one having happened; only confirming
restarts, and then it says so.

### Readings

oracle **2 958, no divergence** · contracts 18 rules + 26 guards, no violation · `settings.py`
57 → **65** holds · `page_host.py` 44, no violation · mutation: the confirmation short-circuited
fells **five** holds in `settings.py` and **one** in `page_host.py`
