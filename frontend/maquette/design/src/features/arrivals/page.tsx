// design/src/pages/arrivals.tsx
// The fourth migrated PAGE: legacy `viewArrivals()` — with `barrePipelineHTML()`
// and `dernierPassageHTML()`, whose only caller it was — reborn as a final
// component. Markup is TRANSPLANTED, not translated.
//
// Arrivées carries the PIPELINE's health: what is stuck, what is moving, what
// arrived, and the run itself. A machine in trouble is Système's business; a
// medium in trouble is this page's, and that cut is what decides where a panel
// belongs — never the page it came from.
//
// THE FIRST MIGRATED PAGE THAT CARRIES A CONTROL WHICH MUTATES. The pilot's bar
// emits `data-pipe="start"` / `"stop"` and nothing else: the writing stays
// the document-level delegation's, exactly as it was, so this component never
// touches the world. Its three states include the one DOIT-4 exists for — an
// action asked during a run is QUEUED, visibly, never refused with « busy, try
// again ».
//
// The cards go through `cardHTML` and the fact rows through `factRowsHTML`,
// both reused VERBATIM: the delegated handlers depend on that markup being
// byte-exact. A section goes through `secInner`, the inside of the `secHTML`
// the acquisition page's five sections still share — this component draws the
// `<section class="sec">` itself, because React cannot set the outer markup of
// a node it also renders,
// and it reproduces the outer function's EMPTY case by drawing no section at
// all.
import { useTranslation } from "react-i18next";
import { SurfaceError } from "../../ui/state-surfaces";
import type { ReactElement } from "react";
import { useArrivalsReference, type PipelineFact } from "../../features/arrivals/reference";
import { usePipeline } from "./queries";
import { useStaging } from "../../lib/queue";
import { type QueueCard } from "../../lib/engine-queue";
import { useUiState } from "../../lib/store-access";
import {
  actionButton,
  crossReference,
  crossReferenceLink,
  emptyNote,
  liveDot,
  liveEmphasis,
  liveStrip,
  // `section` and `pip` are already local bindings in this file; the variants
  // are imported under their own names rather than shadowing them.
  section as sectionClass,
  sectionCount,
  sectionHead,
  sectionTitle,
  statusDot as statusDotClass,
  } from "../../ui/variants";
import {
  pilotActions,
  pilotBar,
  pilotGauge,
  pilotHead,
  pilotQualifier,
  pilotTitle,
} from "./variants";
import { Markup } from "../../ui/markup";

// The nine steps, told as the last run left them. A step with nothing recorded
// at all reads « rien à faire »; a step that BLOCKED something says so and
// points just below, where the stuck section is. The two sentences are
// different on purpose: a step that looked and found everything already in
// order is not a step that had nothing to look at.
function lastRunRows(
  steps: { n: string; l: string }[],
  facts: PipelineFact[],
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  const byName = Object.fromEntries(facts.map((fact) => [fact.n, fact]));
  return steps.map((step) => {
    const fact: PipelineFact = byName[step.n] || { n: step.n };
    const nothing = !fact.r && !fact.s && !fact.blockedCount;
    return {
      l: step.l,
      k: step.n,
      v: fact.blockedCount
        ? `${fact.r ? fact.r + " · " : ""}${t("screens.arrivals.blockedCount", { count: fact.blockedCount })}`
        : fact.r || "",
      s: fact.blockedCount
        ? `${fact.s ? fact.s + " · " : ""}${t("screens.arrivals.blockedBelow")}`
        : nothing
          ? t("screens.arrivals.nothingToDo")
          : fact.s || "",
      state: fact.blockedCount ? "danger" : "",
    };
  });
}

// The pilot's bar. Three states, and the third is the one DOIT-4 exists for:
// an action asked at a bad moment is QUEUED, visibly, and never refused with
// « occupé, réessaie ».
function PipelineBar(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  // FROM THE CACHE (invariant 4), not from `window.__referentiel`. Nothing is
  // drawn until it has answered: the oracle measures at rest, so what it reads
  // is the settled bar — the same bar, from the same bytes, since the seed is
  // held against the fixture it replaced.
  const { data: PIPELINE } = usePipeline();
  if (!PIPELINE) return null;

  if (state.pipe === "running" || state.pipe === "queued") {
    const step = PIPELINE.steps[3];
    return (
      <section className={pilotBar()} data-part="pipeline" data-region="arrivals/pilot-bar">
        <div className={pilotHead()}>
          <span className={statusDotClass({ tone: "info" })} data-part="status-dot" data-tone="info"></span>
          <span className={pilotTitle()} data-part="pipeline/title">{t("screens.arrivals.runningTitle")}</span>
          <span className={pilotQualifier()}>
            {t("screens.arrivals.stepOf", {
              count: PIPELINE.steps.length,
              label: step.l,
            })}
          </span>
        </div>
        <div className={pilotGauge()}>
          <i className="block h-full bg-info rounded-[inherit]" style={{ width: "44%" }}></i>
        </div>
        {/* « Relancer ensuite » stays offered WHILE a run is going, and that is
            the point rather than an oversight: new downloads land during a
            pass, and asking for another one is a legitimate thing to want. */}
        {state.pipe === "queued" ? (
          <>
            <div className={liveStrip()} data-part="live-activity">
              <span className={liveDot()}></span>
              <span>
                {t("screens.arrivals.queuedLead")}
                <b className={liveEmphasis()}>{t("screens.arrivals.queuedBold")}</b>
                {t("screens.arrivals.queuedRest")}
              </span>
            </div>
            <button className={`cfoot ${actionButton()}`} data-part="card/foot" data-pipe="stop">
              {t("screens.arrivals.stopPipeline")}
            </button>
          </>
        ) : (
          <div className={pilotActions()}>
            <button className={`cfoot ${actionButton()}`} data-part="card/foot" data-pipe="start">
              {t("screens.arrivals.runAfterwards")}
            </button>
            <button className={`cfoot ${actionButton()}`} data-part="card/foot" data-pipe="stop">
              {t("screens.arrivals.stop")}
            </button>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className={pilotBar()} data-part="pipeline" data-region="arrivals/pilot-bar">
      <div className={pilotHead()}>
        <span className={statusDotClass({ tone: "neutral" })} data-part="status-dot" data-tone="neutral"></span>
        <span className={pilotTitle()} data-part="pipeline/title">{t("screens.arrivals.idleTitle")}</span>
        <span className={pilotQualifier()}>
          {t("screens.arrivals.idleQualifier", {
            when: PIPELINE.last.when,
          })}
        </span>
      </div>
      <button className={`cfoot solid ${actionButton()}`} data-part="card/foot" data-solid="" data-pipe="start">
        {t("screens.arrivals.startPipeline")}
      </button>
    </section>
  );
}

// The last run, told as its nine steps. The counts are the ones `pipeline_run`
// recorded; nothing here is derived from what the page shows.
function LastRun(): ReactElement | null {
  const { t } = useTranslation();
  const { factRowsHTML } = useArrivalsReference();
  const { data: PIPELINE } = usePipeline();
  if (!PIPELINE) return null;
  const run = PIPELINE.last;
  return (
    <section className={sectionClass()} data-part="section">
      <div className={sectionHead()} data-part="section/head">
        <span className={statusDotClass({ tone: "success" })} data-part="status-dot" data-tone="success"></span>
        <span className={sectionTitle()} data-part="section/title">{t("screens.arrivals.lastRunTitle")}</span>
        <span className={sectionCount()} data-part="section/count">{run.duree}</span>
      </div>
      <div className={liveStrip()} data-part="live-activity">
        <span
          className={liveDot()}
          style={{ animation: "none", background: "var(--color-success)" }}
        ></span>
        <span>
          {t("screens.arrivals.triggeredBy")}
          <b className={liveEmphasis()}>{PIPELINE.declencheurs[run.declencheur]}</b>
          {t("screens.arrivals.triggeredWhen", { when: run.when })}
        </span>
      </div>
      <Markup tag="ol"
        className="flux" data-part="flux"
        html={factRowsHTML(lastRunRows(PIPELINE.steps, run.facts, t))}
      />
    </section>
  );
}

export function ArrivalsPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  const { cardHTML, secInner, emptyInner, skelCardsInner } = useArrivalsReference();
  // WHICH WORLD. The prototype carries two and the harness switches between
  // them; the key carries it, so a surface never reads the other one's cards.
  const scenario = state.scen === "loaded" ? "loaded" : "";
  // FROM THE CACHE (invariant 4). The three lists are one resource with four
  // readers; this is one of them.
  const { data: staging } = useStaging(scenario);

  if (state.phase !== "ready") {
    // Each emits ONE root element, and this draws that element itself so no
    // wrapper appears where the legacy had none.
    return state.phase === "error" ? (
      <SurfaceError subject={t("screens.arrivals.errorSubject")} />
    ) : (
      <Markup
        className={sectionClass()} data-part="section"
        html={skelCardsInner(3)}
      />
    );
  }

  const stuck = staging?.stuck ?? [];
  const moving = staging?.moving ?? [];
  const settled = staging?.settled ?? [];
  const nothing = stuck.length + moving.length + settled.length === 0;

  // A section that would be empty is not drawn at all — the outer `secHTML`
  // answered the empty string, and an empty string renders nothing.
  const section = (
    pip: string,
    title: string,
    cards: QueueCard[],
    inner: string,
    note?: string,
  ) =>
    cards.length === 0 || inner === "" ? null : (
      <Markup tag="section"
        className={sectionClass()} data-part="section"
        html={secInner(pip, title, String(cards.length), inner, note)}
      />
    );

  return (
    <>
      <div className="note" data-part="note">
        <b>{t("screens.arrivals.introLead")}</b>
        {t("screens.arrivals.introRest")}
      </div>
      <PipelineBar />
      <LastRun />
      {state.scen === "real" ? (
        <div className="note" data-part="note">
          <b>{t("screens.arrivals.realLead")}</b>
          {t("screens.arrivals.realMiddle")}
          <code>library.db</code>
          {t("screens.arrivals.realRest")}
        </div>
      ) : null}
      {moving.length > 0 ? (
        <div className={liveStrip()} data-part="live-activity">
          <span className={liveDot()}></span>
          <span>
            {t("screens.arrivals.scrapingLead")}
            {/* french-ok: a media TITLE, which is data — the same one the
                legacy named here. */}
            <b className={liveEmphasis()}>Furious</b>
            {t("screens.arrivals.scrapingRest")}
          </span>
        </div>
      ) : null}
      {nothing ? (
        <Markup
          className={emptyNote()} data-part="empty-state"
          html={emptyInner(
              t("screens.arrivals.emptyTitle"),
              t("screens.arrivals.emptyBody"),
            )}
        />
      ) : null}
      {section(
        "danger",
        t("screens.arrivals.stuckTitle"),
        stuck,
        stuck
          .map((card) =>
            cardHTML(card, {
              foot: t("screens.arrivals.stuckFoot"),
              footAct: "resolve",
            }),
          )
          .join(""),
        `<b>${t("screens.arrivals.stuckNoteLead")}</b>${t("screens.arrivals.stuckNoteRest")}`,
      )}
      {state.scen !== "real" ? (
        <button className={crossReference()} data-part="cross-reference" data-go="acq">
          {t("screens.arrivals.toAcquisition")}
          <span className={crossReferenceLink()}>{t("screens.arrivals.toAcquisitionLink")}</span>
        </button>
      ) : null}
      {section(
        "info",
        t("screens.arrivals.movingTitle"),
        moving,
        moving.map((card) => cardHTML(card)).join(""),
      )}
      {section(
        "success",
        t("screens.arrivals.settledTitle"),
        settled,
        settled.map((card) => cardHTML(card)).join(""),
      )}
    </>
  );
}
