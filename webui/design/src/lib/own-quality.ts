// The account's own quality floor on one acquisition, and the floor in force
// (§ 17; round 10 Q6) — read and written by the quality screen, which belongs to
// the releases feature and may not import the acquisition one (invariant 7).
import i18next from "i18next";
import { useQuery, type QueryClient } from "@tanstack/react-query";

import { read, send } from "./query-client";
import { toast } from "./shell-doors";
import { useUiState } from "./store-access";
import type { Schemas } from "./contract-schemas";

// The follows' own read — the key the acquisition feature reads them under.
const FOLLOWS_KEY = ["/api/v1/acquisition/followed"];

/**
 * The follow one title names, as the follows' read answers it.
 *
 * @param title The acquisition.
 * @returns The follow, or undefined when none carries that title.
 */
export function useFollowOf(title: string): Schemas["Follow"] | undefined {
  // PER WORLD, under the key the acquisition feature caches them at: the dense
  // world's follows are not the real one's.
  const world = useUiState().scen === "loaded" ? "loaded" : "";
  const { data } = useQuery({
    queryKey: [...FOLLOWS_KEY, world],
    queryFn: async () =>
      read<Schemas["Follow"][]>("/api/v1/acquisition/followed", new URLSearchParams(world ? { scenario: world } : {})),
  });
  return data?.find((one) => one.title === title);
}

/**
 * Writes the caller's own quality floor on one of its follows.
 *
 * @param client The cache the follows are read from again.
 * @param title The follow.
 * @param floor The resolution floor, or null to follow the default profile.
 */
export async function setOwnQuality(client: QueryClient, title: string, floor: string | null): Promise<void> {
  try {
    await send("PUT", `/api/v1/acquisition/followed/${encodeURIComponent(title)}/quality`, { profile: floor });
    await client.refetchQueries({ queryKey: FOLLOWS_KEY });
  } catch {
    toast?.show({ message: i18next.t("verbs.acquisitionSettings.refused") });
  }
}
