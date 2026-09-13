// The named states of the configuration page, « Réglages ».
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label is what the ≡ panel shows, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { resetSettings } from "../../engine/legacy.js";

export function settingsStates(): NamedState[] {
  // The pending state, read through the reference the engine publishes. The
  // catalogue a field state searches is the seed the served read answers from,
  // because the driver clears the cache before a state is built.
  const { SETTINGS_STATE } = window.__referentiel;
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
        SETTINGS_STATE.readOnly = true;
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
  ];
}
