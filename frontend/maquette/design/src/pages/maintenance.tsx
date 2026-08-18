// design/src/pages/maintenance.tsx
// The second migrated PAGE: legacy `viewMaintenance()` (`refonte.html`) reborn
// as a final component. Markup is TRANSPLANTED, not translated.
//
// Two levels and a panel, the shape the settings already use: the rubrics, a
// rubric's commands, then the command itself in the bottom panel. The panel
// stays in the fragment — it is opened by the document-level delegation reading
// `data-maintact`, never by this component, and the row IS that control: a list
// of facts beside a parallel column of buttons asks which of the two to aim at,
// and the answer is never on screen.
//
// The one decision of this page lives in that panel, not here: a command that
// DELETES opens with « à blanc » on, and it cannot be turned off until the panel
// has NAMED what would be destroyed.
//
// Like Système, this page writes nothing. It reads `state.phase` (the skeleton
// and error surfaces) and `state.maintTopic` (which rubric is open, `null` for the
// list) — and the delegation is what writes them.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useReference, useUiState } from "../data";
import type { Fact } from "../data";

export function MaintenancePage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    factRowsHTML,
    skelCardsInner,
    surfErrInner,
    MAINT_TOPICS,
    MAINT_ACTIONS,
    RISQUES,
    JOURNAL,
  } = useReference();

  if (state.phase !== "ready") {
    return state.phase === "erreur" ? (
      <div
        className="surferr"
        dangerouslySetInnerHTML={{
          __html: surfErrInner(t("screens.maintenance.errorSubject")),
        }}
      />
    ) : (
      <div
        className="sec"
        dangerouslySetInnerHTML={{ __html: skelCardsInner(3) }}
      />
    );
  }

  const facts = (rows: Fact[]) => (
    <ol
      className="flux"
      dangerouslySetInnerHTML={{ __html: factRowsHTML(rows) }}
    />
  );

  // One rubric open: its commands, and the way back to all of them.
  const topic = MAINT_TOPICS.find((entry) => entry.id === state.maintTopic);
  if (topic) {
    const actions = MAINT_ACTIONS.filter((action) => action.g === topic.id);
    return (
      <>
        <button className="crossref" data-maintopic="">
          {t("screens.maintenance.allCommands")}
        </button>
        <h2 className="h2">{topic.t}</h2>
        <div className="note">{topic.s}</div>
        {facts(
          actions.map((action) => ({
            l: action.l,
            k: action.id,
            v: RISQUES[action.r].t,
            s:
              action.d +
              (action.long ? t("screens.maintenance.mayBeLong") : ""),
            state: action.r === "destructive" ? "danger" : "",
            // The row IS the control — see the note at the top of this file.
            target: { maintact: action.id },
          })),
        )}
      </>
    );
  }

  const countIn = (id: string) =>
    MAINT_ACTIONS.filter((action) => action.g === id).length;

  return (
    <>
      <div className="note">
        <b>{t("screens.maintenance.introLead")}</b>
        {t("screens.maintenance.introRest")}
      </div>
      {MAINT_TOPICS.map((entry) => {
        const inside = MAINT_ACTIONS.filter((action) => action.g === entry.id);
        const destructive = inside.filter(
          (action) => action.r === "destructive",
        ).length;
        return (
          <button className="topic" data-maintopic={entry.id} key={entry.id}>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span className="rt">{entry.t}</span>
              <span className="rs">{entry.s}</span>
            </span>
            <span className="rn">
              {countIn(entry.id)}
              {destructive
                ? t(
                    destructive > 1
                      ? "screens.maintenance.deletesMany"
                      : "screens.maintenance.deletesOne",
                    { count: destructive },
                  )
                : ""}
              {t("screens.maintenance.arrow")}
            </span>
          </button>
        );
      })}

      <h2 className="h2">{t("screens.maintenance.journal")}</h2>
      <div className="note">
        {t("screens.maintenance.journalNote", { total: JOURNAL.total })}
      </div>
      {facts(JOURNAL.lignes)}
    </>
  );
}
