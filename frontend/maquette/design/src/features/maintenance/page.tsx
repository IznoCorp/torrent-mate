// design/src/pages/maintenance.tsx
// The second migrated PAGE: legacy `viewMaintenance()` (`refonte.html@60530dbd8`) reborn
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
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import type { ReactElement } from "react";
import { useUiState } from "../../lib/store-access";
import { useDeletionJournal, useMaintenanceActions } from "./queries";
import { backAction, factList, section, sectionHeading, topicRow } from "../../ui/variants";
import { guidance } from "../../ui/variants/layout";
import { Markup } from "../../ui/markup";
import { FactRows, type FactRow } from "../../ui/fact-rows";

// The six RUBRICS, in the order they are listed. One navigates by what one wants
// to DO — never a flat list of commands whose order means nothing — and a
// rubric's command group is its id. Each rubric's name and the sentence under
// it are the interface's words (`screens.maintenance.topics`).
const MAINTENANCE_TOPICS = ["query", "scan", "repair", "clean", "fix", "analyze"];
// The risk vocabulary is the FEATURE's, since its panel lives here: the
// page and the panel read one derivation of « what does this command risk »
// rather than a copy each (§13).
import { riskLabel } from "./risks";
import { bridge } from "../../lib/shell-doors";

export function MaintenancePage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  // FROM THE CACHE (invariant 4).
  const { data: MAINT_ACTIONS = [] } = useMaintenanceActions();
  const { data: JOURNAL = { total: 0, rows: [] } } = useDeletionJournal();

  if (state.phase !== "ready") {
    return state.phase === "error" ? (
      <SurfaceError subject={t("screens.maintenance.errorSubject")} />
    ) : (
      <div className={section()} data-part="section"><Skeletons count={3} shape="card" /></div>
    );
  }

  const facts = (rows: FactRow[]) => (
    <ol className={factList()} data-part="flux">
      <FactRows rows={rows} />
    </ol>
  );

  // One rubric open: its commands, and the way back to all of them.
  const topic = MAINTENANCE_TOPICS.find((entry) => entry === state.maintTopic);
  if (topic) {
    const actions = MAINT_ACTIONS.filter((action) => action.group === topic);
    return (
      <>
        {/* A RUBRIC IS A SCREEN ONE ENTERS, so it wears the way out every
            screen of this interface wears (B-361). The row that said « toutes
            les commandes » took its place: it navigated by writing the rubric
            away, leaving the entry the reader was standing on untouched, so
            the system Back gesture went on popping the page. This POPS. */}
        <button
          className={backAction()}
          data-part="screen/back"
          onClick={() => bridge.back()}
        >
          {t("screens.maintenance.allCommands")}
        </button>
        <h2 className={sectionHeading()} data-part="heading">{t(`screens.maintenance.topics.${topic}.title`)}</h2>
        <div className={guidance()} data-part="guidance">{t(`screens.maintenance.topics.${topic}.explanation`)}</div>
        {facts(
          actions.map((action) => ({
            label: action.label,
            k: action.id,
            value: riskLabel(action.risk),
            secondaryLine:
              action.description +
              (action.long ? t("screens.maintenance.mayBeLong") : ""),
            state: action.risk === "destructive" ? "danger" : "",
            // The row IS the control — see the note at the top of this file.
            target: { maintact: action.id },
          })),
        )}
      </>
    );
  }

  const countIn = (id: string) =>
    MAINT_ACTIONS.filter((action) => action.group === id).length;

  return (
    <>
      <div className="note" data-part="note">
        <b>{t("screens.maintenance.introLead")}</b>
        {t("screens.maintenance.introRest")}
      </div>
      {MAINTENANCE_TOPICS.map((entry) => {
        const inside = MAINT_ACTIONS.filter((action) => action.group === entry);
        const destructive = inside.filter(
          (action) => action.risk === "destructive",
        ).length;
        return (
          <button className={topicRow()} data-part="topic" data-maintopic={entry} key={entry}>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span className="rt" data-part="topic/title">{t(`screens.maintenance.topics.${entry}.title`)}</span>
              <span className="rs" data-part="topic/subtitle">{t(`screens.maintenance.topics.${entry}.explanation`)}</span>
            </span>
            <span className="rn" data-part="topic/count">
              {countIn(entry)}
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

      <h2 className={sectionHeading()} data-part="heading">{t("screens.maintenance.journal")}</h2>
      <div className="note" data-part="note">
        {t("screens.maintenance.journalNote", { total: JOURNAL.total })}
      </div>
      {facts(JOURNAL.rows)}
    </>
  );
}
