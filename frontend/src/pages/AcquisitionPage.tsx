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

import { acqKeys, getFollowed } from "@/api/acquisition";
import { AddMediaScreen } from "@/components/acquisition/AddMediaScreen";
import {
  PULL_LOADING_PX,
  PULL_SPINNER_CAP_MS,
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
  DEFAULT_TAB,
  FULL_INVALIDATE_EVENTS,
  LEGACY_TAB_REDIRECTS,
  OBLIGATION_INVALIDATE_EVENTS,
  TABS,
  WANTED_INVALIDATE_EVENTS,
  type TabId,
} from "@/components/acquisition/meta";
import { PlusSheet } from "@/components/acquisition/PlusSheet";
import { FollowsPanel } from "@/components/acquisition/FollowsPanel";
import {
  VIEWTABS_HEIGHT_VAR,
  aboveBottomBar,
  publishMeasuredHeight,
} from "@/components/layout/bottom-bar-metrics";
import { scrollRootOf } from "@/lib/scroll-root";
import { useWaitingForOperator } from "@/hooks/useAcquisition";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { handleTablistKeyDown } from "@/lib/tablist";
import { useBackCloses } from "@/lib/use-back-closes";

/**
 * AcquisitionPage — the authenticated acquisition route (``/acquisition``).
 *
 * Two views — Suivis (default, no param) and Maintenant (``?tab=maintenant``)
 * — each answering one of the operator's questions. Legacy ``?tab=`` values
 * are redirected to the view that now answers them, and the last active view
 * is remembered: coming back to /acquisition without an explicit ``?tab=``
 * reopens the view the operator left. Live events from the WebSocket
 * invalidate the matching TanStack Query caches (R13 — processes only new
 * events, not the whole ring on every render).
 *
 * Returns:
 *   The acquisition page element.
 */
/** localStorage key remembering the last active acquisition view. */
const LAST_TAB_STORAGE_KEY = "tm.acquisition.lastTab";

export default function AcquisitionPage(): ReactElement {
  // The active tab is URL-addressable (?tab=<id>) — DOIT-10: the tab is a
  // shareable deep-link and Back returns to the previous tab. Derived from the
  // URL (single source of truth); the default "suivis" carries no param so
  // /acquisition stays clean and ?tab=maintenant is the shareable form.
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const waiting = useWaitingForOperator();
  const rawTab = searchParams.get("tab");

  // Redirect legacy ?tab= values to the view that now answers them, and strip
  // an explicit default (?tab=suivis) to the canonical clean URL. Replace so
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
    const target = rawTab === DEFAULT_TAB ? DEFAULT_TAB : LEGACY_TAB_REDIRECTS[rawTab];
    if (target === undefined) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (target === DEFAULT_TAB) {
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
    : DEFAULT_TAB;

  // Remember the last active view and reopen it when the operator comes back
  // to /acquisition without an explicit ?tab= (their words: « toujours revenir
  // sur l'onglet sur lequel on était en dernier »). A deep link WITH ?tab=
  // always wins; the restore replaces so Back gains no extra entry.
  const restoredRef = useRef(false);
  useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;
    if (rawTab !== null) return;
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(LAST_TAB_STORAGE_KEY);
    } catch {
      return;
    }
    if (stored === null || stored === DEFAULT_TAB) return;
    if (!TABS.some((t) => t.id === stored)) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("tab", stored);
        return next;
      },
      { replace: true },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(LAST_TAB_STORAGE_KEY, activeTab);
    } catch {
      // Private mode: the view still works, it just won't be remembered.
    }
  }, [activeTab]);
  // ACQUISITION-7 (ticket 250): keyboard-driven activation (arrows follow
  // focus) REPLACES the current history entry — holding ArrowRight must not
  // stack one entry per keystroke. Click activation keeps push (D3
  // addressable URLs: Back returns to the previous tab).
  const setActiveTab = useCallback(
    (id: TabId, viaKeyboard = false) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id === DEFAULT_TAB) next.delete("tab");
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
  // EXACT, not ceiled: the filter zone must pin on the very pixel it already
  // occupies at rest, or the gap between the two bars changes the moment it
  // pins — which is what the operator sees as « l'écart diminue quand on
  // scroll ». This bar lives inside the scrollport, so the iOS URL bar cannot
  // resize it mid-gesture; the sub-pixel churn the quantisation guards against
  // does not apply here.
  useEffect(() => {
    const el = viewtabsRef.current;
    const root = document.documentElement;
    if (el == null) return;
    const publish = (): void => {
      publishMeasuredHeight(VIEWTABS_HEIGHT_VAR, el.getBoundingClientRect().height, true);
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
    // Same for a zone that owns its own horizontal drag — the filter pills
    // scroll sideways, and on iOS the ancestor `touch-pan-y` hands that drag
    // to us, so scrolling the pills changed view (operator, 2026-08-08).
    const from = e.target as HTMLElement;
    if (from.closest("[data-swipe]") != null) return;
    if (from.closest("[data-noswipe]") != null) return;
    if (!shouldStartViewSwipe(e.clientX, pager.getBoundingClientRect().left)) {
      return;
    }
    dragRef.current = { x: e.clientX, y: e.clientY, axis: null };
  }, []);

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (drag == null) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.axis ??= lockAxis(dx, dy);
  }, []);

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      dragRef.current = null;
      if (drag?.axis !== "x") return;
      const dx = e.clientX - drag.x;
      const width = pagerRef.current?.getBoundingClientRect().width ?? 0;
      const next = viewSwipeResult(dx, width, activeTab);
      if (next !== activeTab) setActiveTab(next);
    },
    [activeTab, setActiveTab],
  );

  // ── Pull-to-refresh — TOUCH events, not pointer events ────────────────
  //
  // The pager carries `touch-pan-y`: the browser owns vertical pans, so a
  // real finger gets pointercancel after a few px and a pointer-based pull
  // never accumulates (it only ever worked with synthetic events). The
  // vertical pull therefore listens to raw touch events and claims the pan
  // with preventDefault — which requires a NON-passive listener, hence
  // addEventListener instead of a React prop.

  const refreshingRef = useRef(false);
  const touchDragRef = useRef<{
    x: number;
    y: number;
    axis: "x" | "y" | null;
    atTop: boolean;
    dy: number;
  } | null>(null);

  const runRefresh = useCallback(() => {
    // Maquette: armed release → 44 px spinner until the refetch settles
    // (its 1100 ms was a demo stand-in for a real round-trip).
    refreshingRef.current = true;
    setRefreshing(true);
    setPull({ height: PULL_LOADING_PX, dragging: false });

    const settle = (): void => {
      if (!refreshingRef.current) return;
      refreshingRef.current = false;
      setRefreshing(false);
      setPull({ height: 0, dragging: false });
    };

    // The spinner is CAPPED. Waiting on every acquisition query means waiting
    // on the slowest of them, and the operator watched that bar sit for tens
    // of seconds. Past the cap the bar collapses and the refetches finish in
    // the background — the lists update when their data lands, which is what
    // the pull asked for. (The unbounded `fetch` that made those waits
    // possible at all is fixed at the source in `api/client`.)
    const cap = window.setTimeout(settle, PULL_SPINNER_CAP_MS);
    void Promise.resolve(
      queryClientForPull.invalidateQueries({ queryKey: acqKeys.all }),
    )
      .catch(() => {
        // §8 — a refresh that could not run says so; silence would read as
        // « up to date ».
        mqtoast("Actualisation impossible — vérifiez la connexion.");
      })
      .finally(() => {
        window.clearTimeout(cap);
        settle();
      });
  }, [queryClientForPull]);

  useEffect(() => {
    const el = pagerRef.current;
    if (el == null) return undefined;

    const onTouchStart = (e: TouchEvent): void => {
      if (e.touches.length !== 1) {
        // A second finger cancels the pull — and must COLLAPSE the bar with
        // it: leaving it open showed an armed indicator that no release
        // would ever act on.
        touchDragRef.current = null;
        if (!refreshingRef.current) setPull({ height: 0, dragging: false });
        return;
      }
      const t = e.touches[0];
      if (t == null) return;
      const atTop = (scrollRootOf(el)?.scrollTop ?? 0) <= 0;
      touchDragRef.current = {
        x: t.clientX,
        y: t.clientY,
        axis: null,
        dy: 0,
        atTop,
      };
    };

    const onTouchMove = (e: TouchEvent): void => {
      const drag = touchDragRef.current;
      if (drag == null || e.touches.length !== 1) return;
      const t = e.touches[0];
      if (t == null) return;
      const dx = t.clientX - drag.x;
      const dy = t.clientY - drag.y;
      drag.axis ??= lockAxis(dx, dy);
      // NOTHING is claimed here. `preventDefault` would make this listener
      // non-passive, which is what took iOS off the compositor and made the
      // sticky header shiver — the pull needs no claim: at the top, CSS
      // `overscroll-behavior-y: none` means a downward drag scrolls nothing,
      // and raw touchmove keeps reporting the finger through it.
      if (drag.axis !== "y") return;
      drag.dy = dy;
      if (drag.atTop && dy > 0 && !refreshingRef.current) {
        setPull({ height: pullHeight(dy), dragging: true });
      }
    };

    const onTouchEnd = (): void => {
      const drag = touchDragRef.current;
      touchDragRef.current = null;
      if (drag?.axis !== "y") {
        // Not our gesture (or already cancelled) — still make sure no bar is
        // left hanging open from a partial pull.
        if (!refreshingRef.current) setPull({ height: 0, dragging: false });
        return;
      }
      if (!refreshingRef.current && shouldRefresh(drag.dy, drag.atTop)) {
        runRefresh();
        return;
      }
      if (!refreshingRef.current) setPull({ height: 0, dragging: false });
    };

    // EVERY listener here is passive — the page must never leave the
    // compositor. A non-passive `touchmove` announces « I may cancel this
    // scroll », so iOS routes every frame through the main thread and the
    // content scrolls a frame ahead of the position:sticky header: that gap
    // IS the shiver the operator reported three times. Gating it per gesture
    // (attempt #2) was not enough — the flag is sampled at touchstart, so a
    // gesture STARTING at the top kept the listener for its whole duration,
    // which is most scrolls on this page.
    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    el.addEventListener("touchend", onTouchEnd);
    el.addEventListener("touchcancel", onTouchEnd);
    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("touchend", onTouchEnd);
      el.removeEventListener("touchcancel", onTouchEnd);
    };
  }, [runRefresh]);
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  // Warm the Suivis list while the operator is still on Maintenant: the
  // panel only mounts on tab switch, and a cold query there made the list
  // feel slow. Same key+staleTime as FollowsPanel's useFollowed.
  useEffect(() => {
    void queryClient.prefetchQuery({
      queryKey: acqKeys.followed({ active: "all" }),
      queryFn: () => getFollowed({ active: "all" }),
      staleTime: 55_000,
    });
  }, [queryClient]);

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
  // Back gesture closes the « ⋮ » sheet instead of leaving the page.
  useBackCloses(
    plusOpen,
    useCallback(() => {
      setPlusOpen(false);
    }, []),
  );

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
      {/* Pinned at the TRUE top of the scrollport. `top: 0` was not it: sticky
          offsets resolve against the scrollport's content edge, and the shell's
          `main` carries `p-4` — so the tabs parked 16 px low and scrolled cards
          paraded through the band above them (operator, 2026-08-09, screenshot:
          a poster and a title visible over the tab bar). `-mt-4` already
          cancels that same padding for the layout; this cancels it for the
          pinning. The two must move together — the shell test pins main's
          padding for exactly that reason. */}
      <div
        ref={viewtabsRef}
        className="viewtabs sticky top-[-1rem] z-30 bg-background"
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
        // No `touch-action` restriction here. It used to carry `pan-y` to stop
        // the browser's OWN pull-to-refresh from reloading the page — the frame
        // does that now (the document cannot scroll at all), and `pan-y` on
        // this ancestor was ALSO what stopped the filter pills from scrolling
        // sideways: touch-action intersects down the whole chain, so a `pan-x`
        // scroller under a `pan-y` ancestor can pan on neither axis. The
        // restriction lives on the regions that want it instead — the card
        // rows and the panels' content — leaving the pill train free.
        className="flex flex-col"
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
        {activeTab === "suivis" && <FollowsPanel />}
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
