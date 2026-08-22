// design/src/pages/system.tsx
// The first migrated PAGE: legacy `viewSystem()` (`refonte.html`) reborn as a
// final component. Markup is TRANSPLANTED, not translated — every tag, class,
// attribute and inline style below is one the fragment's BLOCK 2 CSS already
// targets, and the two `.crossref` buttons keep the `data-go` / `data-page`
// attributes the document-level delegation reads.
//
// Système answers ONE question: is the machine well? It is a pure renderer —
// it writes nothing, ever. Its only inputs are `state.phase` (the skeleton and
// error surfaces) and `state.panne` (the simulated-fault state, which no UI
// control toggles: only the harness drives it, and only through `__go`).
//
// The fact lists go through `factRowsHTML`, the fragment's own row emitter,
// reused VERBATIM — the same discipline `add.tsx` applies to `cardHTML`, and
// for the same reason: those rows carry `data-*` attributes the delegated click
// handlers read, and re-deriving the markup here would drift the one thing that
// seam depends on being byte-exact. This component draws the `<ol class="flux">`
// itself, because React cannot set the outer markup of a node it also renders.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useSystemReference } from "../../features/system/reference";
import { type Fact } from "../../lib/engine-drawing";
import { useUiState } from "../../lib/store-access";

export function SystemPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    factRowsHTML,
    skelCardsInner,
    surfErrInner,
    SERVICES,
    SERVICES_PANNE,
    SCHEDULERS,
    SCHEDULERS_DOWN,
    EXECUTIONS,
    DISKS,
    INDEX,
    DEPENDENCIES,
    ERRORS,
  } = useSystemReference();

  // The two non-ready surfaces, emitted by the fragment exactly as before. The
  // host element is the `div.body` the legacy returned, so what goes here is
  // its CONTENT.
  if (state.phase !== "ready") {
    // Each emits ONE root element, and this draws that element itself so no
    // wrapper appears where the legacy had none.
    return state.phase === "error" ? (
      <div
        className="surferr" data-part="surface-error" role="alert"
        dangerouslySetInnerHTML={{
          __html: surfErrInner(t("screens.system.errorSubject")),
        }}
      />
    ) : (
      <div
        className="sec" data-part="section"
        dangerouslySetInnerHTML={{ __html: skelCardsInner(3) }}
      />
    );
  }

  const facts = (rows: Fact[]) => (
    <ol
      className="flux" data-part="flux"
      dangerouslySetInnerHTML={{ __html: factRowsHTML(rows) }}
    />
  );

  return (
    <>
      <div className="note" data-part="note">
        <b>{t("screens.system.introLead")}</b>
        {t("screens.system.introRest")}
      </div>
      {state.fault ? (
        <div className="note" data-part="note">
          <b>{t("screens.system.faultLead")}</b>
          {t("screens.system.faultRest")}
        </div>
      ) : null}
      <h2 className="h2" data-part="heading">{t("screens.system.services")}</h2>
      {facts(state.fault ? SERVICES_PANNE : SERVICES)}

      <h2 className="h2" data-part="heading">{t("screens.system.schedulers")}</h2>
      <div className="note" data-part="note">
        <b>{t("screens.system.schedulerLead")}</b>
        {t("screens.system.schedulerRest")}
      </div>
      {facts(state.fault ? SCHEDULERS_DOWN : SCHEDULERS)}

      <h2 className="h2" data-part="heading">{t("screens.system.runs")}</h2>
      {facts(
        EXECUTIONS.map((execution) => ({
          l: execution.q,
          ton: execution.ok ? "success" : "alert",
          v: execution.ok
            ? t("screens.system.runSucceeded")
            : t("screens.system.runFailed"),
          s: execution.d + " · " + execution.r,
        })),
      )}
      <button className="crossref" data-part="cross-reference" data-go="arr">
        {t("screens.system.toArrivals")}
        <span>{t("screens.system.toArrivalsLink")}</span>
      </button>

      <h2 className="h2" data-part="heading">{t("screens.system.disks")}</h2>
      {facts(DISKS)}

      <h2 className="h2" data-part="heading">{t("screens.system.index")}</h2>
      {facts(INDEX)}
      <button className="crossref" data-part="cross-reference" data-page="maint">
        {t("screens.system.toMaintenance")}
        <span>{t("screens.system.toMaintenanceLink")}</span>
      </button>

      <h2 className="h2" data-part="heading">{t("screens.system.dependencies")}</h2>
      {facts(DEPENDENCIES)}

      <h2 className="h2" data-part="heading">{t("screens.system.codeErrors")}</h2>
      {facts([
        {
          l: t("screens.system.errorsRaised"),
          ton: "alert",
          v: t("screens.system.errorsValue"),
          s: t("screens.system.errorsDetail", {
            total: ERRORS.total,
            over: ERRORS.outOf,
            last: ERRORS.latest,
            what: ERRORS.what,
          }),
        },
        { l: t("screens.system.errorsWhere"), v: "", s: ERRORS.where },
      ])}

      <h2 className="h2" data-part="heading">{t("screens.system.settings")}</h2>
      <button className="topic" data-part="topic" data-page="cfg" style={{ marginTop: 0 }}>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span className="rt" data-part="topic/title">{t("screens.system.settings")}</span>
          <span className="rs" data-part="topic/subtitle">{t("screens.system.settingsSubtitle")}</span>
        </span>
        <span className="rn" data-part="topic/count">{t("screens.system.arrow")}</span>
      </button>
    </>
  );
}
