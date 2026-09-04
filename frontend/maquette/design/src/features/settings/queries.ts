// What Configuration asks the server for.
//
// TWO READS. The settings themselves, and which secrets exist — a secret's
// VALUE is never read back, and the layer answers only which keys there are and
// whether each is defined.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { Secret, SettingsTopic } from "./reference";

/**
 * The settings, by topic, as a query DEFINITION.
 *
 * A DEFINITION AND NOT ONLY A HOOK: the page subscribes, and the setting PANEL
 * is produced from a click — and from a cold load at `?panel=setting:<id>`,
 * where no page has mounted. One definition, so the two cannot drift into two
 * shapes of one answer (§13).
 */
export const settingsQuery = {
  queryKey: ["/api/config/schema"],
  queryFn: async () =>
    toEngineShape<SettingsTopic[]>("SETTINGS", await read("/api/config/schema")),
};

/** The settings, by topic. */
export function useSettings() {
  return useQuery(settingsQuery);
}

/** Which secrets exist, and whether each is defined — as a definition. */
export const secretsQuery = {
  queryKey: ["/api/config/secrets"],
  queryFn: async () =>
    toEngineShape<Secret[]>("SECRETS", await read("/api/config/secrets")),
};

/** Which secrets exist, and whether each is defined. */
export function useSecrets() {
  return useQuery(secretsQuery);
}
