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
// `REG_ETAT` STAYS THE SOURCE, and this component never replaces it. The
// document-level delegation writes it (`data-rubrique`, `data-reglage`,
// `data-qreg`, `data-secret`, `data-enregistrer`, `data-redemarrer`) and then
// calls `render()`, whose first act is `magasin?.toucher()` — so subscribing to
// the store's `version` is what re-reads the mutated object here. Two reasons it
// must stay there and not become React state: the edits are PENDING data the
// legacy save path owns, and R60 reads `REG_ETAT.modifs` directly in five holds.
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
  const { REG_ETAT, reglageId, valeurCourante, nomDeFichier } =
    useReference();
  const identity = reglageId(setting);
  const edited = REG_ETAT.modifs.has(identity);
  // `withFile` is false when a group header already names the file: repeating it
  // there prints the file twice on one line and wraps the origin onto two.
  const origin = withFile
    ? `${nomDeFichier(setting.f)} · ${setting.c}`
    : setting.c;
  return (
    <button
      className={`settingrow${edited ? " modified" : ""}`}
      data-reglage={identity}
    >
      <span className="rl">
        {settingLabel(setting)}{" "}
        <span className="rf">{origin}</span>
      </span>
      <span className="rv">{String(valeurCourante(setting))}</span>
    </button>
  );
}

function SearchField(): ReactElement {
  const { REG_ETAT, icons } = useReference();
  const { t } = useTranslation();
  return (
    <div className="search" style={{ marginBottom: 12 }}>
      <Icon paths={icons.search} />
      <input
        id="qreg"
        key={REG_ETAT.q}
        type="search"
        placeholder={t("screens.settings.searchPlaceholder")}
        defaultValue={REG_ETAT.q}
        autoComplete="off"
      />
      {REG_ETAT.q ? (
        <button className="searchclear" data-qreg="">
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
  const { REG_ETAT, fichiersModifies, nomDeFichier } = useReference();
  const { t } = useTranslation();
  const pending = REG_ETAT.modifs.size;
  if (pending === 0) return null;
  const device = document.getElementById("device");
  if (!device) return null;
  const files = fichiersModifies().map(nomDeFichier).join(", ");
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
      <button data-enregistrer="1" disabled={REG_ETAT.lectureSeule}>
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
  // `REG_ETAT` is mutated IN PLACE by the delegation, which bumps the store's
  // version through `render()` — subscribing to it is what makes this component
  // re-read the object it never owns.
  useStoreContent((content) => content.version);
  const { t } = useTranslation();
  const {
    REGLAGES,
    REG_ETAT,
    SECRETS,
    emptyInner,
    chipHTML,
    tousLesReglages,
    fichiersModifies,
  } = useReference();

  if (REG_ETAT.rubrique === "secrets") {
    return (
      <>
        <h2 className="h2">{t("screens.settings.secretsTitle")}</h2>
        <p className="qhint">{t("screens.settings.secretsHint")}</p>
        <div className="panel">
          {SECRETS.map((secret) => (
            <button
              className="settingrow"
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

  if (REG_ETAT.rubrique) {
    const topic = REGLAGES.find((entry) => entry.id === REG_ETAT.rubrique);
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

  const query = REG_ETAT.q.trim().toLowerCase();
  if (query) {
    const all = tousLesReglages();
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
      {REG_ETAT.lectureSeule ? (
        <div className="loaderr">
          <b>{t("screens.settings.readOnlyLead")}</b>
          {t("screens.settings.readOnlyRest")}
        </div>
      ) : null}
      {REG_ETAT.redemarrage ? (
        <div className="loaderr">
          <b>{t("screens.settings.restartLead")}</b>{" "}
          {fichiersModifies().join(", ") ||
            t("screens.settings.restartSomeSettings")}
          {t("screens.settings.restartRest")}{" "}
          <button data-redemarrer="1">
            {t("screens.settings.restartNow")}
          </button>
        </div>
      ) : null}
      {REGLAGES.map((topic) => (
        <button className="topic" data-rubrique={topic.id} key={topic.id}>
          <span style={{ minWidth: 0, flex: 1 }}>
            <span className="rt">{topic.t}</span>
            <span className="rs">{topic.s}</span>
          </span>
          <span className="rn">{topic.r.length}</span>
        </button>
      ))}
      <button className="topic" data-rubrique="secrets">
        <span style={{ minWidth: 0, flex: 1 }}>
          <span className="rt">{t("screens.settings.secretsTitle")}</span>
          <span className="rs">
            {t("screens.settings.secretsSubtitle")}
          </span>
        </span>
        <span className="rn">{SECRETS.length}</span>
      </button>
      <button className="topic" data-profil="global">
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
