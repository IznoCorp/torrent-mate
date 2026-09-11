// WHICH SEASONS WERE ASKED FOR WHILE THE MACHINE WAS BUSY — DOIT-4's visible
// half.
//
// THE CLAUSE, AND WHAT WAS MISSING FROM IT. DOIT-4 asks that an ask arriving
// while the pipeline runs be QUEUED VISIBLY — « En file — pipeline en cours » —
// and never refused. The refusing half was already true: the layer answers
// `queued` and the verb says so. What was missing is the word VISIBLY. The
// verb said it in a message, and a message is gone in four seconds; after it
// went, nothing on the screen said the season was waiting, so the operator who
// looked away had no way to tell an ask that was queued from one that never
// happened. « Said once » is not « visible ».
//
// WHY IT IS HELD IN THE CACHE AND NOT IN A MODULE'S OWN VARIABLE. The season
// list is drawn by a component, and a component redraws when something it READS
// changes. A module-level set would be read once and never again — the pastille
// would appear only if some other change happened to redraw the row, which is a
// surface that works by luck. The cache is what every other fact on this sheet
// is read through (invariant 4), so this one is read the same way and the
// redraw is the cache's business rather than this file's.
//
// IT IS A CLIENT-ONLY KEY, and that is a DEBT rather than a design. The durable
// answer is the server saying so: a season the backend has queued should come
// back queued, the way a season being acquired comes back with its status, and
// then this file is deleted rather than adapted. Until the backend answers it,
// the interface remembers its own ask — which is honest about what it knows
// (« I asked, and I was told it was queued ») and says nothing it has not been
// told. Recorded as a demand on the backend rather than left as a client
// invention.
import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

/** The cache key holding one medium's queued seasons. */
function keyFor(title: string): [string, string] {
  return ["queued-seasons", title];
}

/**
 * Records that a season's grab was answered « queued ».
 *
 * Args:
 *     client: The cache the surfaces read.
 *     title: The medium, as this interface knows it.
 *     season: The season number, 1-based.
 */
export function markSeasonQueued(
  client: QueryClient,
  title: string,
  season: number,
): void {
  const held = (client.getQueryData(keyFor(title)) as number[] | undefined) ?? [];
  if (held.includes(season)) return;
  client.setQueryData(keyFor(title), [...held, season]);
}

/**
 * Forgets a medium's queued seasons.
 *
 * THE ASK IS FORGOTTEN WHEN IT STOPS BEING TRUE, and the moment is the medium's
 * own facts moving: what was queued has either started or is no longer waiting,
 * and the season's own status then says which. A pastille that outlived the
 * wait would be the same defect one step later — a screen asserting something
 * about the machine that the machine no longer agrees with.
 *
 * Args:
 *     client: The cache the surfaces read.
 *     title: The medium, as this interface knows it.
 */
export function forgetQueuedSeasons(client: QueryClient, title: string): void {
  client.removeQueries({ queryKey: keyFor(title) });
}

/**
 * The seasons of one medium whose grab is waiting on the pipeline.
 *
 * Returns:
 *     Their numbers, empty when none is waiting.
 */
export function useQueuedSeasons(title: string): number[] {
  const client = useQueryClient();
  const { data } = useQuery({
    queryKey: keyFor(title),
    // IT ASKS NOBODY. The key holds what this interface was told by an answer
    // it already has; a fetcher here would be a request for a fact no endpoint
    // serves, and `enabled: false` says that in the one place a reader looks.
    queryFn: () => (client.getQueryData(keyFor(title)) as number[]) ?? [],
    enabled: false,
    initialData: [] as number[],
  });
  return data;
}
