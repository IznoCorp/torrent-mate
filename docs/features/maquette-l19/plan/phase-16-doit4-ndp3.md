# Phase 16 — DOIT-4 and NE-DOIT-PAS-3: one instrument

## Objective

Two clause-map rows, one instrument: **a legitimate action asked under a busy scenario is
accepted and queued VISIBLY, never refused with a 409 or an « occupé ».**

`harness/arrivals.py` (R66) already holds the half that is served — a pipeline pass asked for
during a run says « Votre passage est en file » and the running pass carries on. **Every OTHER
mutation under a busy scenario is unproved**, and that is this rule's subject.

## The rule

One hold, over the mutations this lot's producers offer: for each, under a scenario where the
pipeline is running, the action is accepted, the interface says where it stands, and nothing
answers a refusal. The mutation makes one of them refuse and the hold falls naming it.

## The measurement this phase must take first — and the ruling it records

The DOIT-4 row says the resolve queue's own « En file » pastille « has no copy in `fr.json` and
no rule ». **Read against this lot's contract, « no surface changes »:**

- **If the queued state is DRAWN today**, the rule reads it and the row turns `served`.
- **If the pastille does not exist**, drawing it is a behaviour change and **it is not this
  lot's**. It is filed with an owner — L21 is the behaviour lot on these producers — and the row
  reads `partly` with the reason.

**A surface is not drawn to make a row green.** Which of the two it is, is measured here, with
the command, and recorded in this file and in `REPORT.md`.

## What the map reads afterwards

DOIT-4 and NE-DOIT-PAS-3 are amended with this rule named as their proof, or with the reason and
the owner for the half that is not this lot's. `docs/reference/product-intent-map.md` is
amended by proposal — the operator amends it — and the proposal is written in the pull request
body.

## Verdict

**Landed.** R124 (`harness/busy.py`), 7 holds, in the contracts tier.

### Stop B, taken and recorded

The plan named this stop: **if the resolve queue's « En file » pastille does not exist, drawing it
is a behaviour change and it is not this lot's.** It was measured, not assumed —
`grep "En file"` finds it nowhere in `i18n/fr.json` and nowhere in the tree outside the pipeline
pass's own sentence. **It does not exist.** DOIT-4's row reads `partly` with **L21** named and the
reason written. A surface is not drawn to make a row green.

### What R124 reads, and why it is three questions

The act LANDS (on the STATE — a toast can be right about nothing), nothing answers **409** (on the
NETWORK, because a rule reading only the screen passes a build that swallowed one), and nothing
anywhere says the machine is busy.

**The scenario is composed and the rule says so**: `arr-running` has the pipeline running and
nothing to take; `acq-now-loaded` has two media waiting and an idle pipeline. Driving the first
alone would have measured a page with no subject.

**« paused » was this rule's guess; the app's answer is `disabled`.** The hold reads the CHANGE
against what the status was before, never a word this file chose.

### The mutation

Making the take refuse while the pipeline runs fells it: « ['The Hawk','Backrooms'] →
['The Hawk','Backrooms'] ».

### The map, amended as a PROPOSAL

`product-intent-map.md` is the operator's to amend. DOIT-8 → `served` (R121), NE-DOIT-PAS-9 →
`served` (R122), NE-DOIT-PAS-3 → `served` (R124 with R66), DOIT-4 → `partly` with its owed half
named. Each row states what its rule READS, because the guard says itself that it cannot tell
whether a named proof reads its clause.

`check-markup-contracts` refused `[data-part="message"]` — emitted nowhere. Third time this wave.

### Readings

oracle **2 958, no divergence** · contracts **18 rules** + 26 guards, no violation ·
`check-intent-map.py` 23 clauses, 0 violations
