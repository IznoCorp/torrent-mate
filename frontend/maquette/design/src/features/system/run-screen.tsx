// One passage, at its own address: what triggered it, how it ended, each step
// with its counts and its reasons, and its raw output folded away.
//
// THE NARRATIVE IS THE STEPS. A run's raw output is diagnosis material, and
// DOIT-1 asks this interface to speak clear French; so what a reader meets is
// the steps, composed in words from their counts, and the raw lines are a
// disclosure closed until someone asks for them.
//
// WHAT IS NOT KNOWN IS NOT PRINTED AS AN ANSWER (§13). A run still going has
// got to some steps and not others: the ones it has not got to are drawn as
// « — », never as « pas faite », and carry no count. A run nobody holds is
// said, with a way back, never drawn as an empty passage.
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useRun } from "./queries";
import { durationInWords, whenItRan } from "./run-list";
import { useEngineDrawing } from "../../lib/engine-drawing";
import {
  runError,
  runLog,
  runOutcome,
  runReason,
  runStep,
  runStepCounts,
  runStepHead,
  runStepStatus,
  runSummary,
} from "./variants";
import {
  backAction,
  body,
  crossReference,
  crossReferenceLink,
  factList,
  screen,
  screenBar,
  scrollport,
  sectionHeading,
} from "../../ui/variants";
import { guidance } from "../../ui/variants/layout";
import { Disclosure } from "../../ui/disclosure";
import { Icon } from "../../ui/icon";
import { SkeletonLine, SurfaceError } from "../../ui/state-surfaces";
import { bridge } from "../../lib/shell-doors";
import { isRequestFailure } from "../../lib/query-client";
import type { components } from "../../contract/types";

type RunDetail = components["schemas"]["RunDetail"];
type StepTiming = components["schemas"]["StepTiming"];
type Translate = (key: string, options?: Record<string, unknown>) => string;

/** The status the backend answers for a run nobody holds. */
const NOT_FOUND = 404;

/** What a run and a step still going are, as the contract's own token spells it. */
const RUNNING = "running";

/**
 * THE STEPS OF A PIPELINE PASSAGE, IN THE ORDER THEY RUN. The answer of a run
 * still going carries only the steps it has got to, so the ones ahead of it
 * are named from here — the interface's own knowledge of what a passage is,
 * used to say « not yet », never to say what they did.
 */
const PIPELINE_STEPS = [
  "ingest",
  "sort",
  "clean",
  "scrape",
  "cleanup",
  "enforce",
  "verify",
  "trailers",
  "dispatch",
];

/** Each count a step records, and the phrase it is said in. */
const COUNT_KEYS = [
  ["successCount", "screens.run.succeeded"],
  ["skipCount", "screens.run.skipped"],
  ["errorCount", "screens.run.failed"],
  ["unmatchedCount", "screens.run.unmatched"],
] as const;

/**
 * What one step counted, in words.
 *
 * A ZERO IS NOT SAID. « 0 ignoré » reads as a report that found something to
 * count; a step that counted nothing says so once.
 *
 * @param step The step, as the run recorded it.
 * @param say The translator.
 * @returns The composed line.
 */
function countsInWords(step: StepTiming, say: Translate): string {
  const parts = COUNT_KEYS.flatMap(([field, key]) => {
    const count = step[field] ?? 0;
    return count > 0 ? [say(key, { count })] : [];
  });
  for (const [name, count] of Object.entries(step.counts ?? {})) {
    if (count > 0) {
      parts.push(
        say("screens.run.counted", {
          name: say(`screens.run.count.${name}`, { defaultValue: name }),
          count,
        }),
      );
    }
  }
  return parts.length > 0
    ? parts.join(" · ")
    : say("screens.run.nothingCounted");
}

/**
 * The tone a run's outcome is drawn in.
 *
 * @param run The run.
 * @returns The tone.
 */
function outcomeTone(run: RunDetail): "success" | "danger" | "neutral" {
  if (run.outcome === "success") return "success";
  if (run.outcome === "error" || run.outcome === "killed") return "danger";
  return "neutral";
}

/**
 * One step, drawn: its name, its status, its counts, its reasons.
 *
 * @param props.step The step as recorded, or only its name when not yet got to.
 * @returns The row.
 */
function StepRow({
  step,
}: {
  step: StepTiming | { name: string; status?: undefined };
}): ReactElement {
  const { t } = useTranslation();
  const known = step.status !== undefined;
  const live = step.status === RUNNING;
  return (
    <li className={runStep()} data-part="run/step" data-step={step.name}>
      <span className={runStepHead()}>
        <span>
          {t(`screens.run.step.${step.name}`, { defaultValue: step.name })}
        </span>
        <span className={runStepStatus()} data-part="run/step-status">
          {known
            ? t(`screens.run.stepStatus.${step.status}`, {
                defaultValue: step.status,
              })
            : t("screens.run.stepStatus.unknown")}
        </span>
      </span>
      {known && !live ? (
        <span className={runStepCounts()} data-part="run/step-counts">
          {countsInWords(step as StepTiming, t)}
        </span>
      ) : null}
      {((step as StepTiming).reasons ?? []).map((reason, index) => (
        <span className={runReason()} data-part="run/reason" key={index}>
          {reason}
        </span>
      ))}
    </li>
  );
}

/**
 * What one passage says about itself, once its read has answered.
 *
 * @param props.run The run.
 * @returns The passage's body.
 */
function RunBody({ run }: { run: RunDetail }): ReactElement {
  const { t } = useTranslation();
  const going = run.outcome === RUNNING;
  const known = new Set(run.steps.map((step) => step.name));
  const ahead =
    going && run.kind === "pipeline"
      ? PIPELINE_STEPS.filter((name) => !known.has(name)).map((name) => ({
          name,
        }))
      : [];
  const duration = durationInWords(run.durationS, t);
  return (
    <>
      <div className={runSummary()}>
        <span
          className={runOutcome({ tone: outcomeTone(run) })}
          data-part="run/outcome"
        >
          {t(`screens.run.outcome.${run.outcome ?? RUNNING}`)}
        </span>
        <span data-part="run/trigger">
          {run.kind === "maintenance" && run.command
            ? t("screens.system.runCommand", { command: run.command })
            : t("screens.run.triggeredBy", {
                trigger: t(`screens.system.trigger.${run.trigger}`, {
                  defaultValue: run.trigger,
                }),
              })}
        </span>
        <span>{whenItRan(run)}</span>
        {duration !== "" ? (
          <span data-part="run/duration">{duration}</span>
        ) : null}
        {run.dryRun ? (
          <span data-part="run/dry-run">{t("screens.run.dryRun")}</span>
        ) : null}
      </div>

      {run.error ? (
        // THE FAILURE IS LOUD, and whole: the reason is data, and cutting it
        // short would be the interface deciding which part of it matters.
        <div role="alert">
          <h2 className={sectionHeading()} data-part="heading">
            {t("screens.run.error")}
          </h2>
          <p className={runError()} data-part="run/error">
            {run.error}
          </p>
        </div>
      ) : null}

      {run.optionsJson ? (
        <p className={runSummary()} data-part="run/options">
          {t("screens.run.options")} <code>{run.optionsJson}</code>
        </p>
      ) : null}

      {run.steps.length + ahead.length > 0 ? (
        <div>
          <h2 className={sectionHeading()} data-part="heading">
            {t("screens.run.steps")}
          </h2>
          <ol className={factList()} data-part="run/steps">
            {[...run.steps, ...ahead].map((step) => (
              <StepRow key={step.name} step={step} />
            ))}
          </ol>
        </div>
      ) : null}

      {going ? null : run.outputTail ? (
        <Disclosure
          summary={
            <span data-part="run/log-toggle">{t("screens.run.rawLog")}</span>
          }
        >
          {/* FOCUSABLE, because it scrolls sideways: a keyboard reaches a line
              wider than the screen only through a region it can focus. */}
          <pre className={runLog()} data-part="run/log" tabIndex={0}>
            {run.outputTail}
          </pre>
        </Disclosure>
      ) : (
        // NEVER AN EMPTY BOX. A run recorded before output capture existed has
        // no log, and an empty frame reads as « nothing happened ».
        <p className={guidance()} data-part="run/log">
          {t("screens.run.noLog")}
        </p>
      )}

      <button
        className={crossReference()}
        data-part="cross-reference"
        data-go="arr"
      >
        {t("screens.run.leftBehind")}
        <span className={crossReferenceLink()}>
          {t("screens.run.leftBehindLink")}
        </span>
      </button>
    </>
  );
}

/**
 * The run screen.
 *
 * @returns The passage's own surface, in whichever state its read left it.
 */
export function RunScreen(): ReactElement {
  const { runUid } = useParams({ from: "/run/$runUid" });
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const read = useRun(runUid);
  const missing =
    read.isError &&
    isRequestFailure(read.error) &&
    read.error.status === NOT_FOUND;

  return (
    <section
      className={screen({ open: true })}
      data-part="screen"
      data-open=""
      data-key={`run:${runUid}`}
      aria-label={t("screens.run.title")}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button
          className={backAction({ floor: true })}
          data-part="screen/back"
          onClick={() => bridge.back()}
        >
          <Icon paths={icons.left} />
          {t("screens.run.back")}
        </button>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={body()} data-part="run" data-region="run/body">
          {read.data !== undefined ? <RunBody run={read.data} /> : null}
          {read.isPending ? <SkeletonLine width="wide" /> : null}
          {missing ? (
            // A DOOR OUT, never a dead end (DOIT-7): a stale link lands here,
            // and the passages it came from are one tap away.
            <div className={guidance()} data-part="run/not-found">
              {t("screens.run.notFound")}{" "}
              <button className={backAction({ floor: true })} data-go="sys">
                {t("screens.run.notFoundBack")}
              </button>
            </div>
          ) : null}
          {read.isError && !missing ? (
            <SurfaceError
              subject={t("screens.run.errorSubject")}
              detail={
                isRequestFailure(read.error) ? read.error.detail : undefined
              }
              onRetry={() => void read.refetch()}
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}
