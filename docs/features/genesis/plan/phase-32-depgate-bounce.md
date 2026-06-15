# Phase 32 — Dep-gate bounce-back

When the hybrid dependency gate (#13, DESIGN §9) blocks a launch (unmet `Depends on #N`), bounce the card BACK to its from-column via the board writer and post a dep-named recap comment, instead of stranding it in the triggering column — mirroring the un-whitelisted-move ROLLBACK mechanics (bounce-target baseline + bookkeeping anti-loop marker so it does not re-trigger).
