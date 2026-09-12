// Which features own a tap verb, and nothing about what any of them does.
//
// WHY IT EXISTS, and it is two reasons that arrive together. `lib/verbs.ts`
// holds the registry and may import no feature; a feature may import no other
// feature (invariant 7). So the list of features that register a verb has to
// live in the frame — and `shell.tsx`, which held it, stands at the 400-line
// ceiling, which invariant 6 says is never extended.
//
// IT IS THE SPECIES INVARIANT 10 BLESSES BY NAME: one import per feature, the
// same shape as `app/router-tree.tsx`'s one import per page and
// `app/live-updates.ts`'s one import per domain. It names no VERB and no
// attribute — `data-rescrape` is spelled in `features/media/`, where a medium
// is known, and `data-maintenance-run` in `features/maintenance/`.
import type { QueryClient } from "@tanstack/react-query";
import { installJourneyVerbs } from "../features/acquisition/journey-verbs";
import { installMaintenanceVerbs } from "../features/maintenance/action-verbs";
import { installMediaVerbs } from "../features/media/media-verbs";

/**
 * Registers every feature's tap verbs into the one registry.
 *
 * Called from the boot, after `installVerbs()` and before anything can be
 * tapped: a verb registered inside a component would be registered after the
 * first render, and the panels these verbs are drawn on can be raised from a
 * cold load at an address anyone can type.
 *
 * Args:
 *     client: The cache the verbs read and put back.
 */
export function installFeatureVerbs(client: QueryClient): void {
  installJourneyVerbs(client);
  installMaintenanceVerbs(client);
  installMediaVerbs(client);
}
