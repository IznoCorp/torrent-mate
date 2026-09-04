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

*(filled when the phase lands)*
