// The named states of the configuration page, « Réglages ».
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { EVERY_WRITE } from "./rights";
import { applyState, type NamedState } from "../drive";
import { resetSettings } from "../settings-reset";
import { SETTINGS_STATE } from "../../features/settings/state";
import { askToLeave } from "../../app/leave-confirm";
import { owed } from "../owed";

// Long enough that a read held back is still in flight when the state is measured.
const HELD_BACK = 60000;
// Long enough that the ranking file's read has answered and its fields are drawn.
const TYPE_AFTER = 250;
// Long enough that the typed weight has been rendered and the save opened.
const SAVE_AFTER = 50;

/**
 * Types a weight two above the first criterion's and taps « Enregistrer », as a
 * finger would once the file is read.
 */
function saveTypedWeight(): void {
  owed(() => {
    const field = document.querySelector<HTMLInputElement>(
      '[data-part="ranking/criterion"] [data-part="ranking/weight"]');
    if (field === null) return;
    // THE NATIVE SETTER, so the controlled field hears the input event as typing.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
      ?.call(field, String(Number(field.value) + 2));
    field.dispatchEvent(new Event("input", { bubbles: true }));
    owed(() => {
      document.querySelector<HTMLElement>('[data-part="ranking/save"]')?.click();
    }, SAVE_AFTER);
  }, TYPE_AFTER);
}

export function settingsStates(): NamedState[] {
  // The catalogue a field state searches is the seed the served read answers
  // from, because the driver clears the cache before a state is built.
  return [
    [
      "settings",
      "Réglages — les rubriques",
      () => {
        resetSettings();
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-topic",
      "Réglages — une rubrique",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "acquisition";
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-search",
      "Réglages — recherche dans tous les réglages",
      () => {
        resetSettings();
        SETTINGS_STATE.q = "espace";
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-one",
      "Réglages — un réglage, dans son panneau",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "acquisition";
        applyState({ page: "cfg", phase: "ready" });
        const gap = "thresholds:thresholds.min_free_space_staging_gb";
        window.__panel.produce("setting", gap);
      },
    ],
    [
      "settings-edited",
      "Réglages — modifications en attente",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "acquisition";
        SETTINGS_STATE.modifs.set(
          "thresholds:thresholds.min_free_space_staging_gb",
          40,
        );
        SETTINGS_STATE.modifs.set("tracker:tracker.providers.c411.enabled", false);
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    /* C1 — THE BAR IS THE FRAME'S, drawn over the rubric list as over a rubric,
       and over Trackers: one edit waiting, on Réglages' own root. */
    [
      "settings-save-bar-frame",
      "Réglages — la barre d'enregistrement du cadre, une modification en attente",
      () => {
        resetSettings();
        SETTINGS_STATE.modifs.set("thresholds:thresholds.min_free_space_staging_gb", 40);
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    /* C1 — LEAVING WITH EDITS WAITING asks, with three choices. The leave it
       holds is the bar's own tap on Acquisition, so « Enregistrer » and
       « Abandonner les modifications » land where a finger would have. */
    [
      "settings-leave-confirm",
      "Réglages — quitter avec des modifications en attente : enregistrer, abandonner ou rester",
      () => {
        resetSettings();
        SETTINGS_STATE.modifs.set("thresholds:thresholds.min_free_space_staging_gb", 40);
        SETTINGS_STATE.modifs.set("tracker:tracker.providers.c411.enabled", false);
        applyState({ page: "cfg", phase: "ready" });
        askToLeave("cfg", () =>
          document.querySelector<HTMLElement>('[data-part="shell/tab-bar"] [data-page="acq"]')?.click());
      },
    ],
    /* One state per FIELD, because a field is a shape one judges by looking at
       it. The setting each opens is found by TYPE rather than named, so a
       config change that moves a key does not silently open something else. */
    ...[
      ["boolean", "un interrupteur"],
      ["number", "un nombre"],
      ["text", "un texte"],
      ["path", "un chemin"],
      ["list", "une liste"],
      ["duration", "une durée"],
      ["structure", "une structure, qui refuse"],
      ["empty", "une valeur non définie"],
      /* The ninth. Its CONTROL is the text field — the difference is
         in how the value is READ — and that is exactly why it needs a state of
         its own: the six cron settings were rendering « 15 * * * * » where the
         reference said « toutes les heures, à la 15ᵉ minute », and no state
         showed a schedule for anyone to look at. */
      ["schedule", "un horaire, dit en toutes lettres"],
    ].map(([genre, what]): NamedState => [
      `settings-field-${genre}`,
      `Réglages — ${what}`,
      () => {
        resetSettings();
        const topics = window.__mocks?.settings() ?? [];
        const found = topics.flatMap((topic) => topic.settings).find(
          (setting) => setting.type === genre,
        );
        SETTINGS_STATE.topic =
          topics.find((topic) => found !== undefined && topic.settings.includes(found))?.id ?? null;
        applyState({ page: "cfg", phase: "ready" });
        if (found) window.__panel.produce("setting", `${found.file}:${found.key}`);
      },
    ]),
    [
      "settings-secrets",
      "Réglages — secrets et accès",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "secrets";
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-read-only",
      "Réglages — instance en lecture seule",
      () => {
        resetSettings();
        // THE CEILING IS A NAMED LIST SERVED WITH THE ACCOUNT (ruling 23), never a
        // page-local flag: today's read-only instance forbids every write.
        window.__mocks?.setForbiddenWrites(EVERY_WRITE);
        void window.__queries?.resetQueries({ queryKey: ["/api/v1/auth/me"] });
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-restart",
      "Réglages — redémarrage nécessaire",
      () => {
        resetSettings();
        window.__mocks?.setRestartRequired(true);
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "ranking-editor",
      "Réglages — le classement des releases, tel que ranking.json5 le tient",
      () => {
        applyState({ page: "cfg", phase: "ready" });
        window.__screens.ranking();
      },
    ],
    [
      "ranking-editor-loading",
      "Réglages — le classement des releases, pendant la lecture du fichier",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setOperationOutcome("readConfigurationFile", { latencyMilliseconds: HELD_BACK });
        window.__queries?.removeQueries({ queryKey: ["/api/v1/config/files/ranking.json5"] });
        applyState({ page: "cfg", phase: "ready" });
        window.__screens.ranking();
      },
    ],
    [
      "ranking-editor-error",
      "Réglages — le classement des releases, la lecture du fichier en échec",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setOperationOutcome("readConfigurationFile", { status: 500 });
        window.__queries?.removeQueries({ queryKey: ["/api/v1/config/files/ranking.json5"] });
        applyState({ page: "cfg", phase: "ready" });
        window.__screens.ranking();
      },
    ],
    [
      "ranking-editor-saving",
      "Réglages — le classement des releases, un poids enregistré, l'écriture en cours",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setOperationOutcome("updateConfigurationFile", { latencyMilliseconds: HELD_BACK });
        window.__queries?.removeQueries({ queryKey: ["/api/v1/config/files/ranking.json5"] });
        applyState({ page: "cfg", phase: "ready" });
        window.__screens.ranking();
        saveTypedWeight();
      },
    ],
    [
      "ranking-editor-save-conflict",
      "Réglages — le classement des releases, le fichier a changé sous l'édition",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setConfigurationConflict(true);
        window.__queries?.removeQueries({ queryKey: ["/api/v1/config/files/ranking.json5"] });
        applyState({ page: "cfg", phase: "ready" });
        window.__screens.ranking();
        saveTypedWeight();
      },
    ],
  ];
}
