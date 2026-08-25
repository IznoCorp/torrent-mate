// The settings and the secrets.
import { GET, POST, PUT, route } from "./shared";
import { mockState } from "../state";
import type { MockRoute } from "../router";

/** Every route this subject answers. */
export function configurationRoutes(): MockRoute[] {
  return [
    route("readSettings", GET, "/api/config/schema", () => mockState().settings),
    // A secret's VALUE is never read back. The seed carries which keys exist
    // and whether each is defined, and that is the whole of what this answers.
    route("readSecrets", GET, "/api/config/secrets", () => mockState().secrets),
    route("updateSecrets", PUT, "/api/config/secrets", (request) => {
      const held = mockState();
      const asked = request.body;
      if (typeof asked === "object" && asked !== null) {
        for (const key of Object.keys(asked as Record<string, unknown>)) {
          const known = held.secrets.find((secret) => secret.key === key);
          if (known !== undefined) known.defined = true;
        }
      }
      held.restartRequired = true;
      return { restartRequired: held.restartRequired };
    }),
    // Derived from the seeded settings, whose topics name their own files.
    route("readConfigurationFiles", GET, "/api/config/files", () => {
      const names = new Set<string>();
      for (const topic of mockState().settings) {
        for (const name of topic.fileNames) names.add(name);
      }
      return [...names].map((name) => ({ name, changed: false }));
    }),
    route("updateConfigurationFile", PUT, "/api/config/files/{name}", () => {
      const held = mockState();
      held.restartRequired = true;
      return { restartRequired: held.restartRequired, conflict: false };
    }),
    route("restartWeb", POST, "/api/config/restart-web", () => {
      mockState().restartRequired = false;
      return { ok: true };
    }),
    route("readConfigurationStatus", GET, "/api/config/status", () => ({
      readOnly: false,
      restartRequired: mockState().restartRequired,
    })),
  ];
}
