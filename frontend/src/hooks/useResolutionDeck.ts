/**
 * useResolutionDeck — the deck-state machine behind {@link ResolutionDeck}.
 *
 * Owns the whole one-at-a-time resolution flow beyond raw presentation: the
 * pending-queue query, the optimistic ``processed`` set, the cursor + candidate
 * selection, the per-decision reset, the manual-search override, the three
 * shared decision mutations (resolve / dismiss / search-override), the C8 flip
 * animation state + settle timer, the global keyboard shortcuts, and the
 * keep-selection-in-view scroll. The presentation component
 * (``components/decisions/ResolutionDeck.tsx``) consumes this hook's result and
 * renders it — no data logic lives in the view layer.
 */

import { useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
  type SyntheticEvent,
} from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  decisionsKeys,
  type DecisionCandidate,
  type DecisionListItem,
  type ResolveRequest,
} from "@/api/decisions";
import { frenchErrorDetail } from "@/components/decisions/errors";
import {
  useDecisionDetail,
  useDecisions,
  useDismissDecision,
  useResolveDecision,
  useSearchDecision,
} from "@/hooks/useDecisions";

/** Whether the current focus is a text field (so shortcuts don't hijack typing). */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || target.isContentEditable;
}

/** Everything {@link ResolutionDeck} needs to render + drive the deck. */
export interface ResolutionDeckMachine {
  // ---- Pending-queue lifecycle (loading / error / empty branches) ----
  /** ``true`` while the pending-queue query is loading. */
  readonly isLoading: boolean;
  /** ``true`` when the pending-queue query failed. */
  readonly isError: boolean;
  /** The pending-queue query error, if any. */
  readonly error: Error | null;
  /** Refetch the pending queue (the error-state retry affordance). */
  readonly refetch: () => void;

  // ---- Current decision ----
  /** The decision currently under the cursor, or ``undefined`` when the deck is empty. */
  readonly current: DecisionListItem | undefined;
  /** Number of decisions still visible in the deck. */
  readonly visibleCount: number;
  /** Running count of skipped decisions this pass (C9). */
  readonly skipped: number;

  // ---- Candidates ----
  /** Base candidates + live-search overrides for the current decision. */
  readonly candidates: readonly DecisionCandidate[];
  /** Index of the selected candidate. */
  readonly selected: number;
  /** Select a candidate by index (candidate-card click). */
  readonly setSelected: (index: number) => void;

  // ---- Manual search override ----
  /** Manual-search title input value. */
  readonly searchTitle: string;
  /** Set the manual-search title. */
  readonly setSearchTitle: (value: string) => void;
  /** Manual-search year input value. */
  readonly searchYear: string;
  /** Set the manual-search year. */
  readonly setSearchYear: (value: string) => void;
  /** ``true`` while the search-override mutation is in flight. */
  readonly isSearching: boolean;

  // ---- Refs (created here, attached in the view) ----
  /** The manual-search input (focus/blur management). */
  readonly searchRef: RefObject<HTMLInputElement | null>;
  /** The focusable deck container (keyboard control hand-back). */
  readonly deckRef: RefObject<HTMLDivElement | null>;
  /** The candidate grid (keep-selection-in-view scrolling). */
  readonly gridRef: RefObject<HTMLDivElement | null>;

  // ---- Actions ----
  /** Resolve the selected candidate for the current decision. */
  readonly handleResolve: () => void;
  /** Dismiss the current decision. */
  readonly handleDismiss: () => void;
  /** Skip to the next decision without deciding (C9). */
  readonly handleSkip: () => void;
  /** Submit the manual search override. */
  readonly handleSearchSubmit: (e: SyntheticEvent) => void;

  // ---- Derived render state ----
  /** ``true`` while a resolve / dismiss mutation is in flight. */
  readonly busy: boolean;
  /** ``true`` while the current decision plays its resolve-flip (C8). */
  readonly isFlipping: boolean;
  /** Off-screen live-region text announcing the current selection (C10). */
  readonly liveStatus: string;
}

/**
 * Drive the keyboard resolution deck.
 *
 * Args:
 *   initialDecisionId: Optional decision to open on once it appears in the
 *       loaded pending queue (C18).
 *
 * Returns:
 *   A {@link ResolutionDeckMachine} the presentation renders.
 */
export function useResolutionDeck(
  initialDecisionId?: number,
): ResolutionDeckMachine {
  const queryClient = useQueryClient();
  const pendingQuery = useDecisions({ status: "pending", page_size: 200 });
  const queue = useMemo(
    () => pendingQuery.data?.items ?? [],
    [pendingQuery.data],
  );

  // Locally-processed ids drop out of the deck immediately (optimistic), while
  // the pending query re-syncs in the background.
  const [processed, setProcessed] = useState<ReadonlySet<number>>(
    () => new Set(),
  );
  const visible = useMemo(
    () => queue.filter((d) => !processed.has(d.id)),
    [queue, processed],
  );

  const [cursor, setCursor] = useState(0);
  const clampedCursor =
    visible.length === 0 ? 0 : Math.min(cursor, visible.length - 1);
  const current = visible[clampedCursor];
  const currentId = current?.id;

  // C18: jump to a requested decision once it appears in the loaded queue, and
  // only once per id — so navigating away within the deck afterwards is not
  // yanked back.
  const appliedInitialRef = useRef<number | null>(null);
  useEffect(() => {
    if (initialDecisionId == null) return;
    if (appliedInitialRef.current === initialDecisionId) return;
    const idx = visible.findIndex((d) => d.id === initialDecisionId);
    if (idx >= 0) {
      setCursor(idx);
      appliedInitialRef.current = initialDecisionId;
    }
  }, [initialDecisionId, visible]);

  const detailQuery = useDecisionDetail(currentId ?? 0);
  const baseCandidates = useMemo<readonly DecisionCandidate[]>(
    () => detailQuery.data?.candidates ?? [],
    [detailQuery.data],
  );

  const [overrides, setOverrides] = useState<readonly DecisionCandidate[]>([]);
  const candidates = useMemo(
    () => [...baseCandidates, ...overrides],
    [baseCandidates, overrides],
  );
  const [selected, setSelected] = useState(0);

  const [searchTitle, setSearchTitle] = useState("");
  const [searchYear, setSearchYear] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  // A focusable deck container so releasing the search input hands keyboard
  // control back to the deck (C7). A running count of skipped decisions (C9).
  const deckRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const [skipped, setSkipped] = useState(0);
  // The decision id mid resolve-flip (C8) — its view fades out before the
  // next decision slides in; a rafale of validations finalises it at once.
  const [flippingId, setFlippingId] = useState<number | null>(null);
  const flipRef = useRef<{ id: number; timer: number } | null>(null);

  // Reset per-decision state whenever the current decision changes.
  useEffect(() => {
    setOverrides([]);
    setSelected(0);
    setSearchTitle(current?.extracted_title ?? "");
    setSearchYear(
      current?.extracted_year != null ? String(current.extracted_year) : "",
    );
  }, [currentId, current?.extracted_title, current?.extracted_year]);

  const markProcessed = useCallback(
    (id: number) => {
      setProcessed((prev) => new Set(prev).add(id));
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
    },
    [queryClient],
  );

  const resolveMut = useResolveDecision({
    onResolved: (_data, vars) => {
      toast.success(
        "Décision validée — le média poursuit son pipeline (scraping → trailers → vérification → dispatch)",
      );
      // §4 — the shared UNION invalidation set already refreshed the Flow Board +
      // staging grid (plus decisions + history) so the operator SEES the media
      // advance and leave staging now, not only on the next WS tick / poll.
      // C8: fade the resolved decision out (~400 ms) before the next slides in.
      // A rafale of validations finalises any in-flight flip immediately so the
      // flow never slows down — only the last one gets to play out in full.
      if (flipRef.current) {
        clearTimeout(flipRef.current.timer);
        markProcessed(flipRef.current.id);
      }
      setFlippingId(vars.id);
      const timer = window.setTimeout(() => {
        flipRef.current = null;
        setFlippingId(null);
        markProcessed(vars.id);
      }, 400);
      flipRef.current = { id: vars.id, timer };
    },
    onError: (err: unknown) => {
      // A 409 during a pipeline run is EXPECTED (global lock) — say so in
      // French instead of surfacing « Pipeline lock held » as a breakage
      // (revue mobile 2026-07-15, Lucky).
      toast.error(
        err instanceof ApiError
          ? frenchErrorDetail(err)
          : err instanceof Error
            ? err.message
            : "Échec de la validation",
      );
    },
  });

  const dismissMut = useDismissDecision({
    onDismissed: (_data, id) => {
      toast.success("Décision ignorée — dossier laissé tel quel");
      markProcessed(id);
    },
    onError: (err: unknown) => {
      toast.error(
        err instanceof ApiError
          ? frenchErrorDetail(err)
          : err instanceof Error
            ? err.message
            : "Échec de l'action",
      );
    },
  });

  const searchMut = useSearchDecision({
    onResults: (data) => {
      setOverrides(data.candidates);
      // Preselect the first fresh result and RELEASE the search input so the
      // arrow/enter shortcuts work immediately (C7: the search sits on the
      // nominal path from an enqueued non-identified item, so a trapped focus
      // would strand the whole keyboard flow).
      setSelected(data.candidates.length > 0 ? baseCandidates.length : 0);
      searchRef.current?.blur();
      deckRef.current?.focus();
      toast.success(`${String(data.candidates.length)} résultat(s) trouvé(s)`);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Recherche échouée");
    },
  });

  const handleResolve = useCallback(() => {
    if (current == null) return;
    const candidate = candidates[selected];
    if (candidate == null) return;
    const via: ResolveRequest["via"] =
      selected >= baseCandidates.length ? "search_override" : "pick";
    resolveMut.mutate({
      id: current.id,
      body: {
        provider: candidate.provider,
        provider_id: candidate.provider_id,
        via,
      },
    });
  }, [current, candidates, selected, baseCandidates.length, resolveMut]);

  const handleDismiss = useCallback(() => {
    if (current != null) dismissMut.mutate(current.id);
  }, [current, dismissMut]);

  const handleSkip = useCallback(() => {
    const len = visible.length;
    if (len <= 1) return;
    // C9: wrap to the head of the queue instead of stalling on the last card,
    // count the pass, and say so — so a skip is never a silent dead end.
    setSkipped((n) => n + 1);
    const next = clampedCursor + 1;
    if (next >= len) {
      toast.info("Retour au début de la file");
      setCursor(0);
    } else {
      setCursor(next);
    }
  }, [visible.length, clampedCursor]);

  const handleSearchSubmit = useCallback(
    (e: SyntheticEvent) => {
      e.preventDefault();
      if (current == null || searchTitle.trim() === "") return;
      const yearNum = Number.parseInt(searchYear, 10);
      searchMut.mutate({
        id: current.id,
        body: {
          title: searchTitle.trim(),
          ...(Number.isFinite(yearNum) ? { year: yearNum } : {}),
        },
      });
    },
    [current, searchTitle, searchYear, searchMut],
  );

  // Global keyboard shortcuts (ignored while typing in a field).
  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if (current == null) return;
      if (isTypingTarget(e.target)) return;
      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          setSelected((s) => Math.max(0, s - 1));
          break;
        case "ArrowRight":
          e.preventDefault();
          setSelected((s) => Math.min(candidates.length - 1, s + 1));
          break;
        case "Enter":
          e.preventDefault();
          handleResolve();
          break;
        case "d":
          e.preventDefault();
          handleDismiss();
          break;
        case "n":
          e.preventDefault();
          handleSkip();
          break;
        case "s":
          e.preventDefault();
          searchRef.current?.focus();
          break;
        default:
          break;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [current, candidates.length, handleResolve, handleDismiss, handleSkip]);

  // C10: keep the selected candidate scrolled into view as the arrows move it,
  // so keyboard navigation never selects an off-screen card (crucial on mobile
  // where only a couple of cards fit). ``nearest`` avoids gratuitous scrolling.
  useEffect(() => {
    const node = gridRef.current?.querySelector<HTMLElement>(
      `[data-candidate-idx="${String(selected)}"]`,
    );
    // Guard: scrollIntoView is unimplemented in jsdom (and absent on old hosts).
    if (typeof node?.scrollIntoView === "function") {
      node.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [selected, candidates.length]);

  // Clear any pending resolve-flip timer on unmount (C8).
  useEffect(() => {
    return () => {
      if (flipRef.current) clearTimeout(flipRef.current.timer);
    };
  }, []);

  const busy = resolveMut.isPending || dismissMut.isPending;
  // ``current?.id`` is ``number | undefined`` and ``flippingId`` is
  // ``number | null`` (never undefined), so this is false whenever the deck is
  // empty — matching the original post-guard ``flippingId === current.id``.
  const isFlipping = flippingId === current?.id;
  const selectedCandidate = candidates[selected];
  // C10: an off-screen, polite live region announcing the current selection so
  // keyboard-only / screen-reader users track the arrow moves without sight of
  // the grid.
  const liveStatus =
    selectedCandidate != null
      ? `Sélection ${String(selected + 1)} sur ${String(candidates.length)} : ${selectedCandidate.title}${
          selectedCandidate.year != null
            ? ` (${String(selectedCandidate.year)})`
            : ""
        }`
      : "Aucun candidat sélectionné";

  return {
    isLoading: pendingQuery.isLoading,
    isError: pendingQuery.isError,
    error: pendingQuery.error,
    refetch: () => {
      void pendingQuery.refetch();
    },
    current,
    visibleCount: visible.length,
    skipped,
    candidates,
    selected,
    setSelected,
    searchTitle,
    setSearchTitle,
    searchYear,
    setSearchYear,
    isSearching: searchMut.isPending,
    searchRef,
    deckRef,
    gridRef,
    handleResolve,
    handleDismiss,
    handleSkip,
    handleSearchSubmit,
    busy,
    isFlipping,
    liveStatus,
  };
}
