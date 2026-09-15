// The settings feature's tap verbs — what its rows, its fields, its search and
// its banners emit.
//
// ONE REGISTRY ANSWERS THEM (`lib/verbs.ts`), and this module is named once in
// `app/panel-contributions.ts`, the boot's list of feature side effects. The
// panels they raise and the acts they forward to stay where they are drawn —
// `panel-setting.ts`, `panel-secret.ts`, `panel-field.tsx` — so this file grows
// no producer and imports no other feature.
import i18next from "i18next";
import { panel } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { registerVerb } from "../../lib/verbs";
import { settingIdentifier } from "./catalog";
import { settingsVerbs } from "./panel-setting";
import { changeSetting, rawValue } from "./pending-edits";
import { heldSettings } from "./queries";
import type { Setting } from "./types";
import { SETTINGS_STATE } from "./state";

/**
 * Finds one setting among those the layer answered.
 *
 * Args:
 *     identifier: `<file>:<key>`.
 *
 * Returns:
 *     The setting, or undefined when the layer does not carry it.
 */
function heldSetting(identifier: string): Setting | undefined {
  return heldSettings().find((one) => settingIdentifier(one) === identifier);
}

/**
 * Files a list setting changed by one item, and re-produces its panel.
 *
 * Args:
 *     identifier: The list setting's `<file>:<key>`.
 *     change: What happens to the list's items, in place.
 */
function fileList(identifier: string, change: (items: unknown[]) => void): void {
  const setting = heldSetting(identifier);
  if (setting === undefined) return;
  const drawn = rawValue(setting);
  const items = Array.isArray(drawn) ? [...(drawn as unknown[])] : [];
  change(items);
  changeSetting(identifier, items);
  panel.produce("setting", identifier);
}

registerVerb("setting", (identifier) => panel.produce("setting", identifier));

// A secret is never shown, so its panel offers the only act that exists:
// replacing it. The producer takes the KEY and reads the layer's answer itself.
registerVerb("secret", (key) => panel.produce("secret", key));

// A switch carries the value it would file (`data-to`) beside the setting it
// edits (`data-field`); the field alone is an input, and answers nothing here.
registerVerb("to", (target, element) => {
  const identifier = element.dataset.field ?? "";
  if (heldSetting(identifier) === undefined) return;
  changeSetting(identifier, target === "oui");
  panel.produce("setting", identifier);
});

registerVerb("deletefield", (identifier, element) =>
  fileList(identifier, (items) => {
    items.splice(Number(element.dataset.index), 1);
  }));

// A prototype cannot show a keyboard; the added item is named after its place
// in the list, so the shape of the row is judgeable.
registerVerb("addfield", (identifier) =>
  fileList(identifier, (items) => {
    items.push(i18next.t("settings.field.addedItem", { position: items.length + 1 }));
  }));

registerVerb("cancelsetting", (identifier) => settingsVerbs.cancelEdit(identifier));

// The save ASKS THE LAYER (B-299): a conflict is the layer's answer, never a
// banner raised on the strength of the tap.
registerVerb("save", () => {
  void settingsVerbs.save();
});

registerVerb("reloadsettings", () => settingsVerbs.reload());

// A restart cuts the service for every account of the household (B-300, §17),
// so the tap ASKS, and only the confirmation restarts.
registerVerb("restart", () => settingsVerbs.askToRestart());

registerVerb("confirmrestart", () => {
  void settingsVerbs.restart();
});

// The search filters the rows in place; the store's version bump is what
// redraws them.
registerVerb("qsettings", (query) => {
  SETTINGS_STATE.q = query;
  store.touch();
});
