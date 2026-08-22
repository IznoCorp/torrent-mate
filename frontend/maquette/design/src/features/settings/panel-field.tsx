// The editor for ONE setting, as the bottom panel draws it.
//
// It lives with Configuration because that is what makes it change: what a
// setting is, how its raw value is read, and how an edit is filed. It is drawn
// inside the bottom panel, which is a `ui/` primitive — so rather than the
// panel knowing what a setting is, this file DECLARES the block to the panel's
// contract and REGISTERS what draws it.
//
// HOW A SETTING IS NAMED is not reproduced here: `settings-labels.ts` is the
// one implementation, read by the page that lists the settings and by this
// field alike, so a curated label cannot say one thing on a row and another
// above it.
import { useTranslation } from "react-i18next";
import { useSettingsReference, type Setting } from "./reference";
import { useEngineDrawing } from "../../lib/engine-drawing";
import { Icon } from "../../components/icon";
import { settingLabel, unitOf } from "../../settings-labels";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";

// The kind this file adds to the panel's block map. Declared here, beside what
// draws it, so the two halves of the contract cannot drift apart.
declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    field: { setting: Setting };
  }
}

// `fileName` is pure formatting off a `Setting`'s own fields —
// refonte.html keeps it private (not published on `__referentiel`) but it
// carries no engine state, so it is reproduced verbatim rather than
// re-derived differently. HOW A SETTING IS NAMED is not reproduced at all:
// `settings-labels.ts` is the one implementation, read by the page that lists
// the settings and by this panel alike, so a curated label cannot say one
// thing on a row and another above it.
function fileName(f: string): string {
  return f.includes(".") ? f : `${f}.json5`;
}

function FieldBlock({
  block,
}: {
  block: { type: "field" } & PanelBlockMap["field"];
}) {
  const {
    settingId,
    rawValue,
    typedValue,
    changeSetting,
    openSetting,
  } = useSettingsReference();
  const { icons } = useEngineDrawing();
  const { t } = useTranslation();
  const { setting: setting } = block;
  const id = settingId(setting);
  // The field draws what `rawValue` answers — the pending edit if there
  // is one, the file's `brut` otherwise. Reading `.brut` alone would draw a
  // list one has just shortened at its old length, so a removal would look
  // like it did nothing. Never `.v`: that is a pre-formatted DISPLAY string
  // (a boolean's `.brut: false` reads `.v: "non"`, always truthy, which would
  // wedge the switch on).
  const v = rawValue(setting);

  if (setting.type === "structure")
    return (
      <div className="field readonly" data-part="field" data-read-only="">
        <p className="rulenote">
          {t("settings.field.structureBefore")}{" "}
          <b>{t("settings.field.structureWord")}</b>{" "}
          {t("settings.field.structureAfter")}{" "}
          <code>{fileName(setting.f)}</code>.
        </p>
      </div>
    );

  if (setting.type === "boolean")
    return (
      <div className="field" data-part="field">
        <button
          className={`fieldtoggle${v ? " active" : ""}`}
          data-part="field/toggle"
          role="switch"
          aria-label={settingLabel(setting)}
          aria-checked={v ? "true" : "false"}
          data-field={id}
          data-to={v ? "non" : "oui"}
        >
          <span className="fieldknob" />
        </button>
        <span className="fieldlabel">
          {v ? t("settings.field.enabled") : t("settings.field.disabled")}
        </span>
      </div>
    );

  if (setting.type === "list") {
    const items = Array.isArray(v) ? (v as unknown[]) : [];
    return (
      <div className="field list" data-part="field">
        {items.length ? (
          items.map((x, index) => (
            <div className="litem" data-part="field/list-item" key={index}>
              <span>{String(x)}</span>
              <button
                className="lremove"
                data-part="field/list-remove"
                data-deletefield={id}
                data-index={index}
                aria-label={t("settings.field.removeAria", {
                  // french-ok: the INTERPOLATION placeholder, named by
                  // `removeAria` in fr.json — renaming this half alone
                  // leaves « Retirer {{valeur}} » on screen.
                  valeur: String(x),
                })}
              >
                <Icon paths={icons.x} />
              </button>
            </div>
          ))
        ) : (
          <p className="rulenote">{t("settings.field.emptyList")}</p>
        )}
        <button className="ladd" data-part="field/list-add" data-addfield={id}>
          <Icon paths={icons.plus} />
          {t("settings.field.add")}
        </button>
      </div>
    );
  }

  const empty = v === null || v === undefined || v === "";
  const mono = setting.type === "path";
  const numeric = setting.type === "number";
  const unit = unitOf(setting);

  return (
    <div className="field" data-part="field">
      <input
        // KEYED BY THE SETTING, and this is a correctness fix, not a hint.
        // `#sheetin` is a persistent node now, where the legacy layer replaced
        // its innerHTML on every open — a fresh field each time, implicitly.
        // Here the blocks are the same kinds in the same order from one panel
        // to the next, so React would REUSE this very `<input>`: once the
        // operator has typed, the DOM node carries a permanent dirty-value
        // flag, React only updates the `value` ATTRIBUTE, and the next
        // setting's panel opens showing the previous setting's text — which
        // the next blur then files under the NEW setting's id. Keying by the
        // setting makes a different setting a different node.
        key={id}
        className={`fieldinput${mono ? " mono" : ""}`}
        data-part="field/input"
        data-mono={mono || undefined}
        data-field={id}
        type={numeric ? "number" : "text"}
        inputMode={numeric ? "decimal" : undefined}
        defaultValue={empty ? "" : String(v)}
        placeholder={empty ? t("settings.field.undefinedPlaceholder") : ""}
        aria-label={settingLabel(setting)}
        // The ONE place mountSearch's `.fieldinput` `onchange` binding
        // (refonte.html) is replaced by a component-owned handler — and it is
        // the SAME event, bound natively rather than through React's synthetic
        // `onChange`. Three reasons, all measured rather than stylistic:
        //   · the DOM `change` event commits on blur, once; React's `onChange`
        //     fires on every keystroke, which would file a pending edit per
        //     character typed;
        //   · a `change` event dispatched at the element (what a probe does to
        //     exercise this field) reaches a native listener, while React's
        //     synthetic `onChange` is gated by its own value tracker and
        //     silently does nothing for a value already seen;
        //   · the input stays uncontrolled (`defaultValue`), so a re-render
        //     never fights the caret mid-edit.
        // The listener is re-attached on each render, which is what keeps this
        // closure reading the CURRENT setting rather than the one this field
        // was first drawn for.
        ref={(element) => {
          if (!element) return;
          const commit = () => {
            changeSetting(id, typedValue(setting, element.value));
            openSetting(id);
          };
          element.addEventListener("change", commit);
          return () => element.removeEventListener("change", commit);
        }}
      />
      {unit ? (
        <span className="fieldunit">{unit}</span>
      ) : setting.type === "duration" ? (
        <span className="fieldunit">{t("settings.field.durationFormat")}</span>
      ) : null}
    </div>
  );
}

// Declared to the registry as this module evaluates. The shell imports this
// file at boot, before any panel can open.
registerBlock("field", (block) => <FieldBlock block={block} />);
