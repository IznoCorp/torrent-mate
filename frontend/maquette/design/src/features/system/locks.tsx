// What holds the pipeline, and what a crash left behind.
//
// FOUR FACTS, AND EACH CARRIES WHAT MAKES IT DECIDABLE. « Pris » is not a fact
// anybody can act on; « Pris — il y a 4 jours » is. So every row that has an
// age says it, and the two sentinels say « Inactive » rather than nothing when
// they are off — a blank reads as « not asked », which is what §8 refuses.
//
// NO PROCESS IDENTIFIER IS PRINTED. The answer carries one and this block draws
// it nowhere: a pid is jargon to the person this interface is for, and the
// width is the rare resource. What is printed is the AGE, which is what the
// operator decides on.
//
// AND THE REPAIR IS A PATH. A stale lock and a list of leftovers are repaired by
// a Maintenance command, so this block offers the way there and no verb of its
// own — the block that REPORTS is not the block that ACTS.
import { useTranslation } from "react-i18next";
import { FactRows, type FactRow } from "../../ui/fact-rows";
import { Skeletons } from "../../ui/state-surfaces";
import { crossReference, crossReferenceLink, factList } from "../../ui/variants";
import { useLocks } from "./locks-queries";
import type { ReactElement } from "react";

/** Seconds in the units an age is said in. */
const MINUTE = 60;
const HOUR = 3600;
const DAY = 86400;

/** What an age is said with: the interface's own words, by count. */
type SayAge = (key: string, options?: { count: number }) => string;

/**
 * One age, in the words the interface says it in.
 *
 * ROUNDED DOWN TO THE UNIT THAT MATTERS, never printed in seconds: the reader
 * decides « is this normal » on the order of magnitude, and « il y a 295 834 s »
 * makes that arithmetic theirs instead of the interface's.
 *
 * @param seconds How long ago, or null when the fact has no age.
 * @param say The translator.
 * @returns The age in words, or an empty string when there is none.
 */
function ageInWords(seconds: number | null | undefined, say: SayAge): string {
  if (seconds === null || seconds === undefined) return "";
  if (seconds < MINUTE) return say("screens.system.ageNow");
  if (seconds < HOUR) {
    return say("screens.system.ageMinutes", { count: Math.floor(seconds / MINUTE) });
  }
  if (seconds < DAY) return say("screens.system.ageHours", { count: Math.floor(seconds / HOUR) });
  return say("screens.system.ageDays", { count: Math.floor(seconds / DAY) });
}

/**
 * The locks block: what holds the pipeline, and what a crash left behind.
 *
 * @returns The four fact rows, the entries the sweep found, and the way to the
 *   command that repairs them.
 */
export function LocksBlock(): ReactElement {
  const { t } = useTranslation();
  const { data: locks } = useLocks();

  // THE READ HAS NOT ANSWERED YET: the whole block is a skeleton, because none
  // of the four facts is known. That is the one case where a skeleton over the
  // block is right — §13's « what is unknown is not printed as an answer ».
  if (locks === undefined) {
    return (
      <div data-part="locks" data-region="system/locks">
        <Skeletons count={4} shape="card" />
      </div>
    );
  }

  const lock = locks.pipelineLock;
  const sentinels = locks.sentinels;
  const lockValue = lock.stale
    ? t("screens.system.lockStale")
    : lock.held
      ? t("screens.system.lockHeld", { age: ageInWords(lock.ageS, t) })
      : t("screens.system.lockFree");

  const rows: FactRow[] = [
    {
      label: t("screens.system.pipelineLock"),
      value: lockValue,
      tone: lock.stale ? "alert" : lock.held ? "info" : "success",
      secondaryLine: lock.stale ? t("screens.system.lockStaleLine") : undefined,
    },
    {
      label: t("screens.system.pauseSentinel"),
      value: sentinels.pause
        ? t("screens.system.sentinelOn", { age: ageInWords(sentinels.pauseAgeS, t) })
        : t("screens.system.sentinelOff"),
      tone: sentinels.pause ? "warning" : "success",
    },
    {
      label: t("screens.system.watcherSentinel"),
      value: sentinels.watcherPaused
        ? t("screens.system.watcherOff", {
            age: ageInWords(sentinels.watcherPausedAgeS, t),
          })
        : t("screens.system.watcherOn"),
      tone: sentinels.watcherPaused ? "warning" : "success",
    },
  ];

  // THE PARTS ARE NAMED ONE BY ONE, in the order the rows are built: the rule
  // reads each fact by its own name, so a block that drew three of four says
  // WHICH one is missing rather than « the block is wrong ».
  const PARTS = ["locks/pipeline", "locks/pause-sentinel", "locks/watcher-sentinel"];

  return (
    <div data-part="locks" data-region="system/locks">
      <ol className={factList()} data-part="flux">
        <FactRows rows={rows.map((row, index) => ({ ...row, part: PARTS[index] }))} />
      </ol>

      <div data-part="locks/sweep">
        {locks.sweep.status === "pending" ? (
          // ONLY THIS BLOCK WAITS. Three facts have already answered above, and
          // a skeleton over the section would hide them to say one thing is
          // still being counted.
          <Skeletons count={1} shape="card" />
        ) : (
          <ol className={factList()} data-part="flux">
            <FactRows
              rows={[{
                label: t("screens.system.tmpOrphans"),
                value: locks.sweep.orphans.length === 0
                  ? t("screens.system.orphansNone")
                  : t("screens.system.orphansFound", { count: locks.sweep.orphans.length }),
                tone: locks.sweep.orphans.length === 0 ? "success" : "warning",
              }]}
            />
            <FactRows
              rows={locks.sweep.orphans.map((orphan) => ({
                label: orphan.path,
                value: ageInWords(orphan.ageS, t),
                secondaryLine: orphan.prefix,
                part: "locks/orphan",
              }))}
            />
          </ol>
        )}
      </div>

      <button className={crossReference()} data-part="cross-reference" data-page="maint">
        {t("screens.system.toLocksRepair")}
        <span className={crossReferenceLink()}>{t("screens.system.toMaintenanceLink")}</span>
      </button>
    </div>
  );
}
