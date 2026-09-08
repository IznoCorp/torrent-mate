// What Configuration asks the server for.
//
// TWO READS. The settings themselves, and which secrets exist — a secret's
// VALUE is never read back, and the layer answers only which keys there are and
// whether each is defined.
import { useQuery } from "@tanstack/react-query";
import { HELD, read, send } from "../../lib/query-client";
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

/** What the layer answers when a configuration file is written. */
export type WriteOutcome = { restartRequired: boolean; conflict: boolean };

/**
 * Writes one configuration file, and says what came back.
 *
 * THE CONFLICT IS A FIELD OF THE ANSWER, not a status. The contract declares
 * `updateConfigurationFile` answering `{ restartRequired, conflict }` on 200
 * and it declares 409 for a refusal — so « the file moved under the editor » is
 * something the write SUCCEEDS in telling, and drawing it from an error branch
 * would be drawing it from a case the contract does not describe. Recorded
 * because the brief that asked for this banner said production answers 412: the
 * maquette's contract is its own artefact (D7), and this follows it.
 *
 * Args:
 *     name: The file.
 *     values: What to write into it.
 *
 * Returns:
 *     What the layer answered.
 */
export async function writeConfigurationFile(
  name: string,
  values: Record<string, unknown>,
): Promise<WriteOutcome | undefined | typeof HELD> {
  // `HELD` AND `undefined` ARE REAL ANSWERS AND NEITHER IS AN OUTCOME. Offline,
  // the outbox keeps the write and `send` answers the symbol; a 204 answers
  // nothing at all. In both cases the caller has nothing to draw a conflict
  // from and must not invent one, so they are passed through rather than
  // flattened — which is what lets it tell « the file moved » from « nobody has
  // answered yet ».
  return send<WriteOutcome>(
    "PUT", `/api/config/files/${encodeURIComponent(name)}`, values);
}
