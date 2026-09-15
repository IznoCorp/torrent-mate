// design/src/pages/system.tsx
// The first migrated PAGE: legacy `viewSystem()` (`refonte.html@60530dbd8`) reborn as a
// final component. Markup is TRANSPLANTED, not translated — every tag, class,
// attribute and inline style below is one the fragment's BLOCK 2 CSS already
// targets, and the two `.crossref` buttons keep the `data-go` / `data-page`
// attributes the document-level delegation reads.
//
// Système answers ONE question: is the machine well? It READS to answer it —
// the services, the schedulers, what holds the pipeline, the passages — and the
// « Le pipeline » section is where what governs ALL media at once is read and,
// as its levers land, set. Its own inputs stay `state.phase` (the skeleton and
// error surfaces) and `state.panne` (the simulated-fault state, which no UI
// control toggles: only the harness drives it, and only through `__go`).
//
// The fact lists are `FactRows`, inside the `<ol class="flux">` this component
// draws. A row that leads somewhere carries the `data-*` attributes its
// descriptor names, which are what the delegated click handlers read.
import { useTranslation } from "react-i18next";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import type { ReactElement } from "react";
import { PipelinePanel } from "./pipeline-panel";
import { RunList } from "./run-list";
import { useSchedulersDown, useServicesDown } from "./fault";
import { useUiState } from "../../lib/store-access";
import {
  useDependencies,
  useDisks,
  useIndexHealth,
  useSchedulers,
  useServices,
  useSystemErrors,
} from "./queries";
import { crossReference, crossReferenceLink, factList, section, sectionHeading, topicRow } from "../../ui/variants";
import { guidance } from "../../ui/variants/layout";
import { Markup } from "../../ui/markup";
import { FactRows, type FactRow } from "../../ui/fact-rows";

export function SystemPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  // FROM THE CACHE (invariant 4). Both fault variants are derived here from
  // what the layer sent (`./fault`): the healthy lists are its answer, and the
  // simulated fault is the interface's own replay of them.
  const { data: SERVICES = [] } = useServices();
  const SERVICES_DOWN = useServicesDown(SERVICES);
  const { data: SCHEDULERS = [] } = useSchedulers();
  const SCHEDULERS_DOWN = useSchedulersDown(SCHEDULERS);
  const { data: DISKS = [] } = useDisks();
  const { data: INDEX = [] } = useIndexHealth();
  const { data: DEPENDENCIES = [] } = useDependencies();
  // The errors are an OBJECT, not a list, so the empty case is the shape
  // rather than an empty array — and it is stated here rather than left to a
  // question mark at each of its five readers.
  const { data: ERRORS = { total: 0, outOf: 0, latest: "", what: "", where: "" } } =
    useSystemErrors();

  // The two non-ready surfaces, emitted by the fragment exactly as before. The
  // host element is the `div.body` the legacy returned, so what goes here is
  // its CONTENT.
  if (state.phase !== "ready") {
    // Each emits ONE root element, and this draws that element itself so no
    // wrapper appears where the legacy had none.
    return state.phase === "error" ? (
      <SurfaceError subject={t("screens.system.errorSubject")} />
    ) : (
      <div className={section()} data-part="section"><Skeletons count={3} shape="card" /></div>
    );
  }

  const facts = (rows: FactRow[]) => (
    <ol className={factList()} data-part="flux">
      <FactRows rows={rows} />
    </ol>
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
      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.services")}</h2>
      {facts(state.fault ? SERVICES_DOWN : SERVICES)}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.schedulers")}</h2>
      <div className={guidance()} data-part="guidance">
        <b>{t("screens.system.schedulerLead")}</b>
        {t("screens.system.schedulerRest")}
      </div>
      {facts(state.fault ? SCHEDULERS_DOWN : SCHEDULERS)}

      <PipelinePanel />

      <RunList />

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.disks")}</h2>
      {facts(DISKS)}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.index")}</h2>
      {facts(INDEX)}
      <button className={crossReference()} data-part="cross-reference" data-page="maint">
        {t("screens.system.toMaintenance")}
        <span className={crossReferenceLink()}>{t("screens.system.toMaintenanceLink")}</span>
      </button>

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.dependencies")}</h2>
      {facts(DEPENDENCIES)}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.codeErrors")}</h2>
      {facts([
        {
          label: t("screens.system.errorsRaised"),
          tone: "alert",
          value: t("screens.system.errorsValue"),
          secondaryLine: t("screens.system.errorsDetail", {
            total: ERRORS.total,
            over: ERRORS.outOf,
            last: ERRORS.latest,
            what: ERRORS.what,
          }),
        },
        { label: t("screens.system.errorsWhere"), value: "", secondaryLine: ERRORS.where },
      ])}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.settings")}</h2>
      <button className={topicRow()} data-part="topic" data-page="cfg" style={{ marginTop: 0 }}>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span className="rt" data-part="topic/title">{t("screens.system.settings")}</span>
          <span className="rs" data-part="topic/subtitle">{t("screens.system.settingsSubtitle")}</span>
        </span>
        <span className="rn" data-part="topic/count">{t("screens.system.arrow")}</span>
      </button>
    </>
  );
}
