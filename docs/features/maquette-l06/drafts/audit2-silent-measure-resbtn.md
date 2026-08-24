# Drift finding — audit2's R12 measures four primaries and thinks it holds five

Found while repairing R12's pinned size during L06, not fixed because it is a
rule-shape change outside the lot's letter.

**The finding.** `audit2.py:65` — `measure()` returns silently when its
selector finds nothing. `.resbtn` ("search result") is one of the five
contexts R12 names, and it is absent from the state the rule visits
(`acq-add-results`), so only four primaries are ever measured. A hold that
measures nothing reads as a hold that passed — the exact family of hole
`type_scale.py` was written to refuse, and `a gate proves what it READS`.

**What fixing it takes.** Either the rule visits a state that paints
`.resbtn`, or `measure()` refuses an empty selection the way `type_scale.py`'s
"is drawn by a named state" holds do. Either way the change is mutation-tested
(hide the element, watch the rule fall).

**Disposition.** A later wave's rule work; recorded so the finding survives
this branch.
