// What the locks block asks the server for.
//
// ONE READ, IN THE QUERY CACHE (invariant 4). The lock, the two sentinels and
// the sweep are four facts of ONE answer: asking for them separately would let
// the screen show a pipeline that holds nothing beside a pause that is on,
// which is a disagreement the server never sent.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import type { components } from "../../contract/types";

type Locks = components["schemas"]["Locks"];

/** The address, named once: the query key and the read must not drift apart. */
const LOCKS = "/api/maintenance/locks";

/** What holds the pipeline, and what a crash left behind. */
export const useLocks = () =>
  useQuery({
    queryKey: [LOCKS],
    queryFn: async () => (await read(LOCKS)) as Locks,
  });
