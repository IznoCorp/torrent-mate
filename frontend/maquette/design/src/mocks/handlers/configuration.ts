// The settings and the secrets.
import { GET, POST, PUT, route } from "./shared";
import type { components } from "../../contract/types";
import { mockState } from "../state";
import { refused, type MockRoute } from "../router";
import { configurationFiles, writeFileContent } from "../configuration-files";
import { activationRefusal } from "./trackers";
import { stopRunningCrossSeeds } from "./cross-seed";

// Why a file's read is refused: the layer holds no content under that name.
const UNKNOWN_FILE = "no configuration file carries that name";

/** The contract's own shapes, as every module that names one reads them. */
type Schemas = components["schemas"];

/** What separates a setting's file from its key in the identity it is addressed by. */
const IDENTITY_SEPARATOR = ":";

/**
 * Whether one setting is the one an identity names.
 *
 * A SETTING IS ADDRESSED AS `<file>:<key>` — the spelling the row, the panel's
 * address and the body of a write all use. It is taken APART here rather than
 * built up: the interface owns that spelling, and a second place that composes
 * it is a second place it can drift.
 */
function isNamedBy(setting: Schemas["Setting"], identity: string): boolean {
  const separator = identity.indexOf(IDENTITY_SEPARATOR);
  return separator > 0
    && setting.file === identity.slice(0, separator)
    && setting.key === identity.slice(separator + 1);
}

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
    // ONE FILE'S CONTENT, as the layer holds it — what an editor opens on.
    route("readConfigurationFile", GET, "/api/config/files/{name}", (request) =>
      configurationFiles().find((file) => file.name === request.parameters.name)
        ?? refused(404, UNKNOWN_FILE)),
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
    //
    // AND THE VALUE IS KEPT, which is B-342. This handler recorded the file's
    // NAME and never read the request's BODY, so the next `readSettings`
    // answered the seed: the operator saved, was told « Enregistré », and
    // watched the row go back to what it had been. A layer that answers
    // without moving certifies nothing (D7), and an interface that says a
    // thing was done when it was not is NE-DOIT-PAS-1 — the two halves of one
    // defect, and this is the half that lives here.
    route("updateConfigurationFile", PUT, "/api/config/files/{name}", (request) => {
      const held = mockState();
      const name = request.parameters.name;
      // A FILE THAT MOVED TAKES NOTHING. « Rien n'a été écrit » is what the
      // conflict banner says, so a layer that recorded the values anyway would
      // make the banner a lie one level down — which is the very species this
      // handler was repaired for.
      //
      // TWO WAYS A FILE MOVES, and the difference is B-345's settings half.
      // `conflict` is a DIAL — a property of the request, raised by a rule
      // that then reads what it raised. `movedFiles` is a property of the
      // FILE, seeded, so a HAND with no dial reaches B-299's banner simply by
      // saving a setting that lives in it.
      // A TRACKER STILL FAILING IS NOT SWITCHED BACK ON: the write is refused
      // whole, in the engine's own words, and nothing lands (demand T2).
      const refusal = activationRefusal((request.body ?? {}) as Record<string, unknown>);
      if (refusal !== null) return refused(422, refusal);
      const changedOnDisk = held.conflict || held.movedFiles.includes(name);
      if (changedOnDisk) return { restartRequired: held.restartRequired, conflict: true };
      const asked = request.body;
      // A WHOLE FILE travels with the digest its editor read it at — the
      // precondition — and replaces the content the next read answers.
      const fileBody = asked as { values?: Record<string, unknown>; digest?: unknown } | null;
      if (typeof fileBody?.digest === "string" && typeof fileBody.values === "object" && fileBody.values !== null) {
        if (!writeFileContent(name, fileBody.values, fileBody.digest)) {
          return { restartRequired: held.restartRequired, conflict: true };
        }
      }
      if (!held.changedFiles.includes(name)) held.changedFiles = [...held.changedFiles, name];
      if (typeof asked === "object" && asked !== null) {
        // The body is keyed by the setting's own identity — `<file>:<key>`,
        // the spelling the row, the address and the save all use — so the
        // written value lands on the setting it was typed into and on no
        // other.
        for (const [identity, value] of Object.entries(asked as Record<string, unknown>)) {
          for (const topic of held.settings) {
            for (const setting of topic.settings) {
              if (!isNamedBy(setting, identity)) continue;
              setting.raw = value;
              // `displayedValue` is what the contract carries as the value's
              // own SUMMARY, and it is a string where `raw` is anything. Left
              // behind, the panel's « Valeur enregistrée » would go on quoting
              // the seed under a raw value that had moved — the same
              // contradiction one field lower down. Written as the interface
              // would say it, never as `[object Object]`: a structure has no
              // control that can edit it, so none ever arrives here.
              setting.displayedValue = String(value);
            }
          }
        }
      }
      // « COUPER AUSSI LES CROSS-SEEDS EN COURS » (round 9 Q5): the running pairs
      // stop in the SAME call the switch is written by, never a second one.
      if (request.query.get("stopRunningCrossSeeds") === "true" && typeof asked === "object" && asked !== null) {
        stopRunningCrossSeeds(asked as Record<string, unknown>);
      }
      held.restartRequired = true;
      return { restartRequired: held.restartRequired, conflict: false };
    }),
    route("restartWeb", POST, "/api/config/restart-web", () => {
      const held = mockState();
      held.restartRequired = false;
      held.changedFiles = [];
      return { ok: true };
    }),
    route("readConfigurationStatus", GET, "/api/config/status", () => {
      const held = mockState();
      return { restartRequired: held.restartRequired };
    }),
  ];
}
