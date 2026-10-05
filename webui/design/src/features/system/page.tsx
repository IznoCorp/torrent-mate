// design/src/features/system/page.tsx
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
// error surfaces) and `state.fault` (the simulated-fault state, which no UI
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
import { crossReference, crossReferenceLink, factList, section, sectionHeading } from "../../ui/variants";
import { guidance } from "../../ui/variants/layout";
import { Markup } from "../../ui/markup";
import { FactRows } from "../../ui/fact-rows";
import { TopicRow } from "../../ui/topic-row";
import { factRow } from "./state-words";
import type { Schemas } from "../../lib/contract-schemas";

type Fact = Schemas["Fact"];

export function SystemPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  // FROM THE CACHE (invariant 4). Both fault variants are derived here from
  // what the layer sent (`./fault`): the healthy lists are its answer, and the
  // simulated fault is the interface's own replay of them.
  const services = useServices();
  const SERVICES = services.data ?? [];
  const SERVICES_DOWN = useServicesDown(SERVICES);
  const { data: SCHEDULERS = [], error: schedulersError } = useSchedulers();
  const SCHEDULERS_DOWN = useSchedulersDown(SCHEDULERS);
  const disks = useDisks();
  const index = useIndexHealth();
  const dependencies = useDependencies();
  // The errors are an OBJECT, not a list, so the empty case is the shape
  // rather than an empty array — and it is stated here rather than left to a
  // question mark at each of its five readers.
  const { data: ERRORS = { total: 0, outOf: 0, latest: "", what: "", where: "" }, error: errorsError } =
    useSystemErrors();
  // WHY THE PAGE FAILED is the first of its six reads that a server refused: the surface names one
  // reason, and the readers of the others are no less wrong to say a timeout.
  const failure =
    services.error ?? schedulersError ?? disks.error ?? index.error ?? dependencies.error ?? errorsError ?? undefined;

  // The two non-ready surfaces, emitted by the fragment exactly as before. The
  // host element is the `div.body` the legacy returned, so what goes here is
  // its CONTENT.
  if (state.phase !== "ready") {
    // Each emits ONE root element, and this draws that element itself so no
    // wrapper appears where the legacy had none.
    return state.phase === "error" ? (
      <SurfaceError subject={t("screens.system.errorSubject")} failure={failure} />
    ) : (
      <div className={section()} data-part="section"><Skeletons count={3} shape="card" /></div>
    );
  }

  const facts = (rows: Fact[]) => (
    <ol className={factList()} data-part="flux">
      <FactRows rows={rows.map((fact) => factRow(fact, t))} />
    </ol>
  );
  // A SECTION WHOSE OWN READ FAILED SAYS SO, in its place, while the others
  // stay drawn (L24 S2). Defaulting the answer to `[]` drew the heading over
  // nothing: « rien ne se passe » without a reason, which § 8 forbids.
  const factsOf = (read: { data?: Fact[]; isError: boolean }, section: string) =>
    facts(
      read.isError
        ? [{
            label: t("screens.system.unavailableLabel"),
            tone: "alert",
            value: t("screens.system.unavailable"),
            secondaryLine: t(`screens.system.unavailableLine.${section}`),
          }]
        : read.data ?? [],
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
      {state.fault ? facts(SERVICES_DOWN) : factsOf(services, "services")}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.schedulers")}</h2>
      <div className={guidance()} data-part="guidance">
        <b>{t("screens.system.schedulerLead")}</b>
        {t("screens.system.schedulerRest")}
      </div>
      {facts(state.fault ? SCHEDULERS_DOWN : SCHEDULERS)}

      <PipelinePanel />

      <RunList />

      {/* A SECTION A DOOR LANDS ON is named and takes the focus (`./landing`). */}
      <h2 className={sectionHeading()} data-part="heading" data-section="disks" tabIndex={-1}>{t("screens.system.disks")}</h2>
      {factsOf(disks, "disks")}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.index")}</h2>
      {factsOf(index, "index")}
      <button className={crossReference()} data-part="cross-reference" data-page="maint">
        {t("screens.system.toMaintenance")}
        <span className={crossReferenceLink()}>{t("screens.system.toMaintenanceLink")}</span>
      </button>

      <h2 className={sectionHeading()} data-part="heading" data-section="dependencies" tabIndex={-1}>
        {t("screens.system.dependencies")}
      </h2>
      {factsOf(dependencies, "dependencies")}

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
      <TopicRow
        title={t("screens.system.settings")}
        subtitle={t("screens.system.settingsSubtitle")}
        value={t("screens.system.arrow")}
        target={{ "data-page": "cfg" }}
      />
    </>
  );
}
