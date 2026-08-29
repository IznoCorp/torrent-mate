# The amendment to rule 3 of `BUGS.md`

**What follows replaces rule 3 entirely**, in `## Rules of this file`. It is L10-bis's FIRST
commit, before any closure: a closing rule written after the closures measures nothing.

Dictated by the operator on 2026-08-28.

---

## The text as it stands, for comparison

```markdown
3. **A fix is not a fix without a rule that bites.** The rule is mutation-tested: break the
   behaviour on purpose, confirm the rule falls and names the right defect, restore. A closing
   entry names the script and the mutation.
```

## The text that replaces it

```markdown
3. **A fix is not a fix without a rule that bites, and the rule is RUN.** Mutation-tested: break
   the behaviour on purpose, confirm the rule falls and names the right defect, restore. A closing
   entry names the script, the mutation, and the run that passed — a command whose output nobody
   has seen is a claim.

   **When no instrument reaches the defect, building one is part of the work — never a reason to
   leave the entry open.** Dictated by the operator on 2026-08-28, and the count is why. Forty-one
   entries stood open that day and eight of them were closed in substance, held open by one
   sentence wearing the same shape: « not fixed here, it needs its own X ». That sentence satisfies
   the first half of this rule *perfectly* — a rule nobody wrote cannot fail its mutation — which is
   how the rule written to force proof became the rule that licensed deferral. It is written into
   B-036, B-041, B-055, B-057, B-058, B-061, B-100 and B-104, each time in good faith.

   **So every entry a wave takes is closed by an instrument that RAN**: the oracle, a harness hold,
   the accessibility tier, a guard arm, a test. The entry carries the command and its result.
   Where the instrument did not exist, the wave built it, and the instrument is the deliverable as
   much as the fix — B-139's own text says its defect « is measurable in twenty lines and nothing
   measures it », which is the whole of this rule in one line.

   **The one honest exception, and it is narrow.** Where no instrument can reach the defect, the
   entry names WHICH instrument cannot, WHY, and what was done instead. Two shapes have been met so
   far: prose in a document no guard greps (B-024 — a dead phase name cited as live), and a
   continuous-integration condition provable only by making the pipeline red on purpose (B-151).
   **An exception that is not named is indistinguishable from an instrument nobody built**, which
   is B-085's sentence with the reader replaced by a wave.
```

---

## What the amendment changes in practice

**An entry can no longer be closed by a reading.** « I checked, it is fixed » is not a closure; the
command and its output are.

**An entry can no longer stay open because the instrument is missing.** That is the reversal, and
it is the one the operator dictated: the absent instrument becomes the work.

**An entry may still be closed without an instrument** — but it must say which one cannot reach it
and why. Two entries of this wave are in that case and are named in advance, so the exception is
not discovered at the moment it happens to be convenient.

## The trap this amendment can create, and it belongs here

A rule demanding an instrument for every closure pushes towards **writing the instrument easiest to
make pass**, not the most revealing. That is B-075 and it has been paid for six times: a floor set
at the current value, an empty read passing in silence, a corpus enumerated by hand.

The counter-measure is already in the rule: **the mutation**. An instrument that does not fall when
the behaviour is broken on purpose is not an instrument, and the closing entry must show it fallen
before showing it green. This is not a formality appended at the end — it is the only moment where
anything is learned about the guard just written.
