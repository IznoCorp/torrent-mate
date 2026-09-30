// A settled decision, read on its medium (L24 S1, OPEN 1 = C).
//
// ONE BLOCK, TWO SHEETS: the journey sheet draws it while the medium is in
// Acquisition, the Médiathèque sheet once it is shelved — the same component
// and the same derivation, so the two can never say it differently (§ 13).
// There is no list of decisions anywhere: a decision is read on the medium it
// was about.
//
// It says what was chosen, among how many candidates, by whom — the operator,
// by a pick or a manual search, or the engine, alone — and when. A decision
// left as it was, or superseded since, says its own sentence in the choice's
// place. While a decision is PENDING nothing is drawn: the medium is an
// « À traiter » card and its card opens the arbitration.
import { useTranslation } from "react-i18next";
import { registerBlock } from "../../ui/panel/contract";
import { actionButton, factsPanel, keyValueRow, ruleNote, sheetActions, sheetFacts, sectionHeading } from "../../ui/variants";
import { Icon } from "../../ui/icon";
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useDecisions, type Decisions } from "./decision-queries";
import { decisionHeadingPlace } from "./variants";
import { decisionState, decisionStateDetail, viaLabel } from "./decision-vocabulary";
import type { SettledDecision } from "./types";

declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    decision: { subject: string };
  }
}

/** A medium, as the block finds its decision: its title, and its provider ids when known. */
export type DecisionSubject = { title: string; ids?: Record<string, string | number | null | undefined> };

/**
 * The medium's latest settled decision, or none — nothing while one is pending.
 *
 * THE ONE DERIVATION both sheets read. A decision is the medium's when its
 * choice names one of the medium's provider ids, or, lacking ids, when its
 * folder or its title is the medium's. The settled list is newest first, so the first
 * match is the latest.
 *
 * @param decisions The decisions read, both lists.
 * @param subject The medium.
 * @returns The decision, or null.
 */
export function settledDecisionOf(decisions: Decisions | undefined, subject: DecisionSubject): SettledDecision | null {
  if (decisions === undefined) return null;
  if (decisions.pending.some((pending) => pending.title === subject.title)) return null;
  const known = Object.entries(subject.ids ?? {}).filter(([, id]) => id !== null && id !== undefined && id !== "");
  const byId = (decision: SettledDecision) =>
    decision.choice !== undefined &&
    known.some(([provider, id]) => provider === decision.choice!.provider && String(id) === String(decision.choice!.id));
  const byTitle = (decision: SettledDecision) =>
    decision.folder === subject.title || decision.title === subject.title || decision.choice?.title === subject.title;
  return decisions.settled.find(known.length > 0 ? byId : byTitle) ?? null;
}

/**
 * The block: a medium's settled decision, or nothing.
 *
 * @param props.subject The medium.
 * @returns The block, or null when the medium has no settled decision.
 */
export function DecisionBlock({ subject }: { subject: DecisionSubject }) {
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const { data } = useDecisions();
  const decision = settledDecisionOf(data, subject);
  if (decision === null) return null;
  const state = decisionState(decision.state);
  const rows: [string, string, string][] = [
    decision.state === "resolved" && decision.choice
      ? ["choice", t("surfaces.decision.chosen"),
         `${decision.choice.title} · ${decision.choice.provider.toUpperCase()} ${decision.choice.id}`]
      : ["state", t("surfaces.decision.state"), state?.[1] ?? decision.state],
    ["count", t("surfaces.decision.among"), t("surfaces.decision.candidates", { count: decision.candidatesCount })],
    ["author", t("surfaces.decision.by"),
     decision.settledBy === "engine"
       ? t("surfaces.decision.byEngine")
       : decision.choice
         ? t("surfaces.decision.byOperator", { via: viaLabel(decision.choice.via) })
         : t("surfaces.decision.byOperatorAlone")],
    ["when", t("surfaces.decision.when"), decision.when],
  ];
  return (
    <section data-part="decision" data-decision-id={decision.id} data-settled-by={decision.settledBy}>
      <h2 className={`${sectionHeading()} ${decisionHeadingPlace()}`} data-part="heading">{t("surfaces.decision.heading")}</h2>
      <div className={`${factsPanel()} ${sheetFacts()}`} data-part="panel">
        {rows.map(([part, caption, value]) => (
          <div key={part} className={keyValueRow()} data-part="key-value" data-decision-part={part}>
            <span>{caption}</span>
            <span>{value}</span>
          </div>
        ))}
        {decision.state === "resolved" ? null : (
          <p className={ruleNote()} data-decision-part="sentence">
            {decisionStateDetail(decision.state)}
          </p>
        )}
      </div>
      {/* « CORRIGER », the block's one act (S5): its verb creates or re-opens
          the decision, then opens the candidates screen. */}
      <div className={sheetActions()}>
        <button
          className={actionButton({ kind: "panelAction" })}
          data-part="decision/correct"
          data-decision-correct={decision.id}
        >
          <Icon paths={icons.search} />
          {t("surfaces.decision.correct")}
        </button>
      </div>
    </section>
  );
}

registerBlock("decision", (block) => <DecisionBlock subject={{ title: block.subject }} />);
