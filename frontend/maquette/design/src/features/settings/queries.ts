// What Configuration asks the server for.
//
// TWO READS. The settings themselves, and which secrets exist — a secret's
// VALUE is never read back, and the layer answers only which keys there are and
// whether each is defined.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { Secret, SettingsTopic } from "./reference";

/** The settings, by topic. */
export function useSettings() {
  return useQuery({
    queryKey: ["/api/config/schema"],
    queryFn: async () =>
      toEngineShape<SettingsTopic[]>("SETTINGS", await read("/api/config/schema")),
  });
}

/** Which secrets exist, and whether each is defined. */
export function useSecrets() {
  return useQuery({
    queryKey: ["/api/config/secrets"],
    queryFn: async () =>
      toEngineShape<Secret[]>("SECRETS", await read("/api/config/secrets")),
  });
}
