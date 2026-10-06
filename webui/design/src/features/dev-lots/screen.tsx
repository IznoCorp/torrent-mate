// « Avancement des lots » — where the work stands, lot by lot, on the design host.
//
// IT DRAWS WHAT THE HOST GENERATED, never a list written here: one card per
// lot, each phase with its state — planned, in progress, PR open, merged — its
// pull requests and what blocks it. Nothing on it acts: the page is read, and
// its links lead to the pull requests themselves.
//
// FOUR CASES, each drawn: the read in flight (placeholders), the read failed
// (the error surface, with a retry that re-asks), the host serving nothing (a
// notice — every host but the design host), and the lots.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Chip } from "../../ui/chip";
import { Icon } from "../../ui/icon";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { useEngineDrawing } from "../../lib/engine-drawing";
import { momentOf } from "../../lib/clock";
import { bridge } from "../../lib/shell-doors";
import type { ChipTone } from "../../ui/variants";
import { backAction, body, factName, screen, screenBar, scrollport } from "../../ui/variants";
import { lotsKey, readLots, type Lot, type LotPhase, type PhaseState } from "./queries";
import {
  lotBlocker, lotCard, lotCount, lotHead, lotList, lotName, lotsStamp, phaseFacts, phaseHead, phaseId, phaseList,
  phaseRow, phaseTitle, pullRequestLink,
} from "./variants";

// The tone each state earns: nothing begun is quiet, work under way informs,
// a PR waiting for its merge asks for attention, a merge is good news.
const TONE: Record<PhaseState, ChipTone> = {
  planned: "neutral",
  "in-progress": "info",
  "pr-open": "warning",
  merged: "success",
};

/**
 * The lots progress, read from the host once per session unless re-asked.
 *
 * @returns The query.
 */
function useLots() {
  // A FAILED READ STAYS FAILED ON MOUNT: « Réessayer » is what re-asks, so the
  // error the reader saw is never replaced by a silent second attempt.
  return useQuery({ queryKey: lotsKey, queryFn: () => readLots(), retryOnMount: false });
}

/**
 * One phase's row.
 *
 * @param properties The phase.
 * @returns The row.
 */
function PhaseRow({ phase }: { phase: LotPhase }): ReactElement {
  const { t } = useTranslation();
  return (
    <li className={phaseRow()} data-part="lots/phase" data-phase={phase.id} data-state={phase.state}>
      <span className={phaseHead()}>
        <span className={phaseId()}>{phase.id}</span>
        <span className={phaseTitle()} data-part="lots/phase-title">{phase.title}</span>
      </span>
      <span className={phaseFacts()}>
        <Chip tone={TONE[phase.state]} label={t(`screens.devLots.state.${phase.state}`)} />
        {phase.dispatch ? (
          <span data-part="lots/dispatch">{t(`screens.devLots.dispatch.${phase.dispatch}`, phase.dispatch)}</span>
        ) : null}
        {phase.prs.map((pr) => (
          <a key={pr.number} className={pullRequestLink()} data-part="lots/pr" data-state={pr.state} href={pr.url}
            target="_blank" rel="noreferrer">
            {t("screens.devLots.pr", { number: pr.number })}
          </a>
        ))}
      </span>
      {phase.blockedBy ? (
        <span className={lotBlocker()} data-part="lots/blocker">
          {t("screens.devLots.blockedBy", { reason: phase.blockedBy })}
        </span>
      ) : null}
    </li>
  );
}

/**
 * One lot's card.
 *
 * @param properties The lot.
 * @returns The card.
 */
function LotCard({ lot }: { lot: Lot }): ReactElement {
  const { t } = useTranslation();
  return (
    <li className={lotCard()} data-part="lots/lot" data-lot={lot.id}>
      <div className={lotHead()}>
        <h2 className={lotName()} data-part="lots/lot-name">{lot.name}</h2>
        <span className={lotCount()}>{t("screens.devLots.phases", { count: lot.phases.length })}</span>
      </div>
      {lot.blockedBy ? (
        <span className={lotBlocker()} data-part="lots/blocker">
          {t("screens.devLots.blockedBy", { reason: lot.blockedBy })}
        </span>
      ) : null}
      <ol className={phaseList()}>
        {lot.phases.map((phase) => <PhaseRow key={phase.id} phase={phase} />)}
      </ol>
    </li>
  );
}

/**
 * The lots progress screen.
 *
 * @returns The screen, in whichever of its four cases the read leaves it.
 */
export function DevLotsScreen(): ReactElement {
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const { data, isPending, isError, error, refetch } = useLots();
  return (
    <section className={screen({ open: true })} data-part="screen" data-open="" data-key="dev-lots"
      aria-label={t("screens.devLots.title")}>
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.devLots.back")}
        </button>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={body()} data-part="surface/body" data-region="screen-dev-lots/body">
          <h1 className={factName()}>{t("screens.devLots.title")}</h1>
          {isPending ? <Skeletons count={3} shape="card" /> : null}
          {isError ? (
            <SurfaceError subject={t("screens.devLots.errorSubject")} failure={error ?? undefined}
              onRetry={() => void refetch()} />
          ) : null}
          {data && !data.available ? (
            <SurfaceError tone="info" part="lots/unavailable">{t("screens.devLots.unavailable")}</SurfaceError>
          ) : null}
          {data?.available ? (
            <>
              <p className={lotsStamp()} data-part="lots/stamp">
                {t("screens.devLots.updated", { moment: momentOf(data.generatedAt) })}
              </p>
              {data.lots.length === 0 ? (
                <SurfaceError tone="info" part="lots/none">{t("screens.devLots.noLots")}</SurfaceError>
              ) : (
                <ol className={lotList()} data-part="lots/list">
                  {data.lots.map((lot) => <LotCard key={lot.id} lot={lot} />)}
                </ol>
              )}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
