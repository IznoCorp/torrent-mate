// design/src/screens/resolution.tsx
// Legacy `openResolve(cible)` (`refonte.html`) — the arbitration screen —
// reborn as a real route (`/resolution/$folder`) and a final component.
// Markup is TRANSPLANTED, not translated: every tag, class and data-attribute
// below is the one the legacy screen drew, so the same stylesheet applies
// unchanged. `data-key="resolution:" + dossier` is an identity this screen
// never had — the legacy `openScreen(html, undefined, …)` passed no `cle` at
// all — added here because a router-owned screen needs one to answer
// `.screen.open[data-key^="resolution:"]` the way every other migrated screen
// already does.
//
// ── L'écran de résolution ────────────────────────────────────────────────
// One screen answers two questions that used to live on two pages: « what is
// stuck » and « which medium is it ». It is a SCREEN and not a panel — on
// `/medias` the arbitration appeared UNDER the list being read, and on a phone
// it was never seen.
//
// What it is asked about is a FOLDER. The name is set in the mono face and
// never cleaned up: it is what is on disk, and recognising it is the whole
// point.
//
// THE SCORE IS SHOWN ONLY WHEN IT SEPARATES. « Lucky » is the real case that
// settles this: four of its five candidates came back at exactly 1.00.
// Printing « 100 % » four times suggests a ranking that does not exist and
// invites the operator to trust it. When the leaders tie, the screen says so —
// and that sentence is the reason a human is being asked at all.
//
// The desktop deck's keyboard shortcuts (← → ⏎) have no phone. What they were
// for — going through several in a row — is kept as a plain progression:
// « 1 sur 2 », and « Suivante » once this one is answered.
//
// Three ways out, and the third is the one that was missing: pick a candidate,
// search by hand, or LEAVE IT AS IT IS. The last exists in the engine
// (`dismissed`) and nowhere in the interface, so a folder whose automatic
// result was right had no way of being agreed with.
//
// Every way out carries NO onClick: the document-level click delegation the
// legacy engine still runs is the seam this screen leans on, exactly as
// `media.tsx`, `profile.tsx` and `releases.tsx`. `data-resolve` (pick this
// candidate) is read by the branch that treats `state.resolveTarget` as the
// folder and the attribute as the CHOICE — which is why the shell's
// `window.__screens.resolution()` door writes that target before navigating.
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useDecisions } from "./queries";
import { useAcquisitionQueue, useStaging } from "../../lib/queue";
import { useArrivalsReference } from "../../features/arrivals/reference";
import { Candidates, DecisionCard } from "./resolution-cards";
import { type QueueCard } from "../../lib/engine-queue";
import { useStoreContent, useUiState } from "../../lib/store-access";
import { actionButton, backAction, body, emptyNote, qualityHint, ruleNote, screen, screenBar, scrollport, sectionHeading, sheetActions } from "../../ui/variants";
import { guidance } from "../../ui/variants/layout";
import { Icon } from "../../ui/icon";

export function ResolutionScreen() {
  const { folder: raw } = useParams({ from: "/resolution/$folder" });
  // Defensive: `__screens.resolution` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const folder = raw.normalize("NFC");
  // The queue lists (`world.blocked` / `world.stuck` / `world.stuckReel`) are
  // MUTATED IN PLACE by `actionResolve` / `actionLeave` (splice, unshift),
  // which bump the store's `version` through `render()` without producing a new
  // `state` reference. Subscribing to `version` is what makes the progression
  // (« 1 sur 2 ») and « Passer à la suivante » answer the queue as it is now —
  // the legacy screen re-opened itself for the same reason.
  useStoreContent((c) => c.version);
  const {
    icons,
    REASON_DETAIL,
    REASON_LABEL,
    REASON_TONE,
  } = useArrivalsReference();
  const { t } = useTranslation();
  // THE DECISIONS COME FROM THE CACHE (invariant 4). `decisionPending` and
  // `DECISIONS_REGLEES` were the engine's, read straight off the fixture; the
  // same two answers are derived here from `/api/decisions/`.
  //
  // THE QUEUE IS STILL THE ENGINE'S, and that is a measured decision rather
  // than an oversight. `derivedStuck` has FOUR readers — this screen, Arrivées,
  // Acquisition and the shell's own screen opener — and `leaveQueue` spans
  // `stuck`, `stuckReel` AND `blocked`, which is Acquisition's list. It is a
  // shared resource rather than a surface, its actions are driven by the
  // engine's document-level delegation, and it converts when its last reader
  // does. Splitting it here would leave two truths about one queue.
  const { data: decisions } = useDecisions();
  const scenario = String(useUiState().scen) === "loaded" ? "loaded" : "";
  const { data: staging } = useStaging(scenario);
  const { data: queue } = useAcquisitionQueue(scenario);
  const settledDecisions = decisions?.settled ?? [];
  const decisionPending = (subject: string | null) =>
    decisions?.pending.find((entry) => entry.d === subject) ?? null;
  // A folder either HAS a pending decision or it has none, and the screen must
  // not borrow one. Showing another folder's candidates would be the worst
  // possible lie on the one screen whose job is to name what is on disk.
  const decision = decisionPending(folder);
  // The queue spans BOTH surfaces a decision shows up on: « À traiter » on the
  // acquisition side and « Ça coince » in Arrivées. They are two views of one
  // thing — a folder the scrape could not name — and a progression that
  // counted only one of them would be wrong on the other.
  const pending = (queue?.blocked ?? [])
    .concat(staging?.stuck ?? [])
    .filter((card: QueueCard) => decisionPending(card.t as string) != null);
  const rank = decision
    ? pending.findIndex((card: QueueCard) => card.t === decision.d) + 1
    : 0;
  // The legacy screen picked its own subject between `decision.d` and
  // `state.resolveTarget`; here the ROUTE PARAM is the identity, and
  // `decisionPending` matches on that very `d` — so the two legacy branches
  // are one value. A target the door could not resolve at all reaches this
  // screen as the legacy's own last resort, « élément inconnu ».
  return (
    <section
      className={`${screen()} open`}
      data-part="screen"
      data-open=""
      data-key={`resolution:${folder}`}
      aria-label={folder}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => window.__bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.resolution.back")}
        </button>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={body()} data-part="surface/body" data-region="screen-resolution/body">
          <div className="note" data-part="note">
            <b>{t("screens.resolution.noteTitle")}</b>{" "}
            {t("screens.resolution.noteOn")} <code>/medias</code>{" "}
            {t("screens.resolution.noteAppeared")}{" "}
            <em>{t("screens.resolution.noteUnder")}</em>{" "}
            {t("screens.resolution.noteRest")}
          </div>
          <h2 className={sectionHeading()} data-part="heading">
            <code>{folder}</code>
          </h2>
          <p className={qualityHint()}>
            {decision
              ? (REASON_DETAIL[decision.reason] ?? "")
              : t("screens.resolution.noMediaIdentified")}
          </p>
          <div className="cmeta" data-part="card/meta" style={{ marginBottom: "12px" }}>
            {decision ? (
              <span
                className={`chip ${REASON_TONE[decision.reason] ?? "neutral"}`} data-part="chip"
                data-tone={REASON_TONE[decision.reason] ?? "neutral"}
              >
                {REASON_LABEL[decision.reason] ?? decision.reason}
              </span>
            ) : (
              ""
            )}
            {pending.length > 1 ? (
              <span className="caption" data-part="card/caption">
                {rank} {t("screens.resolution.outOf")} {pending.length}{" "}
                {t("screens.resolution.waiting")}
              </span>
            ) : (
              ""
            )}
          </div>
          {decision ? (
            <Candidates decision={decision} />
          ) : (
            <p className={ruleNote()}>{t("screens.resolution.noCandidates")}</p>
          )}
          <div className={emptyNote()} data-part="empty-state">
            <b>{t("screens.resolution.emptyTitle")}</b>
            {t("screens.resolution.emptyBody")}
            <button
              className={`cfoot ${actionButton()}`}
              data-part="card/foot"
              style={{ marginTop: "10px" }}
              data-manual={folder || undefined}
            >
              {t("screens.resolution.searchManually")}
            </button>
          </div>
          <div className={sheetActions({ secondary: true })} data-part="sheet/actions">
            <button className={`sact ${actionButton()}`} data-part="sheet/action" data-leave={folder || undefined}>
              <Icon paths={icons.check} />
              {t("screens.resolution.leaveAsIs")}
            </button>
            {pending.length > 1 ? (
              <button className={`sact ${actionButton()}`} data-part="sheet/action" data-next={folder}>
                <Icon paths={icons.right} />
                {t("screens.resolution.next")}
              </button>
            ) : (
              ""
            )}
          </div>
          <div className={guidance()} data-part="guidance">
            <b>{t("screens.resolution.note2Title")}</b>{" "}
            {t("screens.resolution.note2Body")}
          </div>
          {settledDecisions.length > 0 ? (
            <>
              <h2 className={sectionHeading()} data-part="heading" style={{ marginTop: "18px" }}>
                {t("screens.resolution.settledHeading")}
              </h2>
              <p className={qualityHint()}>{t("screens.resolution.settledHint")}</p>
              {settledDecisions.slice(0, 6).map((settled) => (
                <DecisionCard key={settled.d} decision={settled} />
              ))}
            </>
          ) : (
            ""
          )}
        </div>
      </div>
    </section>
  );
}
