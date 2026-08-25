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
        for (const [key, value] of Object.entries(asked as Record<string, unknown>)) {
          const known = held.secrets.find((secret) => secret.key === key);
          // An EMPTY value clears a secret. Marking a key defined because it
          // was mentioned would make clearing one look like setting it.
          if (known !== undefined) known.defined = value !== "";
        }
      }
      held.restartRequired = true;
      return { restartRequired: held.restartRequired };
    }),
    // Derived from the seeded settings, whose topics name their own files.
    route("readConfigurationFiles", GET, "/api/config/files", () => {
      const held = mockState();
      const names = new Set<string>();
      for (const topic of held.settings) {
        for (const name of topic.fileNames) names.add(name);
      }
      return [...names].map((name) => ({
        name,
        changed: held.changedFiles.includes(name),
      }));
    }),
    // A write is RECORDED, or the next read contradicts it: save a file, list
    // the files, and nothing had changed.
    route("updateConfigurationFile", PUT, "/api/config/files/{name}", (request) => {
      const held = mockState();
      const name = request.parameters.name;
      if (!held.changedFiles.includes(name)) held.changedFiles = [...held.changedFiles, name];
      held.restartRequired = true;
      return { restartRequired: held.restartRequired, conflict: held.conflict };
    }),
    route("restartWeb", POST, "/api/config/restart-web", () => {
      const held = mockState();
      held.restartRequired = false;
      held.changedFiles = [];
      return { ok: true };
    }),
    route("readConfigurationStatus", GET, "/api/config/status", () => {
      const held = mockState();
      return { readOnly: held.readOnly, restartRequired: held.restartRequired };
    }),
  ];
}
