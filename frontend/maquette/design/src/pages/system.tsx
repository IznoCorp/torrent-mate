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
import type { Fact } from "../data";
import { useReference, useUiState } from "../data";

export function SystemPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    factRowsHTML,
    skelCardsInner,
    surfErrInner,
    SERVICES,
    SERVICES_PANNE,
    PLANIFICATEURS,
    PLANIFICATEURS_PANNE,
    EXECUTIONS,
    DISQUES,
    INDEX,
    DEPENDANCES,
    ERREURS,
  } = useReference();

  // The two non-ready surfaces, emitted by the fragment exactly as before. The
  // host element is the `div.body` the legacy returned, so what goes here is
  // its CONTENT.
  if (state.phase !== "prete") {
    // Each emits ONE root element, and this draws that element itself so no
    // wrapper appears where the legacy had none.
    return state.phase === "erreur" ? (
      <div
        className="surferr"
        dangerouslySetInnerHTML={{
          __html: surfErrInner(t("screens.system.errorSubject")),
        }}
      />
    ) : (
      <div
        className="sec"
        dangerouslySetInnerHTML={{ __html: skelCardsInner(3) }}
      />
    );
  }

  const facts = (rows: Fact[]) => (
    <ol
      className="flux"
      dangerouslySetInnerHTML={{ __html: factRowsHTML(rows) }}
    />
  );

  return (
    <>
      <div className="note">
        <b>{t("screens.system.introLead")}</b>
        {t("screens.system.introRest")}
      </div>
      {state.panne ? (
        <div className="note">
          <b>{t("screens.system.faultLead")}</b>
          {t("screens.system.faultRest")}
        </div>
      ) : null}
      <h2 className="h2">{t("screens.system.services")}</h2>
      {facts(state.panne ? SERVICES_PANNE : SERVICES)}

      <h2 className="h2">{t("screens.system.schedulers")}</h2>
      <div className="note">
        <b>{t("screens.system.schedulerLead")}</b>
        {t("screens.system.schedulerRest")}
      </div>
      {facts(state.panne ? PLANIFICATEURS_PANNE : PLANIFICATEURS)}

      <h2 className="h2">{t("screens.system.runs")}</h2>
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
      <button className="crossref" data-go="arr">
        {t("screens.system.toArrivals")}
        <span>{t("screens.system.toArrivalsLink")}</span>
      </button>

      <h2 className="h2">{t("screens.system.disks")}</h2>
      {facts(DISQUES)}

      <h2 className="h2">{t("screens.system.index")}</h2>
      {facts(INDEX)}
      <button className="crossref" data-page="maint">
        {t("screens.system.toMaintenance")}
        <span>{t("screens.system.toMaintenanceLink")}</span>
      </button>

      <h2 className="h2">{t("screens.system.dependencies")}</h2>
      {facts(DEPENDANCES)}

      <h2 className="h2">{t("screens.system.codeErrors")}</h2>
      {facts([
        {
          l: t("screens.system.errorsRaised"),
          ton: "alert",
          v: t("screens.system.errorsValue"),
          s: t("screens.system.errorsDetail", {
            total: ERREURS.total,
            over: ERREURS.sur,
            last: ERREURS.derniere,
            what: ERREURS.quoi,
          }),
        },
        { l: t("screens.system.errorsWhere"), v: "", s: ERREURS.ou },
      ])}

      <h2 className="h2">{t("screens.system.settings")}</h2>
      <button className="topic" data-page="cfg" style={{ marginTop: 0 }}>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span className="rt">{t("screens.system.settings")}</span>
          <span className="rs">{t("screens.system.settingsSubtitle")}</span>
        </span>
        <span className="rn">{t("screens.system.arrow")}</span>
      </button>
    </>
  );
}
