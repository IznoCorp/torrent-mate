// The two pieces Configuration draws BESIDE its own flow: the banners, and the
// save bar.
//
// THEY ARE ON EVERY BRANCH OF THE PAGE. All three banners were written inline
// in the RUBRIC LIST alone, so a read-only instance said so on the list and
// said nothing once a rubric was open — while the save bar, which raises the
// third of them, exists everywhere. B-299's banner would have been invisible
// exactly where « Enregistrer » is tapped.
//
// A FILE OF THEIR OWN since the settings micro-wave, and the reason is a
// ceiling rather than taste: `page.tsx` stands against a 400-line hard block a
// wave may only move DOWNWARD, and what this wave added to that page — a way
// out of a rubric, on two branches — is the page's own subject. These two are
// not: one is a portal into the frame's own host, the other is a strip drawn
// over whatever branch is showing.
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useSettingsReference } from "./reference";
import { useConfigurationStatus } from "./queries";
import { loadError, loadErrorAction } from "../../ui/variants";
import { saveAction, saveBar } from "./variants";

// The save bar lives BESIDE the view rather than inside it, so scrolling the
// settings never scrolls it away — and it exists only when there is something to
// save. Its host is `#device`, a sibling of the page's own container, so this
// page has a second portal: the one piece of it that renders outside its host.
// THE THREE BANNERS THE COPY NAMES, in one place and drawn on every branch of
// this page.
//
// They were written inline in the RUBRIC LIST alone, so a read-only instance
// said so on the list and said nothing once a rubric was open — and the save
// bar, which is what raises the third of them, exists on every branch. B-299's
// banner would have been invisible exactly where the operator taps « Enregistrer ».
export function SettingsBanners(): ReactElement {
  const { SETTINGS_STATE, changedFiles } = useSettingsReference();
  const { t } = useTranslation();
  // THE RESTART IS THE LAYER'S FACT, and the banner is a reader of it (B-343).
  // It used to be raised on `SETTINGS_STATE` — an engine object nothing
  // re-renders — so it appeared at the next render something else caused, or
  // never: the operator saved, was told « Enregistré », and saw no banner. A
  // query re-renders every reader the moment its answer moves, which is what
  // makes B-300's confirmation reachable by the path a hand walks.
  const { data: status } = useConfigurationStatus();
  const restartOwed = Boolean(status?.restartRequired);
  return (
    <>
      {SETTINGS_STATE.readOnly ? (
        <div className={loadError()} data-part="load-error">
          <b>{t("screens.settings.readOnlyLead")}</b>
          {t("screens.settings.readOnlyRest")}
        </div>
      ) : null}
      {/* THE THIRD BANNER — the one the copy named and the page never drew
          (B-299). The file moved on disk while it was being edited, so what is
          on screen no longer describes what is stored. The edits are NOT thrown
          away by the banner appearing: losing the operator's work on top of the
          surprise would be the second loss, and reloading is offered as a
          decision rather than taken as one. */}
      {SETTINGS_STATE.conflict ? (
        <div className={loadError()} data-part="load-error">
          <b>{t("screens.settings.conflictLead")}</b>
          {t("screens.settings.conflictRest")}{" "}
          <button className={loadErrorAction()} data-reloadsettings="1">
            {t("screens.settings.conflictReload")}
          </button>
        </div>
      ) : null}
      {restartOwed ? (
        <div className={loadError()} data-part="load-error">
          <b>{t("screens.settings.restartLead")}</b>{" "}
          {changedFiles().join(", ") ||
            t("screens.settings.restartSomeSettings")}
          {t("screens.settings.restartRest")}{" "}
          <button className={loadErrorAction()} data-restart="1">
            {t("screens.settings.restartNow")}
          </button>
        </div>
      ) : null}
    </>
  );
}

export function SaveBar(): ReactElement | null {
  const {
    SETTINGS_STATE,
    changedFiles,
    fileName,
  } = useSettingsReference();
  const { t } = useTranslation();
  const pending = SETTINGS_STATE.modifs.size;
  if (pending === 0) return null;
  const device = document.getElementById("device");
  if (!device) return null;
  const files = changedFiles().map(fileName).join(", ");
  return createPortal(
    <div
      className={saveBar()}
      id="savebar"
      role="region"
      aria-label={t("screens.settings.saveBarLabel")}
    >
      <span className="sn" data-part="save-bar/pending">
        <b>
          {t(
            pending > 1
              ? "screens.settings.pendingMany"
              : "screens.settings.pendingOne",
            { count: pending },
          )}
        </b>{" "}
        {t("screens.settings.willWrite", { files })}
      </span>
      <button className={saveAction()} data-save="1" disabled={SETTINGS_STATE.readOnly}>
        {t("screens.settings.save")}
      </button>
    </div>,
    device,
  );
}
