// the engine's derived read model over the staging queue
//
// A queue card exactly as `BLOCKED` / `STUCK` / `STUCK_REAL` shape one — the
// source carries more fields (`s`, `chip`, `strip`, `noposter`…) than any one
// reader needs, so this stays the same loose index shape as `MediaSheet`
// rather than a speculative closed type: a caller narrows the fields it
// actually reads, starting with `t` to match against a decision's `d`.
export type QueueCard = Record<string, unknown>;
