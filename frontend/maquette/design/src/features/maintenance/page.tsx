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
import { useMaintenanceReference } from "../../features/maintenance/reference";
import { type Fact } from "../../lib/engine-drawing";
import { useUiState } from "../../lib/store-access";

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
  } = useMaintenanceReference();

  if (state.phase !== "ready") {
    return state.phase === "error" ? (
      <div
        className="surferr" data-part="surface-error" role="alert"
        dangerouslySetInnerHTML={{
          __html: surfErrInner(t("screens.maintenance.errorSubject")),
        }}
      />
    ) : (
      <div
        className="sec" data-part="section"
        dangerouslySetInnerHTML={{ __html: skelCardsInner(3) }}
      />
    );
  }

  const facts = (rows: Fact[]) => (
    <ol
      className="flux" data-part="flux"
      dangerouslySetInnerHTML={{ __html: factRowsHTML(rows) }}
    />
  );

  // One rubric open: its commands, and the way back to all of them.
  const topic = MAINT_TOPICS.find((entry) => entry.id === state.maintTopic);
  if (topic) {
    const actions = MAINT_ACTIONS.filter((action) => action.g === topic.id);
    return (
      <>
        <button className="crossref" data-part="cross-reference" data-maintopic="">
          {t("screens.maintenance.allCommands")}
        </button>
        <h2 className="h2" data-part="heading">{topic.t}</h2>
        <div className="note" data-part="note">{topic.s}</div>
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
      <div className="note" data-part="note">
        <b>{t("screens.maintenance.introLead")}</b>
        {t("screens.maintenance.introRest")}
      </div>
      {MAINT_TOPICS.map((entry) => {
        const inside = MAINT_ACTIONS.filter((action) => action.g === entry.id);
        const destructive = inside.filter(
          (action) => action.r === "destructive",
        ).length;
        return (
          <button className="topic" data-part="topic" data-maintopic={entry.id} key={entry.id}>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span className="rt" data-part="topic/title">{entry.t}</span>
              <span className="rs" data-part="topic/subtitle">{entry.s}</span>
            </span>
            <span className="rn" data-part="topic/count">
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

      <h2 className="h2" data-part="heading">{t("screens.maintenance.journal")}</h2>
      <div className="note" data-part="note">
        {t("screens.maintenance.journalNote", { total: JOURNAL.total })}
      </div>
      {facts(JOURNAL.lignes)}
    </>
  );
}
