/**
 * Acquisition page — two views, legacy redirects, live-event invalidation.
 *
 * Two panels — Maintenant and Suivis — replacing the former seven tabs (spec
 * §3). The active view is URL-addressable via ``?tab=<id>`` (DOIT-10); the
 * default ``maintenant`` carries no param so ``/acquisition`` stays clean.
 * Legacy ``?tab=`` values are redirected through {@link LEGACY_TAB_REDIRECTS}
 * with ``{ replace: true }`` so an old deep link does not stack history.
 *
 * Live updates: the acquisition event stream (via useEventStreamContext)
 * invalidates the matching query when a relevant event arrives, using the R13
 * new-events-only ref pattern.
 */

import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactElement,
} from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { acqKeys } from "@/api/acquisition";
import { AddMediaScreen } from "@/components/acquisition/AddMediaScreen";
import {
  PULL_THRESHOLD_PX,
  lockAxis,
  shouldRefresh,
  shouldStartViewSwipe,
  viewSwipeResult,
} from "@/components/acquisition/gestures";
import { MaintenantPanel } from "@/components/acquisition/MaintenantPanel";
import {
  ACQ_EVENT_TYPES,
  FULL_INVALIDATE_EVENTS,
  LEGACY_TAB_REDIRECTS,
  OBLIGATION_INVALIDATE_EVENTS,
  TABS,
  WANTED_INVALIDATE_EVENTS,
  type TabId,
} from "@/components/acquisition/meta";
import { PlusSheet } from "@/components/acquisition/PlusSheet";
import { SuivisPanel } from "@/components/acquisition/SuivisPanel";
import { aboveBottomBar } from "@/components/layout/bottom-bar-metrics";
import { useWaitingForOperator } from "@/hooks/useAcquisition";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { handleTablistKeyDown } from "@/lib/tablist";

/**
 * AcquisitionPage — the authenticated acquisition route (``/acquisition``).
 *
 * Two views — Maintenant (default, no param) and Suivis (``?tab=suivis``) —
 * each answering one of the operator's questions. Legacy ``?tab=`` values
 * are redirected to the view that now answers them. Live events from the
 * WebSocket invalidate the matching TanStack Query caches (R13 — processes
 * only new events, not the whole ring on every render).
 *
 * Returns:
 *   The acquisition page element.
 */
export default function AcquisitionPage(): ReactElement {
  // The active tab is URL-addressable (?tab=<id>) — DOIT-10: the tab is a
  // shareable deep-link and Back returns to the previous tab. Derived from the
  // URL (single source of truth); the default "maintenant" carries no param so
  // /acquisition stays clean and ?tab=suivis is the shareable form.
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const waiting = useWaitingForOperator();
  const rawTab = searchParams.get("tab");

  // Redirect legacy ?tab= values to the view that now answers them. Replace so
  // Back doesn't cycle through the redirect — DOIT-10 deep-link survives.
  useEffect(() => {
    if (rawTab === null) return;
    // The ranking editor did not dissolve into a view — it MOVED to /config.
    // Redirecting its deep link to « maintenant » landed the operator on the
    // wrong page with no pointer to the new home.
    if (rawTab === "reglages") {
      void navigate("/config?tab=classement", { replace: true });
      return;
    }
    const target = LEGACY_TAB_REDIRECTS[rawTab];
    if (target === undefined) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (target === "maintenant") {
          next.delete("tab");
        } else {
          next.set("tab", target);
        }
        return next;
      },
      { replace: true },
    );
  }, [rawTab, setSearchParams, navigate]);

  const activeTab: TabId = TABS.some((t) => t.id === rawTab)
    ? (rawTab as TabId)
    : "maintenant";
  // ACQUISITION-7 (ticket 250): keyboard-driven activation (arrows follow
  // focus) REPLACES the current history entry — holding ArrowRight must not
  // stack one entry per keystroke. Click activation keeps push (D3
  // addressable URLs: Back returns to the previous tab).
  const setActiveTab = useCallback(
    (id: TabId, viaKeyboard = false) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id === "maintenant") next.delete("tab");
          else next.set("tab", id);
          return next;
        },
        { replace: viaKeyboard },
      );
    },
    [setSearchParams],
  );

  // ── Touch gestures ────────────────────────────────────────────────────
  //
  // Two horizontal gestures compete for one surface. Arbitration: a drag that
  // STARTS on a card belongs to the card; anywhere else it changes view. The
  // consequence is accepted, not hidden — in card-dense areas, changing view
  // will mostly happen through the tabs. Only a thumb on a real device can say
  // whether that trade is right; the tabs remain the guaranteed path either way.
  const pagerRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    x: number;
    y: number;
    axis: "x" | "y" | null;
    atTop: boolean;
  } | null>(null);
  const [pullDistance, setPullDistance] = useState(0);
  const queryClientForPull = useQueryClient();

  const onPointerDown = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const pager = pagerRef.current;
    if (pager == null) return;
    // A mouse drag is text selection, not a view gesture: on desktop the tabs
    // are one click away and a selection sweep must not change the view.
    if (e.pointerType === "mouse") return;
    // A gesture born inside a card is the card's; it says so with data-swipe.
    if ((e.target as HTMLElement).closest("[data-swipe]") != null) return;
    if (!shouldStartViewSwipe(e.clientX, pager.getBoundingClientRect().left)) {
      return;
    }
    dragRef.current = {
      x: e.clientX,
      y: e.clientY,
      axis: null,
      atTop: window.scrollY <= 0,
    };
  }, []);

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (drag == null) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.axis ??= lockAxis(dx, dy);
    if (drag.axis === "y" && drag.atTop && dy > 0) {
      setPullDistance(dy);
    }
  }, []);

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      dragRef.current = null;
      setPullDistance(0);
      if (drag == null) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;

      if (drag.axis === "x") {
        const width = pagerRef.current?.getBoundingClientRect().width ?? 0;
        const next = viewSwipeResult(dx, width, activeTab);
        if (next !== activeTab) setActiveTab(next);
        return;
      }
      if (shouldRefresh(dy, drag.atTop)) {
        void queryClientForPull.invalidateQueries({ queryKey: acqKeys.all });
      }
    },
    [activeTab, setActiveTab, queryClientForPull],
  );
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  // ── Sheet state ─────────────────────────────────────────────────────────

  // « ?add=1 » IS the open state (DOIT-10): opening pushes a history entry,
  // so the browser back button and the phone's back gesture close the screen,
  // and a « Voir la fiche » navigation away then back RESTORES the search —
  // query included (the screen reads ?q=). A useState here was the regression:
  // back from the fiche landed on the page with the search silently gone.
  const location = useLocation();
  const addOpen = searchParams.has("add");
  const openAdd = (): void => {
    const next = new URLSearchParams(searchParams);
    next.set("add", "1");
    void navigate(`?${next.toString()}`, { state: { addPushed: true } });
  };
  const closeAdd = (): void => {
    // Pushed by us → pop the entry; deep-linked → replace, there is no entry.
    if ((location.state as { addPushed?: boolean } | null)?.addPushed === true) {
      void navigate(-1);
    } else {
      const next = new URLSearchParams(searchParams);
      next.delete("add");
      next.delete("q");
      void navigate(`?${next.toString()}`, { replace: true });
    }
  };
  const [plusOpen, setPlusOpen] = useState(false);

  // Only invalidate on fresh events, not re-scanning the ring every render
  // (AppShell R13 ref pattern, coherence study F13).
  const lastProcessedRef = useRef(0);
  useEffect(() => {
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;

    for (const msg of fresh) {
      if (!ACQ_EVENT_TYPES.has(msg.type)) continue;

      // reswitch (ticket 342) — tell the operator WHY an « en cours » item just
      // went back to searching (a dead/blocked release was swapped). The wanted
      // invalidation below still runs so the card refreshes.
      if (msg.type === "GrabReswitched") {
        toast.info("Source bloquée — bascule vers une autre release.");
      }

      if (FULL_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({ queryKey: acqKeys.all });
        continue;
      }
      if (WANTED_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({ queryKey: acqKeys.wanted({}) });
        void queryClient.invalidateQueries({ queryKey: acqKeys.followed({}) });
        continue;
      }
      if (OBLIGATION_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({
          queryKey: acqKeys.obligations({}),
        });
        continue;
      }
      if (msg.type === "WatcherRunTriggered") {
        void queryClient.invalidateQueries({ queryKey: acqKeys.status() });
      }
    }
  }, [events, queryClient]);

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      {/* Tabs — two views. E5 segmented control.
          ACQUISITION-7 (ticket 250): full WAI-ARIA tablist wiring — roving
          tabIndex + arrow-key navigation + tab/panel linkage. */}
      <div
        role="tablist"
        aria-label="Vues de la page Acquisition"
        className="flex flex-nowrap gap-1 overflow-x-auto rounded-lg bg-muted p-1"
        onKeyDown={(e) => {
          handleTablistKeyDown(
            e,
            TABS.map((t) => t.id),
            activeTab,
            (id) => {
              setActiveTab(id, true);
            },
            (id) => `acq-tab-${id}`,
          );
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            id={`acq-tab-${tab.id}`}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls="acq-tabpanel"
            tabIndex={activeTab === tab.id ? 0 : -1}
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
            {/* §3.2 — the badge counts WHAT AWAITS THE OPERATOR, same
                derivation as the nav badge (§13). « ? » when unknowable. */}
            {tab.id === "maintenant" && (waiting.unknown || waiting.count > 0) && (
              <span
                data-testid="tab-maintenant-badge"
                className="ml-1.5 inline-flex h-[1.125rem] min-w-[1.125rem] items-center justify-center rounded-full bg-warning px-1 text-[0.6875rem] font-semibold leading-none text-warning-foreground"
                aria-label={
                  waiting.unknown
                    ? "Compteur indisponible"
                    : `${String(waiting.count)} élément(s) à traiter`
                }
              >
                {waiting.unknown ? "?" : String(waiting.count)}
              </span>
            )}
          </button>
        ))}
        {/* « ⋮ » — second rank, AT THE END OF THE TAB TRAIN (maquette): a
            full-width « Plus » button at page bottom was reading as a primary
            action, which Veille/Obligations are precisely not. */}
        <button
          type="button"
          aria-label="Plus — veille et obligations"
          className="ml-auto shrink-0 rounded-md px-3 py-2 text-lg leading-none text-muted-foreground hover:text-foreground"
          onClick={() => {
            setPlusOpen(true);
          }}
        >
          ⋮
        </button>
      </div>

      {/* Active panel. */}
      <div
        ref={pagerRef}
        id="acq-tabpanel"
        role="tabpanel"
        aria-labelledby={`acq-tab-${activeTab}`}
        // stops the browser's OWN pull-to-refresh from
        // reloading the page: a full reload loses the view, the filters and the
        // display mode, which is the opposite of what the pull asked for.
        className="flex touch-pan-y flex-col gap-4 pt-1"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {/* The live region is ALWAYS mounted with conditional content: a
            region that mounts on first use announces nothing the first time —
            assistive tech only reports changes inside an existing region. */}
        <p
          data-testid="pull-indicator"
          aria-live="polite"
          className={
            pullDistance > 0
              ? "text-center text-xs text-muted-foreground"
              : "sr-only"
          }
        >
          {pullDistance > 0
            ? pullDistance >= PULL_THRESHOLD_PX
              ? "Relâchez pour actualiser"
              : "Tirez pour actualiser"
            : ""}
        </p>
        {activeTab === "maintenant" && <MaintenantPanel />}
        {activeTab === "suivis" && (
          <SuivisPanel
            onAddMedia={() => {
              openAdd();
            }}
          />
        )}
      </div>

      {/* ── « Plus » : Veille et Obligations ─────────────────────────── */}

      <PlusSheet open={plusOpen} onOpenChange={setPlusOpen} />

      {/* ── « + » : add-by-search + add-by-ID (§7) ────────────────────── */}

      {/* Anchored above the bottom bar by its real measured height rather than
          a hardcoded offset — the original defect (§10). z-30 sits below every
          Sheet / Dialog / BottomTabBar (z-50) so the button does not show
          through an open full-screen surface. The 0px fallback is load-bearing:
          this bar is md:hidden; on desktop the button floats at gap alone. */}
      <button
        type="button"
        className="fixed right-4 z-30 flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90"
        style={{ bottom: aboveBottomBar("1rem") }}
        aria-label="Ajouter un média"
        onClick={() => {
          openAdd();
        }}
      >
        <Plus className="size-6" aria-hidden="true" />
      </button>
      <AddMediaScreen
        open={addOpen}
        onOpenChange={(open) => {
          if (open) {
            openAdd();
          } else {
            closeAdd();
          }
        }}
      />
    </section>
  );
}
