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
import { MoreVertical, Plus } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactElement,
} from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { acqKeys } from "@/api/acquisition";
import { AddMediaScreen } from "@/components/acquisition/AddMediaScreen";
import {
  PULL_LOADING_PX,
  lockAxis,
  pullArmed,
  pullHeight,
  shouldRefresh,
  shouldStartViewSwipe,
  viewSwipeResult,
} from "@/components/acquisition/gestures";
import { MaintenantPanel } from "@/components/acquisition/MaintenantPanel";
import { MqToaster, mqtoast } from "@/components/acquisition/MqToast";
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
import {
  TOPBAR_HEIGHT_VAR,
  VIEWTABS_HEIGHT_VAR,
  aboveBottomBar,
} from "@/components/layout/bottom-bar-metrics";
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
  const viewtabsRef = useRef<HTMLDivElement | null>(null);

  // Publish the view-tabs height: the Suivis filter zone pins directly under
  // this bar and needs its real measured height (same contract as the bars).
  useEffect(() => {
    const el = viewtabsRef.current;
    const root = document.documentElement;
    if (el == null) return;
    const publish = (): void => {
      root.style.setProperty(
        VIEWTABS_HEIGHT_VAR,
        `${String(el.getBoundingClientRect().height)}px`,
      );
    };
    publish();
    if (typeof ResizeObserver === "undefined") {
      return () => {
        root.style.removeProperty(VIEWTABS_HEIGHT_VAR);
      };
    }
    const observer = new ResizeObserver(publish);
    observer.observe(el);
    return () => {
      observer.disconnect();
      root.style.removeProperty(VIEWTABS_HEIGHT_VAR);
    };
  }, []);
  const dragRef = useRef<{
    x: number;
    y: number;
    axis: "x" | "y" | null;
    atTop: boolean;
  } | null>(null);
  // Maquette .ptr model: a damped height while dragging (transition cut so
  // the bar tracks the finger), 44 px while the refresh actually runs.
  const [pull, setPull] = useState<{ height: number; dragging: boolean }>({
    height: 0,
    dragging: false,
  });
  const [refreshing, setRefreshing] = useState(false);
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

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (drag == null) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      drag.axis ??= lockAxis(dx, dy);
      if (drag.axis === "y" && drag.atTop && dy > 0 && !refreshing) {
        setPull({ height: pullHeight(dy), dragging: true });
      }
    },
    [refreshing],
  );

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      dragRef.current = null;
      if (drag == null) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;

      if (drag.axis === "x") {
        setPull({ height: 0, dragging: false });
        const width = pagerRef.current?.getBoundingClientRect().width ?? 0;
        const next = viewSwipeResult(dx, width, activeTab);
        if (next !== activeTab) setActiveTab(next);
        return;
      }
      if (!refreshing && shouldRefresh(dy, drag.atTop)) {
        // Maquette: armed release → 44 px spinner until the refetch settles
        // (its 1100 ms was a demo stand-in for a real round-trip).
        setRefreshing(true);
        setPull({ height: PULL_LOADING_PX, dragging: false });
        void Promise.resolve(
          queryClientForPull.invalidateQueries({ queryKey: acqKeys.all }),
        ).finally(() => {
          setRefreshing(false);
          setPull({ height: 0, dragging: false });
        });
        return;
      }
      setPull({ height: 0, dragging: false });
    },
    [activeTab, setActiveTab, queryClientForPull, refreshing],
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
        mqtoast("Source bloquée — bascule vers une autre release.");
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
    <section className="mq -mx-4 -mt-4 flex flex-col md:mx-auto md:mt-0 md:max-w-2xl">
      {/* Tabs — the maquette's .viewtabs: an equal-width .seg segment plus a
          DETACHED « ⋮ » (.more). Pinned under the topbar (measured height, not
          a hardcoded offset) so only the list below scrolls.
          ACQUISITION-7 (ticket 250): full WAI-ARIA tablist wiring — roving
          tabIndex + arrow-key navigation + tab/panel linkage. */}
      <div
        ref={viewtabsRef}
        className="viewtabs sticky z-30 bg-background"
        style={{ top: `var(${TOPBAR_HEIGHT_VAR}, 56px)` }}
      >
        <div
          role="tablist"
          aria-label="Vues de la page Acquisition"
          className="seg"
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
            >
              {tab.label}
              {/* §3.2 — the badge counts WHAT AWAITS THE OPERATOR, same
                  derivation as the nav badge (§13). « ? » when unknowable. */}
              {tab.id === "maintenant" && (waiting.unknown || waiting.count > 0) && (
                <span
                  data-testid="tab-maintenant-badge"
                  className="n"
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
        </div>
        {/* « ⋮ » — its own bordered button BESIDE the segment (maquette
            .more), never inside the train: Veille/Obligations are not a
            third view. */}
        <button
          type="button"
          aria-label="Plus — veille et obligations"
          className="more"
          onClick={() => {
            setPlusOpen(true);
          }}
        >
          <MoreVertical aria-hidden="true" />
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
        className="flex touch-pan-y flex-col"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {/* Maquette .ptr — spinner-only chrome. The sr-only live region is
            ALWAYS mounted with conditional content: a region that mounts on
            first use announces nothing the first time — assistive tech only
            reports changes inside an existing region. It is absolutely
            positioned, so the grid cell layout of .ptr is untouched. */}
        <div
          data-testid="pull-indicator"
          className={`ptr${pullArmed(pull.height) ? " armed" : ""}${refreshing ? " loading" : ""}`}
          style={{
            height: `${String(pull.height)}px`,
            ...(pull.dragging ? { transition: "none" } : {}),
          }}
        >
          <div className="spin" />
          <p aria-live="polite" className="sr-only">
            {refreshing
              ? "Actualisation en cours"
              : pull.height > 0
                ? pullArmed(pull.height)
                  ? "Relâchez pour actualiser"
                  : "Tirez pour actualiser"
                : ""}
          </p>
        </div>
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
        data-testid="acq-fab"
        className="fab fixed right-4 z-30"
        style={{ bottom: aboveBottomBar("1rem") }}
        aria-label="Ajouter un média"
        onClick={() => {
          openAdd();
        }}
      >
        <Plus className="size-6" aria-hidden="true" />
      </button>

      {/* Maquette in-page toast — single host for the whole surface. */}
      <MqToaster />
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
