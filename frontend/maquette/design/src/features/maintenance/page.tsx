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
import { SurfaceError } from "../../ui/state-surfaces";
import type { ReactElement } from "react";
import { useMaintenanceReference } from "../../features/maintenance/reference";
import { type Fact } from "../../lib/engine-drawing";
import { useUiState } from "../../lib/store-access";
import { useDeletionJournal, useMaintenanceActions } from "./queries";
import { crossReference, section, sectionHeading, topicRow } from "../../ui/variants";
import { guidance } from "../../ui/variants/layout";
import { Markup } from "../../ui/markup";
// The risk vocabulary is the FEATURE's, since its panel lives here: the
// page and the panel read one derivation of « what does this command risk »
// rather than a copy each (§13).
import { riskLabel } from "./risks";

export function MaintenancePage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    factRowsHTML,
    skelCardsInner,
    MAINT_TOPICS,
  } = useMaintenanceReference();
  // FROM THE CACHE (invariant 4).
  const { data: MAINT_ACTIONS = [] } = useMaintenanceActions();
  const { data: JOURNAL = { total: 0, lignes: [] } } = useDeletionJournal();

  if (state.phase !== "ready") {
    return state.phase === "error" ? (
      <SurfaceError subject={t("screens.maintenance.errorSubject")} />
    ) : (
      <Markup
        className={section()} data-part="section"
        html={skelCardsInner(3)}
      />
    );
  }

  const facts = (rows: Fact[]) => (
    <Markup tag="ol"
      className="flux" data-part="flux"
      html={factRowsHTML(rows)}
    />
  );

  // One rubric open: its commands, and the way back to all of them.
  const topic = MAINT_TOPICS.find((entry) => entry.id === state.maintTopic);
  if (topic) {
    const actions = MAINT_ACTIONS.filter((action) => action.g === topic.id);
    return (
      <>
        <button className={crossReference()} data-part="cross-reference" data-maintopic="">
          {t("screens.maintenance.allCommands")}
        </button>
        <h2 className={sectionHeading()} data-part="heading">{topic.t}</h2>
        <div className={guidance()} data-part="guidance">{topic.s}</div>
        {facts(
          actions.map((action) => ({
            l: action.l,
            k: action.id,
            v: riskLabel(action.r),
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
          <button className={topicRow()} data-part="topic" data-maintopic={entry.id} key={entry.id}>
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

      <h2 className={sectionHeading()} data-part="heading">{t("screens.maintenance.journal")}</h2>
      <div className="note" data-part="note">
        {t("screens.maintenance.journalNote", { total: JOURNAL.total })}
      </div>
      {facts(JOURNAL.lignes)}
    </>
  );
}
