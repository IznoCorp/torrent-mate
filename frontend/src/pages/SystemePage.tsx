/**
 * SystemePage — the /systeme hub with 4 URL-addressable tabs.
 *
 * Mirrors the AcquisitionPage tab pattern (``TAB_IDS`` array validated against
 * ``?tab=`` from ``useSearchParams``, ``setActiveTab`` pushing/clearing the
 * param, segmented-control tablist). Redistributes every existing maintenance
 * and registry panel into four tabs — zero panel rewrites, only the page shell
 * is new.
 *
 * Tabs:
 * - **État** (default, clean URL): DisksPanel + LocksPanel + IndexHealthPanel
 *   + providers (ex-RegistryPage cards, inlined) + EventFeed + RecentEventsTable.
 * - **Actions**: ActionCatalog (ex-Maintenance, kept as-is).
 * - **Exécutions de maintenance**: RunHistoryTable kind="maintenance" +
 *   TriggerLegend + ``&run=`` RunDetail drawer scoped to this tab.
 * - **Journal**: DestructiveLogPanel (§7 home).
 *
 * The RunDetail drawer on the maintenance tab follows the same openRun/closeRun
 * URL pattern as /pipeline (DOIT-10 — preserving other params).
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";

import { registryKeys } from "@/api/registry";
import {
  groupProviders,
  subCircuitHint,
  subCircuitLabel,
} from "@/components/registry/groupProviders";
import { EventFeed } from "@/components/dashboard/EventFeed";
import { RecentEventsTable } from "@/components/dashboard/RecentEventsTable";
import { ActionCatalog } from "@/components/maintenance/ActionCatalog";
import { DestructiveLogPanel } from "@/components/maintenance/DestructiveLogPanel";
import { DisksPanel } from "@/components/maintenance/DisksPanel";
import { IndexHealthPanel } from "@/components/maintenance/IndexHealthPanel";
import { LocksPanel } from "@/components/maintenance/LocksPanel";
import { RunDetail } from "@/components/pipeline/RunDetail";
import { RunHistoryTable } from "@/components/pipeline/RunHistoryTable";
import { TriggerLegend } from "@/components/pipeline/TriggerLegend";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { useRegistryStatus } from "@/hooks/useRegistryStatus";
import { relativeTime } from "@/lib/format";

// ---------------------------------------------------------------------------
// Tab model
// ---------------------------------------------------------------------------

/**
 * Known tab identifiers (``"maintenance"`` = the Exécutions de maintenance
 * history tab — not the old /maintenance page, which now redirects here).
 */
const TAB_IDS = ["etat", "actions", "maintenance", "journal"] as const;
type TabId = (typeof TAB_IDS)[number];

/** Default tab shown when no ``?tab=`` param is present (clean URL). */
const DEFAULT_TAB: TabId = "etat";

/** Tab definitions — id + French label. */
const TABS: readonly { id: TabId; label: string }[] = [
  { id: "etat", label: "État" },
  { id: "actions", label: "Actions" },
  { id: "maintenance", label: "Exécutions de maintenance" },
  { id: "journal", label: "Journal" },
];

// ---------------------------------------------------------------------------
// Provider section constants (ex-RegistryPage)
// ---------------------------------------------------------------------------

/** Event class names the provider section listens for live invalidation. */
const REGISTRY_EVENT_TYPES = new Set([
  "CircuitBreakerOpened",
  "CircuitBreakerClosed",
  "CircuitBreakerHalfOpened",
  "RegistryFanOutCompleted",
]);

/** Circuit-state → badge tone mapping. */
const CIRCUIT_TONE: Record<string, "success" | "danger" | "warning"> = {
  closed: "success",
  open: "danger",
  half_open: "warning",
};

/** Circuit-state → French label. */
const CIRCUIT_LABEL: Record<string, string> = {
  closed: "OK",
  open: "Ouvert",
  half_open: "Semi-ouvert",
};

// ---------------------------------------------------------------------------
// ProvidersPanel — provider health cards (ex-RegistryPage, inlined as a tab
// panel so the page component has no external dependency on RegistryPage).
// ---------------------------------------------------------------------------

/**
 * ProvidersPanel — provider health cards, formerly the ``/registry`` page.
 *
 * Fetches the live registry status via {@link useRegistryStatus} and renders
 * one card per provider group with circuit-breaker badges, recent-failure
 * count, last success/failure timestamps, and last call latency.  Live events
 * on the WebSocket invalidate the snapshot (AppShell R13 ref pattern — only
 * new events are scanned).
 *
 * Returns:
 *   The provider-cards element, or a loading/error/empty fallback.
 */
function ProvidersPanel(): ReactElement {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useRegistryStatus();
  const { events } = useEventStreamContext();

  // Invalidate the snapshot on any registry/circuit event, scanning only
  // events appended since the last render — not the whole ring every time
  // (AppShell R13 ref pattern, coherence study F13).
  const lastProcessedRef = useRef(0);
  useEffect(() => {
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;
    const hasRegistryEvent = fresh.some((e) =>
      REGISTRY_EVENT_TYPES.has(e.type),
    );
    if (hasRegistryEvent) {
      void queryClient.invalidateQueries({ queryKey: registryKeys.status() });
    }
  }, [events, queryClient]);

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Fournisseurs</h2>
        {Array.from({ length: 3 }).map((_, idx) => (
          <Skeleton key={`sk-${String(idx)}`} className="h-28 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Fournisseurs</h2>
        <p className="text-xs text-muted-foreground">
          Impossible de charger le statut :{" "}
          {error instanceof Error ? error.message : "Erreur inconnue"}
        </p>
      </div>
    );
  }

  const { providers } = data;

  // ── Empty state ────────────────────────────────────────────────────────
  if (providers.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Fournisseurs</h2>
        <p className="text-xs text-muted-foreground">
          Aucun fournisseur configuré.
        </p>
      </div>
    );
  }

  // ── Normal render ──────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold tracking-tight">Fournisseurs</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {groupProviders(providers).map(({ parent: p, subs }) => (
          <Card
            key={p.provider_name}
            className={!p.live ? "opacity-60" : undefined}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="font-mono text-lg">
                {p.provider_name}
              </CardTitle>
              <Badge tone={CIRCUIT_TONE[p.circuit_state]}>
                {CIRCUIT_LABEL[p.circuit_state] ?? p.circuit_state}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              {!p.live && (
                <p className="text-muted-foreground">
                  En attente de données live
                </p>
              )}
              <p>
                Échecs récents :{" "}
                <span className="font-mono tabular-nums">
                  {p.failure_count_recent}
                </span>
              </p>
              <p>Dernier succès : {relativeTime(p.last_success_at)}</p>
              <p>Dernier échec : {relativeTime(p.last_failure_at)}</p>
              <p>
                Latence :{" "}
                <span className="font-mono tabular-nums">
                  {p.last_latency_ms != null
                    ? `${p.last_latency_ms.toFixed(0)} ms`
                    : "—"}
                </span>
              </p>

              {subs.length > 0 && (
                <div className="mt-2 space-y-1 border-t border-border pt-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    Sous-circuits
                  </p>
                  {subs.map((s) => (
                    <div
                      key={s.provider_name}
                      className="flex flex-col gap-0.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs">
                          {subCircuitLabel(s.provider_name)}
                          {s.last_latency_ms != null && (
                            <span className="ml-1 font-mono tabular-nums text-muted-foreground">
                              · {s.last_latency_ms.toFixed(0)} ms
                            </span>
                          )}
                        </span>
                        <Badge tone={CIRCUIT_TONE[s.circuit_state]}>
                          {CIRCUIT_LABEL[s.circuit_state] ?? s.circuit_state}
                        </Badge>
                      </div>
                      {/* Rationale visible on all devices (not just hover) so
                          touch users learn what the sub-circuit is (REGISTRY-4). */}
                      <p className="text-xs text-muted-foreground">
                        {subCircuitHint(s.provider_name)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * SystemePage — the authenticated system hub route (``/systeme``).
 *
 * Four tabbed panels for system health (état), maintenance actions,
 * maintenance run history, and the destructive-operations journal.  The
 * active tab is URL-addressable via ``?tab=<id>`` — DOIT-10: the tab is a
 * shareable deep-link and Back returns to the previous tab.  The default
 * ``etat`` tab carries no param so ``/systeme`` stays clean.
 *
 * Returns:
 *   The system hub page element.
 */
export default function SystemePage(): ReactElement {
  const [searchParams, setSearchParams] = useSearchParams();

  // Derive the active tab from the URL (single source of truth). Unknown
  // values fall back to the default etat tab — no error screen for a bad
  // query param.
  const rawTab = searchParams.get("tab");
  const activeTab: TabId = TAB_IDS.includes(rawTab as TabId)
    ? (rawTab as TabId)
    : DEFAULT_TAB;

  /** Push or clear the ``?tab=`` param. The default tab carries no param. */
  const setActiveTab = useCallback(
    (id: TabId) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id === DEFAULT_TAB) next.delete("tab");
          else next.set("tab", id);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  // Single shared live-event stream (same WebSocket the TopBar StatusDot
  // reads); the feed + recent-events table in the état tab read from it.
  const { events } = useEventStreamContext();

  // Run-detail selection is URL-addressable (?run=<uid>) on the maintenance
  // tab — same openRun/closeRun pattern as /pipeline, preserving other params.
  const selectedRun = searchParams.get("run");
  const openRun = useCallback(
    (uid: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("run", uid);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );
  const closeRun = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("run");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Système</h1>

      {/* Tabs — horizontal scroll on narrow screens (4 tabs at ~390px: no wrap,
          natural width per tab, scroll inside the tablist). On sm+ tabs fill
          the row evenly (flex-1). E5 segmented control. */}
      <div
        role="tablist"
        className="flex flex-nowrap gap-1 overflow-x-auto rounded-lg bg-muted p-1"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => {
              setActiveTab(tab.id);
            }}
            className={`whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors sm:flex-1 ${
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active panel — each tab renders its own Cards directly (H1: max 3
          surface levels — page → Card panel → row). No outer Card wrapper. */}
      {/* État — system health at a glance: disks, locks, index, providers,
          and the live event stream. */}
      {activeTab === "etat" && (
        <div className="flex flex-col gap-6">
          {/* Monitoring panels: 1 col mobile → 2 tablet → 3 desktop. */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            <DisksPanel />
            <LocksPanel />
            <IndexHealthPanel />
          </div>

          {/* Provider health cards — ex-RegistryPage. */}
          <ProvidersPanel />

          {/* Live event feed + recent-events table (formerly on the
              /maintenance page; relocated to /systeme?tab=etat). */}
          <EventFeed events={events} />
          <RecentEventsTable events={events} />
        </div>
      )}

      {/* Actions — maintenance command catalog with generated run forms
          (ActionCatalog is rendered as-is, zero changes). */}
      {activeTab === "actions" && <ActionCatalog />}

      {/* Exécutions de maintenance (F1 — the second history table,
          renamed). The trigger legend is carried here so labels stay
          decodable (C2). Clicking a row sets ?run=<uid>; when set, the
          RunDetail drawer renders inline below the table. */}
      {activeTab === "maintenance" && (
        <div className="flex flex-col gap-4">
          <RunHistoryTable
            kind="maintenance"
            onSelect={openRun}
            legend={<TriggerLegend />}
          />

          {selectedRun !== null && (
            <RunDetail runUid={selectedRun} onClose={closeRun} />
          )}
        </div>
      )}

      {/* Journal — the append-only destructive-operations trail (§7).
          Gets its addressable home here, linked directly via
          /systeme?tab=journal. */}
      {activeTab === "journal" && <DestructiveLogPanel />}
    </section>
  );
}
