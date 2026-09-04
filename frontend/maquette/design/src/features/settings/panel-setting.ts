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
import { settingsQuery } from "./queries";
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
  // delegation verb that writes them, which is L13's. Read through the same
  // slice the settings page reads them through, so the panel and the page
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
    __settingsVerbs?: { cancelEdit: (identifier: string) => void };
  }
}

window.__settingsVerbs = { cancelEdit };

registerProducer("setting", {
  produce: settingPanel,
  needs: [settingsQuery],
  holds: (identifier, cache) => settingOf(identifier, cache) !== null,
});
