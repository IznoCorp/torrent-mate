// Maintenance — the commands run against the library
//
// The shapes this feature's reads answer, declared where the subject lives.

import type { Schemas } from "../../lib/contract-schemas";

// The deletion journal: how many destructive operations the library has been
// through, and the rows describing them.
export type DeletionJournal = Schemas["DeletionJournal"];

// One maintenance COMMAND. `g` is its rubric, `r` its risk (a key of `RISQUES`),
// `long` whether it can take a while, `blanc` whether it can run dry.
export type MaintenanceAction = Schemas["MaintenanceAction"];
