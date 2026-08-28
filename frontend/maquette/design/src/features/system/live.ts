// What a server event refreshes on the system page.
//
// SEVEN READS, ONE SURFACE, and the map keeps them apart for the reason the
// page keeps them apart: one « everything about the system » invalidation would
// make every event refetch seven resources, which is a reload under another
// name.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/** The schedulers, and when each next runs. */
const SCHEDULERS_KEY = ["/api/maintenance/schedulers"];
/** The disks, and what is left on them. */
const DISKS_KEY = ["/api/maintenance/disks"];
/** The index's health. */
const INDEX_HEALTH_KEY = ["/api/maintenance/index-health"];
/** Whether each external provider answers. */
const DEPENDENCIES_KEY = ["/api/system/dependencies"];
/** The services, and whether each answers. */
const SERVICES_KEY = ["/api/system/services"];
/** What the code has been complaining about. */
const ERRORS_KEY = ["/api/system/errors"];
/** The runs, and how each ended. */
const HISTORY_KEY = ["/api/pipeline/history"];

/** What a server event refreshes on the system page. */
export const systemLiveRules: readonly LiveRule[] = [
  {
    types: ["DiskFullWarning", "ItemDispatched"],
    keys: [DISKS_KEY],
    because:
      "a warning is the disks read arriving as news, and a dispatched item is "
      + "the one routine act that consumes the space it reports",
  },
  {
    types: ["WatcherRunTriggered", "PipelineStarted", "PipelineEnded",
            "BackfillStarted"],
    keys: [SCHEDULERS_KEY, HISTORY_KEY],
    because:
      "a run beginning or ending moves the next scheduled time AND appends to "
      + "the history — the two reads that are about runs rather than about "
      + "state",
  },
  {
    types: ["StepErrored", "TrackerAuthFailed", "LockedCapabilityUnresolved"],
    keys: [ERRORS_KEY],
    because:
      "an error is exactly what this read answers, and a screen that has to be "
      + "reloaded to show one is §8's own example of a lie by omission. "
      + "`LockedCapabilityUnresolved` is a capability that cannot be resolved — "
      + "a configuration failure, not progress — and it was exempted under a "
      + "sentence about per-step progress that does not describe it",
  },
  {
    types: ["CircuitBreakerOpened", "CircuitBreakerClosed",
            "CircuitBreakerHalfOpened", "ProviderCallCompleted",
            "ProviderExhaustedEvent"],
    keys: [DEPENDENCIES_KEY],
    because:
      "a breaker trips when a provider stops answering, and this read's own "
      + "second line IS the breaker state (« aucun disjoncteur ouvert »). They "
      + "fire ON TRANSITION and never per probe, which is exactly the shape a "
      + "demand was filed asking the backend to build — it already had it. "
      + "`ProviderCallCompleted` joins them and it was EXEMPTED as « per-item "
      + "progress », which its own docstring contradicts: it is throttled to "
      + "roughly one sample per ten seconds per transport and exists so the web "
      + "process can track per-provider latency and recency — the derivation "
      + "this read is built on. A provider failing UNDER the breaker's "
      + "threshold moves it and moved nothing here, so the page said "
      + "« disponibles » over a provider that was degrading. That is the same "
      + "error as the download refusal, at the other end: an event accepted "
      + "into an exemption on a reason its docstring refutes",
  },
  {
    types: ["LibraryScanCompleted", "BackfillCompleted", "RegistryBootValidated"],
    keys: [INDEX_HEALTH_KEY, SERVICES_KEY],
    because:
      "the index's health is what a scan and a backfill exist to change. "
      + "`RegistryBootValidated` fires ONCE when the boot completes, carrying "
      + "the registered providers and the capability map — it is not per-item "
      + "progress, and it is the one event that says the services have just "
      + "been established. It was exempted under a sentence about per-step "
      + "progress that is false of it",
  },
];

/** The events that reach the system page and deliberately refresh nothing. */
export const systemLiveExemptions: LiveExemptions = {
  types: [
    "BackfillItemCompleted",
    "BackfillSkipped",
    "VerifyItemDone",
    "ItemProgressed",
    "PipelinePaused",
    "PipelineResumed",
    "StepStarted",
    "StepCompleted",
    "ProviderFallbackTriggered",
    "RegistryFanOutCompleted",
    "RegistryBootValidated",
  ],
  keys: [],
  /* WHAT IS LEFT UNREFRESHED IS NOTHING, and the two sentences that used to
     sit here were both wrong. The first claimed no event says a DEPENDENCY
     stopped answering; the breakers do, and `ProviderCallCompleted` samples it
     between transitions. The second kept `/api/system/services` unrefreshable;
     `RegistryBootValidated` says the services have just been established, and
     it is mapped above. `CircuitBreakerOpened/Closed/
     HalfOpened` exist, fire on transition, and are a rule above. What remains
     unclaimed is process liveness: nothing is emitted when a service itself
     stops answering. Filed as a demand rather than papered over with a clock —
     a poll here would satisfy the letter of the page and break this lot's third
     clause. */
  because:
    "every one of them is per-item or per-step progress, and this page reads "
    + "state rather than progress. `BackfillItemCompleted` in particular fires "
    + "once per item of a backfill that walks the whole library — mapping it to "
    + "the index's health would refetch that read thousands of times for one "
    + "number that moves once, at the end (`BackfillCompleted`, above)",
};
