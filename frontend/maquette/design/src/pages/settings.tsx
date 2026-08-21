// design/src/pages/settings.tsx
// The third migrated PAGE, and the largest data surface in the prototype:
// legacy `viewReglages()` / `vueRubrique()` / `vueSecrets()` /
// `chercheReglagesHTML()` / `ligneReglageHTML()` (`refonte.html`) reborn as a
// final component. Markup is TRANSPLANTED, not translated.
//
// ONE NAVIGATES BY WHAT ONE WANTS TO CHANGE, NEVER BY FILE. The engine keeps
// nineteen JSON5 files; knowing which one holds the minimum free disk space
// before an ingest is knowledge of the code, not of the library. Each setting
// says where it comes from — that is what reading a log needs — but that is not
// the map.
//
// `SETTINGS_STATE` STAYS THE SOURCE, and this component never replaces it. The
// document-level delegation writes it (`data-topic`, `data-setting`,
// `data-qsettings`, `data-secret`, `data-save`, `data-restart`) and then
// calls `render()`, whose first act is `store?.toucher()` — so subscribing to
// the store's `version` is what re-reads the mutated object here. Two reasons it
// must stay there and not become React state: the edits are PENDING data the
// legacy save path owns, and R60 reads `SETTINGS_STATE.modifs` directly in five holds.
// Making it React-owned would leave those holds with nothing to read.
//
// The labels come from `settings-labels.ts` — the ONE implementation, shared
// with the panel that edits a setting, so a curated label cannot read one way
// on a row and another way above it. The detector that records a path segment
// nobody named moved there with the naming: it is part of naming a subject,
// not a diagnostic beside it.
import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../components/icon";
import type { Setting, SettingsTopic } from "../data";
import { useReference, useStoreContent } from "../data";
import { settingLabel } from "../settings-labels";

// The pending-edit marker and the row's own identity live on the same element:
// the row IS the control the delegation reads.
function SettingRow({
  setting,
  withFile,
}: {
  setting: Setting;
  withFile?: boolean;
}): ReactElement {
  const { SETTINGS_STATE, settingId, displayedValue, fileName } =
    useReference();
  const identity = settingId(setting);
  const edited = SETTINGS_STATE.modifs.has(identity);
  // `withFile` is false when a group header already names the file: repeating it
  // there prints the file twice on one line and wraps the origin onto two.
  const origin = withFile
    ? `${fileName(setting.f)} · ${setting.c}`
    : setting.c;
  return (
    <button
      className={`settingrow${edited ? " modified" : ""}`}
      data-part="setting/row"
      data-setting={identity}
    >
      <span className="rl">
        {settingLabel(setting)}{" "}
        <span className="rf">{origin}</span>
      </span>
      <span className="rv">{String(displayedValue(setting))}</span>
    </button>
  );
}

function SearchField(): ReactElement {
  const { SETTINGS_STATE, icons } = useReference();
  const { t } = useTranslation();
  return (
    <div className="search" style={{ marginBottom: 12 }}>
      <Icon paths={icons.search} />
      <input
        id="qsettings"
        key={SETTINGS_STATE.q}
        type="search"
        placeholder={t("screens.settings.searchPlaceholder")}
        defaultValue={SETTINGS_STATE.q}
        autoComplete="off"
      />
      {SETTINGS_STATE.q ? (
        <button className="searchclear" data-qsettings="">
          <Icon paths={icons.x} />
        </button>
      ) : null}
    </div>
  );
}

// The save bar lives BESIDE the view rather than inside it, so scrolling the
// settings never scrolls it away — and it exists only when there is something to
// save. Its host is `#device`, a sibling of the page's own container, so this
// page has a second portal: the one piece of it that renders outside its host.
function SaveBar(): ReactElement | null {
  const { SETTINGS_STATE, changedFiles, fileName } = useReference();
  const { t } = useTranslation();
  const pending = SETTINGS_STATE.modifs.size;
  if (pending === 0) return null;
  const device = document.getElementById("device");
  if (!device) return null;
  const files = changedFiles().map(fileName).join(", ");
  return createPortal(
    <div className="savebar" id="savebar">
      <span className="sn">
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
      <button data-save="1" disabled={SETTINGS_STATE.readOnly}>
        {t("screens.settings.save")}
      </button>
    </div>,
    device,
  );
}

function TopicView({ topic }: { topic: SettingsTopic }): ReactElement {
  const byFile = new Map<string, Setting[]>();
  for (const setting of topic.r) {
    if (!byFile.has(setting.f)) byFile.set(setting.f, []);
    byFile.get(setting.f)!.push(setting);
  }
  return (
    <>
      <h2 className="h2">{topic.t}</h2>
      <p className="qhint">{topic.s}</p>
      {[...byFile.entries()].map(([file, settings]) => (
        <Fragment key={file}>
          <h2 className="h2" style={{ marginTop: 16 }}>
            <code>{file}.json5</code>
          </h2>
          <div className="panel">
            {settings.map((setting) => (
              <SettingRow key={setting.c} setting={setting} />
            ))}
          </div>
        </Fragment>
      ))}
    </>
  );
}

export function SettingsPage(): ReactElement | null {
  // `SETTINGS_STATE` is mutated IN PLACE by the delegation, which bumps the store's
  // version through `render()` — subscribing to it is what makes this component
  // re-read the object it never owns.
  useStoreContent((content) => content.version);
  const { t } = useTranslation();
  const {
    SETTINGS,
    SETTINGS_STATE,
    SECRETS,
    emptyInner,
    chipHTML,
    allSettings,
    changedFiles,
  } = useReference();

  if (SETTINGS_STATE.topic === "secrets") {
    return (
      <>
        <h2 className="h2">{t("screens.settings.secretsTitle")}</h2>
        <p className="qhint">{t("screens.settings.secretsHint")}</p>
        <div className="panel">
          {SECRETS.map((secret) => (
            <button
              className="settingrow"
              data-part="setting/row"
              data-secret={secret.k}
              key={secret.k}
            >
              <span className="rl">
                {secret.l}{" "}
                <span className="rf">{secret.k}</span>
              </span>
              <span
                className="rv"
                dangerouslySetInnerHTML={{
                  __html: chipHTML(
                    secret.def
                      ? ["success", t("screens.settings.secretSet")]
                      : ["warning", t("screens.settings.secretUnset")],
                  ),
                }}
              />
            </button>
          ))}
        </div>
        <div className="note">
          <b>{t("screens.settings.secretsNoteLead")}</b>
          {t("screens.settings.secretsNoteRest")}
        </div>
        <SaveBar />
      </>
    );
  }

  if (SETTINGS_STATE.topic) {
    const topic = SETTINGS.find((entry) => entry.id === SETTINGS_STATE.topic);
    if (!topic) {
      return (
        <>
          <div
            className="empty"
            dangerouslySetInnerHTML={{
              __html: emptyInner(t("screens.settings.unknownTopic"), ""),
            }}
          />
          <SaveBar />
        </>
      );
    }
    return (
      <>
        <TopicView topic={topic} />
        <SaveBar />
      </>
    );
  }

  const query = SETTINGS_STATE.q.trim().toLowerCase();
  if (query) {
    const all = allSettings();
    const found = all.filter(
      (setting) =>
        settingLabel(setting).toLowerCase().includes(query) ||
        setting.c.toLowerCase().includes(query),
    );
    return (
      <>
        <SearchField />
        {found.length === 0 ? (
          <div
            className="empty"
            dangerouslySetInnerHTML={{
              __html: emptyInner(
                t("screens.settings.noMatchTitle"),
                t("screens.settings.noMatchBody"),
              ),
            }}
          />
        ) : (
          <>
            <p className="qhint">
              {t(
                found.length > 1
                  ? "screens.settings.countMany"
                  : "screens.settings.countOne",
                { found: found.length, total: all.length },
              )}
            </p>
            <div className="panel">
              {found.slice(0, 40).map((setting) => (
                <SettingRow
                  key={`${setting.f}:${setting.c}`}
                  setting={setting}
                  withFile
                />
              ))}
            </div>
          </>
        )}
        <SaveBar />
      </>
    );
  }

  return (
    <>
      <SearchField />
      {SETTINGS_STATE.readOnly ? (
        <div className="loaderr">
          <b>{t("screens.settings.readOnlyLead")}</b>
          {t("screens.settings.readOnlyRest")}
        </div>
      ) : null}
      {SETTINGS_STATE.redemarrage ? (
        <div className="loaderr">
          <b>{t("screens.settings.restartLead")}</b>{" "}
          {changedFiles().join(", ") ||
            t("screens.settings.restartSomeSettings")}
          {t("screens.settings.restartRest")}{" "}
          <button data-restart="1">
            {t("screens.settings.restartNow")}
          </button>
        </div>
      ) : null}
      {SETTINGS.map((topic) => (
        <button className="topic" data-topic={topic.id} key={topic.id}>
          <span style={{ minWidth: 0, flex: 1 }}>
            <span className="rt">{topic.t}</span>
            <span className="rs">{topic.s}</span>
          </span>
          <span className="rn">{topic.r.length}</span>
        </button>
      ))}
      <button className="topic" data-topic="secrets">
        <span style={{ minWidth: 0, flex: 1 }}>
          <span className="rt">{t("screens.settings.secretsTitle")}</span>
          <span className="rs">
            {t("screens.settings.secretsSubtitle")}
          </span>
        </span>
        <span className="rn">{SECRETS.length}</span>
      </button>
      <button className="topic" data-profile="global">
        <span style={{ minWidth: 0, flex: 1 }}>
          <span className="rt">{t("screens.settings.rankingTitle")}</span>
          <span className="rs">
            {t("screens.settings.rankingSubtitle")}
          </span>
        </span>
        <span className="rn">{t("screens.settings.arrow")}</span>
      </button>
      <div className="note">
        <b>{t("screens.settings.mapNoteLead")}</b>
        {t("screens.settings.mapNoteRest")}
      </div>
      <SaveBar />
    </>
  );
}
