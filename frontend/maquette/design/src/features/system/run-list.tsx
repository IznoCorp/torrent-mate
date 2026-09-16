// « Les passages » — what the machine has done lately, one row per run.
//
// A ROW IS A PATH. Each run has its own address, and the row leads there: the
// list answers « what happened », the screen behind it answers « what happened
// in that one ». A list that shows a summary and nothing to open is a list the
// reader has to take on trust.
//
// THE LINE IS COMPOSED HERE, from the counts. A server sending « 1 rangé · 1
// bloqué » would be writing the interface's words for it, and the demand
// register asks for the figures instead. So this file builds the sentence, and
// the rule reads the figures against it.
//
// AND A SHORT LIST SAYS IT IS SHORT. `degraded` means the read failed and what
// is drawn may be missing rows: printing it as a complete list is the clause
// NE-DOIT-PAS-5 names, and the sentence sits ABOVE the rows it qualifies.
import { useTranslation } from "react-i18next";
import { crossReference, crossReferenceLink, factList, sectionHeading } from "../../ui/variants";
import { runHead, runLine, runRow } from "./variants";
import { guidance } from "../../ui/variants/layout";
import { usePipelineHistory } from "./queries";
import "./run-verbs";
import type { ReactElement } from "react";
import type { components } from "../../contract/types";

type RunSummary = components["schemas"]["RunSummary"];

/** Seconds in a minute, for the duration a row says. */
const MINUTE = 60;
/** Seconds in an hour: from there on, a duration is said in minutes alone. */
const HOUR = 60 * MINUTE;

/** The step whose success count is what a passage RANGED. */
const DISPATCH = "dispatch";
/** The step that blocks what it cannot pass. */
const VERIFY = "verify";
/** What a maintenance run is, as the contract's own token spells it. */
const MAINTENANCE = "maintenance";
/** The command a veille runs, as the history records it. */
const DETECTION_COMMAND = "follow-detect";

/**
 * THE WORD EACH OUTCOME WEARS, one per outcome (NE-DOIT-PAS-1): a run still
 * going, stopped or paused is not « réussi », and a map with two words for five
 * outcomes is how it came to say so.
 */
const OUTCOME_WORDS: Record<components["schemas"]["RunOutcome"], string> = {
  success: "screens.system.runSucceeded",
  error: "screens.system.runFailed",
  running: "screens.system.runRunning",
  killed: "screens.system.runKilled",
  paused: "screens.system.runPaused",
};

/**
 * When a passage ran, as the row says it.
 *
 * COMPOSED FROM THE INSTANT, never printed raw. An ISO timestamp is a machine's
 * way of writing a date, and this interface's reader is not a machine; the six
 * runs whose fixture line carries a rendered date keep theirs, because that is
 * what the engine drew and the oracle measures.
 *
 * @param run The run.
 * @returns The day and the hour, in the shape the page already uses.
 */
export function whenItRan(run: Pick<RunSummary, "startedAt" | "when">): string {
  if (run.when !== undefined) return run.when;
  const instant = new Date(run.startedAt);
  const day = String(instant.getDate()).padStart(2, "0");
  const month = String(instant.getMonth() + 1).padStart(2, "0");
  const hour = String(instant.getHours()).padStart(2, "0");
  const minute = String(instant.getMinutes()).padStart(2, "0");
  return `${day}/${month} ${hour} h ${minute}`;
}

/**
 * One duration, as the row says it.
 *
 * @param seconds How long it took, or null when the run has not ended.
 * @param say The translator.
 * @returns The duration in words, or an empty string.
 */
export function durationInWords(seconds: number | null | undefined,
                         say: (key: string, options?: { count: number; seconds?: string }) => string): string {
  if (seconds === null || seconds === undefined) return "";
  const total = Math.round(seconds);
  if (total < MINUTE) return say("screens.system.runSeconds", { count: total });
  if (total >= HOUR) return say("screens.system.runMinutes", { count: Math.round(seconds / MINUTE) });
  // UNDER AN HOUR THE SECONDS ARE SAID. Rounded to the minute, 104 s read
  // « 2 min » and 439 s « 7 min »: a passage's length is what the row reports,
  // and a figure a minute off is not that length.
  const minute = Math.floor(total / MINUTE);
  const rest = total % MINUTE;
  if (rest === 0) return say("screens.system.runMinutes", { count: minute });
  return say("screens.system.runMinutesSeconds", { count: minute, seconds: String(rest).padStart(2, "0") });
}

/**
 * What one passage DID, composed from the counts it recorded.
 *
 * @param run The run, as the history answers it.
 * @param say The translator.
 * @returns The composite line.
 */
function whatItDid(run: RunSummary,
                   say: (key: string, options?: { count: number }) => string): string {
  const steps = run.steps ?? [];
  const duration = durationInWords(run.durationS, say);
  // PER KIND. A detection counts what it detected, and « rien de nouveau »
  // over a count is the report contradicting itself; a run still going and a
  // command whose steps count nothing have nothing to report yet but their time.
  if (run.command === DETECTION_COMMAND || run.kind === MAINTENANCE || run.outcome === "running") {
    const found = run.command === DETECTION_COMMAND
      ? (steps[0]?.counts as { detected?: number } | undefined)?.detected
      : undefined;
    const parts = [];
    if (found !== undefined) {
      parts.push(found === 0
        ? say("screens.system.runNothing", { count: 0 })
        : say("screens.system.detectedCount", { count: found }));
    }
    if (duration !== "") parts.push(duration);
    return parts.join(" · ");
  }
  const dispatched = steps.find((step) => step.name === DISPATCH)?.successCount ?? 0;
  const verified = steps.find((step) => step.name === VERIFY);
  const blocked = (verified?.errorCount ?? 0) + (verified?.unmatchedCount ?? 0);
  const parts = [];
  // NOTHING IS A SENTENCE OF ITS OWN. « 0 rangé » reads as a report that counted
  // something; « rien de nouveau » is what the run actually found.
  parts.push(dispatched === 0
    ? say("screens.system.runNothing", { count: 0 })
    : say("screens.system.runSorted", { count: dispatched }));
  if (blocked > 0) parts.push(say("screens.system.runBlocked", { count: blocked }));
  if (duration !== "") parts.push(duration);
  return parts.join(" · ");
}

/**
 * The passages, newest first, each one a path to its own screen.
 *
 * @returns The section, in whichever of its states the read left it.
 */
export function RunList(): ReactElement {
  const { t } = useTranslation();
  const { data: history } = usePipelineHistory();
  const runs = history?.runs ?? [];

  return (
    <div data-part="runs" data-region="system/runs">
      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.runs")}</h2>

      {history?.degraded ? (
        // ABOVE THE ROWS IT QUALIFIES, because a warning under a list is read
        // after the list has already been believed.
        <div className={guidance()} data-part="runs/degraded">
          {t("screens.system.runsDegraded")}
        </div>
      ) : null}

      {history !== undefined && runs.length === 0 ? (
        <div className={guidance()} data-part="runs/empty">{t("screens.system.noRuns")}</div>
      ) : null}

      <ol className={factList()} data-part="flux">
        {runs.map((run) => (
          <li key={run.runUid}>
            <button className={runRow()} data-part="runs/row" data-run={run.runUid}>
              <span className={runHead()}>
                <span data-part="runs/when">{whenItRan(run)}</span>
                <span data-part="runs/trigger">
                  {run.kind === MAINTENANCE && run.command
                    ? t("screens.system.runCommand", { command: run.command })
                    : t(`screens.system.trigger.${run.trigger}`, { defaultValue: run.trigger })}
                </span>
                <span data-part="runs/outcome">{run.outcome ? t(OUTCOME_WORDS[run.outcome]) : null}</span>
              </span>
              <span className={runLine()} data-part="runs/line">{whatItDid(run, t)}</span>
            </button>
          </li>
        ))}
      </ol>

      <button className={crossReference()} data-part="cross-reference" data-go="arr">
        {t("screens.system.toArrivals")}
        <span className={crossReferenceLink()}>{t("screens.system.toArrivalsLink")}</span>
      </button>
    </div>
  );
}
