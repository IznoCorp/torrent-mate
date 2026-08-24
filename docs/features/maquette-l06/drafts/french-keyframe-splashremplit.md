# Drift finding — a French keyframe name the guard cannot see

Found during sub-phase 1.3 of L06 (an agent reading BLOCK 2 whole), not fixed
because it is outside the lot's letter: L06 folds values onto a scale and
refuses any markup or naming change beyond D-L06-4's publisher move.

**The finding.** `frontend/maquette/design/refonte.html` names a keyframe
`splashremplit` (used by `.splashbar i`). A keyframe name is a name someone
chose — code, under the English-names rule — and none of
`check-no-french.py`'s arms reads `@keyframes` names, so the gate is green
over it.

**What fixing it takes.** A rename with both ends moved in one step (the
`@keyframes` declaration and every `animation`/`animation-name` that reads
it), through the repository's rename discipline, plus — if the guard is to
ever see the next one — an arm that reads keyframe names. That is a naming
wave's work, not a scale wave's.

**Disposition.** To be carried by a later wave (the operator's call whether it
rides L07's surface conversion or a small naming pass); recorded here so the
finding survives this branch.
