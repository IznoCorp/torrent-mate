/**
 * ResolutionDeck — the keyboard-driven rapid-resolution surface for ambiguous /
 * low-confidence scrape decisions (webui-overhaul OBJ2B).
 *
 * Presents ONE pending decision at a time: the extracted folder title/year on
 * the left, its candidate matches (poster · title · year · overview · score)
 * compared as selectable cards, and a manual title/year search override that
 * appends fresh candidates. Validating pins the chosen provider identity
 * (``resolve``) and auto-advances to the next decision; a running counter shows
 * how many remain. Full keyboard control makes "20 ambiguous in ~2 minutes"
 * realistic:
 *
 * - ``←`` / ``→`` move the candidate selection
 * - ``Entrée`` validate the selected candidate
 * - ``d`` dismiss (leave the folder as-is)
 * - ``s`` focus the manual search
 * - ``n`` skip to the next decision without deciding
 *
 * Backed entirely by existing endpoints (no new backend): the candidates,
 * ``poster_url``/``overview``/``score`` and the live search all already exist.
 */

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactElement,
  type SyntheticEvent,
} from "react";
import { toast } from "sonner";

import {
  decisionsKeys,
  type DecisionCandidate,
  type ResolveRequest,
} from "@/api/decisions";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { TRIGGER_LABEL, TRIGGER_TONE } from "@/components/decisions/triggers";
import { ApiError } from "@/api/client";
import { frenchErrorDetail } from "@/components/decisions/errors";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { Kbd } from "@/components/ds/Kbd";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDecisionDetail,
  useDecisions,
  useDismissDecision,
  useResolveDecision,
  useSearchDecision,
} from "@/hooks/useDecisions";
import { cn } from "@/lib/utils";

/** Whether the current focus is a text field (so shortcuts don't hijack typing). */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || target.isContentEditable;
}

/** Props for {@link ResolutionDeck}. */
export interface ResolutionDeckProps {
  /**
   * When set, the deck opens positioned on this ``scrape_decision.id`` once it
   * is present in the loaded pending queue (C18) — the target of both the
   * ambiguous-card "Résoudre" and the non-identified enqueue flows.
   */
  readonly initialDecisionId?: number;
}

/**
 * ResolutionDeck — one-at-a-time keyboard resolution of pending decisions.
 *
 * Args:
 *   initialDecisionId: Optional decision to open on (C18).
 *
 * Returns:
 *   The resolution deck element.
 */
export function ResolutionDeck({
  initialDecisionId,
}: ResolutionDeckProps = {}): ReactElement {
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

  // ── Loading / error / empty ────────────────────────────────────────────
  if (pendingQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={`sk-${String(i)}`} className="aspect-[2/3] w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (pendingQuery.isError) {
    return (
      <ErrorState
        title="Impossible de charger les décisions"
        {...(pendingQuery.error instanceof Error
          ? { message: pendingQuery.error.message }
          : {})}
        onRetry={() => {
          void pendingQuery.refetch();
        }}
      />
    );
  }

  if (current == null) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title="Aucune décision à résoudre"
        description="Toutes les ambiguïtés de scraping ont été traitées."
      />
    );
  }

  const busy = resolveMut.isPending || dismissMut.isPending;
  const isFlipping = flippingId === current.id;
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

  // ── Deck ───────────────────────────────────────────────────────────────
  return (
    <div
      ref={deckRef}
      tabIndex={-1}
      role="group"
      aria-label="File de résolution des décisions"
      className="flex flex-col gap-4 outline-none"
    >
      <p className="sr-only" role="status" aria-live="polite">
        {liveStatus}
      </p>
      <div
        className={cn(
          "relative flex flex-col gap-4",
          isFlipping && "ps-resolve-out",
        )}
      >
        {isFlipping && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
            <CheckCircle2
              className="ps-count-pop size-16 text-success"
              aria-hidden="true"
            />
          </div>
        )}
        {/* Header: extracted media + trigger + progress + shortcuts */}
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1 flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 break-words text-base font-semibold">
                {current.extracted_title}
              </span>
              {current.extracted_year != null && (
                <span className="font-mono text-sm tabular-nums text-muted-foreground">
                  {current.extracted_year}
                </span>
              )}
              <Badge tone={TRIGGER_TONE[current.trigger] ?? "neutral"} dot>
                {TRIGGER_LABEL[current.trigger] ?? current.trigger}
              </Badge>
            </div>
            <span className="font-mono text-xs text-muted-foreground">
              {current.media_kind === "movie" ? "Film" : "Série"} ·{" "}
              {String(visible.length)} restante(s)
              {skipped > 0 && ` · ${String(skipped)} passée(s)`}
            </span>
          </div>
          <div className="hidden flex-wrap items-center gap-3 text-xs text-muted-foreground pointer-fine:flex">
            <span className="flex items-center gap-1">
              <Kbd>←</Kbd>
              <Kbd>→</Kbd> choisir
            </span>
            <span className="flex items-center gap-1">
              <Kbd>⏎</Kbd> valider
            </span>
            <span className="flex items-center gap-1">
              <Kbd>d</Kbd> ignorer
            </span>
            <span className="flex items-center gap-1">
              <Kbd>n</Kbd> passer
            </span>
            <span className="flex items-center gap-1">
              <Kbd>s</Kbd> chercher
            </span>
          </div>
        </div>

        {/* Manual search override */}
        <form
          onSubmit={handleSearchSubmit}
          className="flex flex-wrap items-end gap-2"
        >
          <div className="flex flex-1 flex-col gap-1">
            <label
              htmlFor="deck-search-title"
              className="text-xs font-medium text-muted-foreground"
            >
              Recherche manuelle
            </label>
            <Input
              id="deck-search-title"
              ref={searchRef}
              value={searchTitle}
              onChange={(e) => {
                setSearchTitle(e.target.value);
              }}
              onKeyDown={(e) => {
                // C7: Échap releases the search input and hands keyboard control
                // back to the deck (arrows/Entrée) instead of trapping the user.
                if (e.key === "Escape") {
                  e.preventDefault();
                  searchRef.current?.blur();
                  deckRef.current?.focus();
                }
              }}
              placeholder="Titre à rechercher"
            />
          </div>
          <div className="flex w-24 flex-col gap-1">
            <label
              htmlFor="deck-search-year"
              className="text-xs font-medium text-muted-foreground"
            >
              Année
            </label>
            <Input
              id="deck-search-year"
              value={searchYear}
              inputMode="numeric"
              onChange={(e) => {
                setSearchYear(e.target.value);
              }}
              placeholder="2024"
            />
          </div>
          <Button
            type="submit"
            variant="outline"
            disabled={searchMut.isPending}
          >
            Chercher
          </Button>
        </form>

        {/* Candidates */}
        {candidates.length === 0 ? (
          <EmptyState
            title="Aucun candidat"
            description="Aucun match automatique — utilise la recherche manuelle ci-dessus ou ignore ce dossier."
          />
        ) : (
          <div
            ref={gridRef}
            className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
          >
            {candidates.map((candidate, idx) => (
              <div
                key={`${candidate.provider}-${String(candidate.provider_id)}-${String(idx)}`}
                data-candidate-idx={idx}
              >
                <CandidateCard
                  candidate={candidate}
                  isSelected={idx === selected}
                  onClick={() => {
                    setSelected(idx);
                  }}
                />
              </div>
            ))}
          </div>
        )}

        {/* Actions — a thumb-reachable sticky bar on mobile (C11), inline on ≥sm */}
        <div className="sticky bottom-0 z-10 -mx-1 flex items-center gap-2 border-t border-border bg-background/95 px-1 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:px-0 sm:py-0 sm:backdrop-blur-none">
          <Button
            className="flex-1 sm:flex-none"
            onClick={handleResolve}
            disabled={busy || candidates.length === 0}
          >
            Valider le choix
          </Button>
          <Button
            className="flex-1 sm:flex-none"
            variant="outline"
            onClick={handleDismiss}
            disabled={busy}
          >
            Ignorer
          </Button>
          <Button
            className="flex-1 sm:flex-none"
            variant="ghost"
            onClick={handleSkip}
            disabled={busy}
          >
            Passer
          </Button>
        </div>
      </div>
    </div>
  );
}
