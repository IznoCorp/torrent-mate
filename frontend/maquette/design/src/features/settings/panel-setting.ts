// One setting's panel — what a row of a Configuration rubric raises.
//
// It lives with Configuration because that is what makes it change: the
// setting's own schema, the edit pending on it, and whether this instance may
// write at all. The FIELD it draws is already this feature's — `panel-field.tsx`
// registers the `field` block — and what this producer does is build the
// descriptor that names it.
//
// A PRODUCER IS NOT A HOOK: it is called from the click delegation and from the
// addressed-panel table on a cold load at `?panel=setting:<file>:<key>`, so it
// reads the query cache synchronously (invariant 10).
import i18next from "i18next";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { flattenSettings, settingIdentifier, valueShown } from "./catalog";
import { HELD } from "../../lib/query-client";
import { settingsQuery, writeConfigurationFile } from "./queries";
import type { Setting, SettingsTopic } from "./reference";

// THE ICONS COME THROUGH THE ENGINE'S DRAWING SLICE, not by importing
// `app/icons.ts`, and it is invariant 8 that decides. `app/icons.ts` is outside
// `ui/` and `lib/`, so the fan-in ceiling applies to it — four features — and a
// producer per feature importing it directly walked it to five in one phase,
// which is « no god module » arriving exactly where the guard was aimed. Every
// other drawing helper in this tree comes through the same door
// (`lib/engine-drawing.ts`), it is the SAME object either way, and it dies with
// the engine — at which point `app/icons.ts` is the durable home and this line
// is the one that changes.
const icons = () => window.__referentiel.icons;

/**
 * Finds one setting among those the layer answered.
 *
 * Args:
 *     identifier: `<file>:<key>`, as the address and the row both spell it.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The setting, or null when the layer has not answered or does not carry it.
 */
function settingOf(identifier: string, cache: PanelCache): Setting | null {
  const topics = cache.held<SettingsTopic[]>(settingsQuery.queryKey);
  if (topics === undefined) return null;
  return flattenSettings(topics).find(
    (setting) => settingIdentifier(setting) === identifier) ?? null;
}

/**
 * Builds one setting's descriptor.
 *
 * Args:
 *     identifier: `<file>:<key>`.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null for a setting the layer does not carry — which is
 *     what the engine's producer did by returning early on `!setting`.
 */
function settingPanel(identifier: string, cache: PanelCache): PanelDescriptor | null {
  const setting = settingOf(identifier, cache);
  if (setting === null) return null;
  const translate = i18next.t.bind(i18next);
  // THE PENDING EDITS AND THE INSTANCE'S RIGHTS are the engine's mutable state
  // — not server state, and not this feature's yet: they move with the last
  // delegation verb that writes them, and that is the engine's last lot. Read
  // through the same slice the settings page reads, so the panel and the page
  // cannot disagree about what has been edited.
  const { modifs: pending, readOnly } = window.__referentiel.SETTINGS_STATE;
  const shown = valueShown(setting, pending);
  const changed = pending.has(identifier);
  return {
    address: "setting:" + identifier,
    title: window.__settingLabels.label(setting),
    meta: [{ m: `${setting.f}.json5 · ${setting.c}` }],
    ...(changed ? { puce: ["info", translate("panels.setting.edited")] } : {}),
    blocs: [
      setting.note ? { type: "note", text: setting.note } : null,
      readOnly ? null : { type: "field", setting },
      {
        type: "faits",
        lignes: [
          { c: translate("panels.setting.currentValue"), v: String(shown) },
          ...(changed
            ? [{
                c: translate("panels.setting.writtenValue"),
                v: String(setting.v),
                terne: true,
              }]
            : []),
          // The file is on the mono line above; a « Fichier » fact under it
          // says the same thing twice on a screen that has no room for it.
        ],
      },
      {
        type: "actions",
        actions: [
          readOnly
            ? {
                text: translate("panels.setting.readOnly"),
                icone: icons().x,
                desactive: true,
              }
            : null,
          changed
            ? {
                text: translate("panels.setting.cancelEdit"),
                icone: icons().x,
                target: { cancelsetting: identifier },
              }
            : null,
        ],
      },
      { type: "note", text: translate("panels.setting.nothingWritten") },
    ],
  };
}

/* « ANNULER LA MODIFICATION » — the verb this panel offers, living beside the
   panel that offers it. It was `legacy.js`'s `data-cancelsetting` branch, and
   it moves here because a producer owns the verbs its own surface carries
   (`frame-model.md` Part 12). Its rule was written FIRST, against the engine's
   branch, and seen red under a mutation of it — `harness/settings.py`'s
   « cancelling drops that edit », « and leaves every other edit standing »,
   « and the panel is gone ».

   THE MAP IT WRITES IS STILL THE ENGINE'S. `SETTINGS_STATE` is not server state
   and does not move in this lot; what moved is the DECISION about it, which is
   this feature's. So is the redraw and the sentence that follows — both through
   seams that die with the engine.

   THE WAIT IS THE PANEL'S EXIT, unchanged at 200 ms: the panel closes, then the
   page is redrawn and the message said. Shortening or removing it is a
   behaviour change and this is a conversion. */
const CANCEL_SETTLE_MILLISECONDS = 200;

function cancelEdit(identifier: string): void {
  window.__referentiel.SETTINGS_STATE.modifs.delete(identifier);
  window.__panel.close();
  window.setTimeout(() => {
    window.__referentiel.render();
    window.__toast?.show({
      message: i18next.t("panels.setting.cancelledToast"),
    });
  }, CANCEL_SETTLE_MILLISECONDS);
}

declare global {
  interface Window {
    /** The verbs the settings panels offer, called by the click delegation. */
    __settingsVerbs?: {
      cancelEdit: (identifier: string) => void;
      /** Writes every changed file and reads what came back (B-299). */
      save: () => Promise<void>;
      /** Throws the stale edits away and asks for the settings again. */
      reload: () => void;
      /** Asks before cutting the service for the household (B-300, §17). */
      askToRestart: () => void;
      /** Restarts, once the operator has said so. */
      restart: () => void;
    };
  }
}

/* SAVING — the settings' other verb, and the one that made B-299 readable.
   `data-save` closed over nothing but local state: it cleared the pending
   edits, raised the restart flag and said « Enregistré », without ever asking
   the layer. So `conflict` — a field the contract has always answered — had no
   reader, and the copy naming « three banners » drew two.

   IT WRITES EACH CHANGED FILE and reads what comes back. A conflict does not
   clear the edits: the file moved under the editor, so what is on screen no
   longer describes what is stored, and throwing the operator's work away on top
   of that would be the second loss. */
async function saveEdits(): Promise<void> {
  const reference = window.__referentiel;
  const files = reference.changedFiles();
  const pending = reference.SETTINGS_STATE.modifs;
  let conflicted = false;
  for (const file of files) {
    const values: Record<string, unknown> = {};
    for (const [identifier, value] of pending)
      if (identifier.startsWith(file + ":")) values[identifier] = value;
    const answered = await writeConfigurationFile(file, values);
    // A WRITE THE OUTBOX HELD, or one that answered nothing, says nothing about
    // the file — so it says nothing here either. Neither is a conflict, and
    // neither is a promise that there is none.
    if (answered !== HELD && answered !== undefined && answered.conflict)
      conflicted = true;
  }
  reference.SETTINGS_STATE.conflict = conflicted;
  if (conflicted) {
    reference.render();
    return;
  }
  pending.clear();
  reference.SETTINGS_STATE.redemarrage = true;
  reference.render();
  window.__toast?.show({
    message: i18next.t("panels.setting.savedToast", {
      files: files.map(reference.fileName).join(", "),
    }),
  });
}

/* RELOADING after a conflict — the only honest verb. The editor's copy is
   stale and there is nothing local worth keeping, so the pending edits go with
   the banner and the settings are asked for again. */
function reloadSettings(): void {
  const reference = window.__referentiel;
  reference.SETTINGS_STATE.modifs.clear();
  reference.SETTINGS_STATE.conflict = false;
  window.__queries?.invalidateQueries({ queryKey: settingsQuery.queryKey });
  reference.render();
}

/* RESTARTING IS ASKED BEFORE IT IS DONE (B-300, §17).

   « Redémarrer maintenant » used to restart on the tap: the flag dropped and a
   toast said « Service redémarré ». A restart cuts the service for EVERY
   account of the household — §17 — which is the case NE-DOIT-PAS-6's spirit
   covers even though nothing is destroyed, and it is the one thing the sentence
   below has to say rather than merely asking « êtes-vous sûr ? ».

   THE CONFIRMATION IS `ui/dialog`, whose paragraph colour and danger contrast
   R116 holds — so this adds no drawing primitive, only a use of
   one. Cancelling leaves the restart OWED and says nothing about one having
   happened: a confirmation that restarts anyway is a delay. */
function askToRestart(): void {
  const translate = i18next.t.bind(i18next);
  window.__dialog?.open({
    heading: translate("screens.settings.restartConfirmHeading"),
    body: [
      {
        type: "paragraph",
        runs: [{ text: translate("screens.settings.restartConfirmBody") }],
      },
    ],
    actions: [
      {
        text: translate("screens.settings.restartConfirmGo"),
        tone: "danger",
        target: { "data-confirmrestart": "1" },
      },
      {
        text: translate("screens.settings.restartConfirmCancel"),
        tone: "ghost",
        dismiss: true,
      },
    ],
  });
}

/** Restarts, and only once the operator has said so. */
function restart(): void {
  const reference = window.__referentiel;
  window.__dialog?.close();
  reference.SETTINGS_STATE.redemarrage = false;
  reference.render();
  window.__toast?.show({
    message: i18next.t("screens.settings.restartDone"),
  });
}

window.__settingsVerbs = {
  cancelEdit,
  save: saveEdits,
  reload: reloadSettings,
  askToRestart,
  restart,
};

registerProducer("setting", {
  produce: settingPanel,
  needs: [settingsQuery],
  holds: (identifier, cache) => settingOf(identifier, cache) !== null,
});
