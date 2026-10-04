// The pipeline's levers: what governs ALL media at once.
//
// ONE BUTTON, NEVER TWO. Pause and resume are one question — is this run to be
// held? — so the section offers the one the machine's state admits, and when
// nothing runs it offers neither AND SAYS WHY. A control that is simply absent
// leaves the reader looking for it; §8 asks for the reason instead.
//
// THE BOUND IS A PATH, NOT A CONTROL. A setting is edited where settings are
// edited: the row says what it is worth and leads to its own panel. That is the
// operator's ruling, and it is why this file has a row and not a field.
//
// WHAT IS NOT KNOWN IS NOT PRINTED (§13). While either read is in flight the
// section draws its PLACE and no values: a bound printed as `0`, or a lock
// printed « Libre », before the answer arrives is a lie the reader cannot tell
// from a fact.
import { useRights } from "../../lib/account";
import "./lever-verbs";
import { useTranslation } from "react-i18next";
import { Skeletons } from "../../ui/state-surfaces";
import { actionButton } from "../../ui/variants/controls";
import { factList, guidance, topicRow } from "../../ui/variants";
import { FactRows } from "../../ui/fact-rows";
import { ageInWords } from "./locks";
import { WatchBlock } from "./watch";
import { useLocks } from "./locks-queries";
import { useBoundSetting, usePipelineState } from "./queries";
import type { ReactElement } from "react";

/** What the automatic trigger's control carries when a press would turn it on. */
const TURN_ON = "on";
const TURN_OFF = "off";

/** How many placeholders stand for the section while its reads are in flight. */
const WAITING_ROWS = 3;

/**
 * The levers: the bound, pause or resume, and the automatic trigger.
 *
 * @returns The section's controls, or its place while the reads are in flight.
 */
export function Levers(): ReactElement {
  const { t } = useTranslation();
  const { data: locks } = useLocks();
  const { data: pipeline } = usePipelineState();
  const bound = useBoundSetting();
  // THE LEVERS ARE WRITES (`pipeline.control`): absent for an account that does
  // not hold it, and under a ceiling that forbids it — the rows still say the state.
  const control = useRights().holds("pipeline.control");

  // NEITHER READ HAS ANSWERED: the place is drawn and nothing else. The parts
  // below are what the values will land in, so their names exist only once the
  // values do — a part with no value is the shape §13 refuses.
  if (locks === undefined || pipeline === undefined) {
    return (
      <div data-part="levers" data-region="system/levers">
        <Skeletons count={WAITING_ROWS} shape="card" />
      </div>
    );
  }

  const running = pipeline.state === "running";
  const paused = pipeline.state === "paused" || locks.sentinels.pause;
  const queued = pipeline.state === "queued";
  const idle = !running && !paused && !queued;
  // THE AUTOMATIC TRIGGER IS WATCHING only when it is on AND its process answers.
  const watching = pipeline.watcherEnabled === true && pipeline.watcherDown !== true;

  return (
    <div data-part="levers" data-region="system/levers">
      {/* A PATH ONLY WHERE THERE IS SOMEWHERE TO GO. While the key is a demand
          the catalogue does not hold, the row says what it is worth — « pas
          encore réglable » — and offers no door onto a panel that would not
          open: DOIT-7 refuses a dead end, and a control leading nowhere is one. */}
      <div className={topicRow()} data-part="levers/bound" data-bound={bound?.identity}>
        <span>{t("screens.system.bound")}</span>
        <span data-part="levers/bound-value">{bound?.said}</span>
        {bound?.identity === undefined ? null : <span>{t("screens.system.boundEdit")}</span>}
      </div>

      {/* THE ONE THE STATE ADMITS. Pause while a run is going, resume while it
          is held, and when nothing runs the reason rather than a dead control. */}
      {control && paused ? (
        <button className={actionButton({ kind: "cardFoot" })} data-part="levers/resume" data-pipeline-resume="">
          {t("screens.system.resumeAll")}
        </button>
      ) : null}
      {control && (running || queued) && !paused ? (
        <button className={actionButton({ kind: "cardFoot" })} data-part="levers/pause" data-pipeline-pause="">
          {t("screens.system.pauseAll")}
        </button>
      ) : null}
      {idle ? (
        <div className={guidance()} data-part="levers/nothing-running">
          {t("screens.system.nothingRunning")}
        </div>
      ) : null}
      {queued ? (
        // DOIT-4: what was asked of a busy machine is WAITING, and the screen
        // says so. It is never refused and never silently dropped.
        <div className={guidance()} data-part="levers/queued">
          {t("screens.system.pipelineQueued")}
        </div>
      ) : null}

      {/* THE CONTROL NAMES THE ACT, THE ROW SAYS THE STATE. A label reading
          « actif » does not say whether a press turns it on or off. */}
      {/* ONE ROW FOR ONE FACT: the automatic processing is said here, beside
          the control that moves it, and nowhere else on the page. */}
      {/* OFF BY A PERSON IS ORANGE, OFF BY A FAULT IS RED: a pause someone
          chose is not a failure, and a failure nobody chose must not read as
          a pause. */}
      <ol className={factList()} data-part="levers/watcher-state">
        <FactRows rows={[{
          label: t("screens.system.automaticTrigger"),
          value: watching ? t("states.active") : t("states.inactive"),
          tone: watching ? "success" : pipeline.watcherEnabled ? "alert" : "warning",
          secondaryLine: watching
            ? undefined
            : pipeline.watcherEnabled
              ? t("screens.system.automaticTriggerDown")
              : ageInWords(locks.sentinels.watcherPausedAgeS, t),
        }]} />
      </ol>
      {control ? <button
        className={actionButton({ kind: "cardFoot" })}
        data-part="levers/watcher"
        data-watcher={pipeline.watcherEnabled ? TURN_OFF : TURN_ON}
      >
        {pipeline.watcherEnabled ? t("screens.system.turnTriggerOff") : t("screens.system.turnTriggerOn")}
      </button> : null}
      {watching ? null : (
        <div className={guidance()} data-part="levers/trigger-consequence">
          {t("screens.system.automaticTriggerOff")}
        </div>
      )}

      <WatchBlock />
    </div>
  );
}
