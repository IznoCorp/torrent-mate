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
 * All deck state, mutations, keyboard shortcuts and flip animation live in
 * {@link useResolutionDeck}; this component is pure presentation over it.
 */

import { CheckCircle2 } from "lucide-react";
import { type ReactElement } from "react";

import { CandidateCard } from "@/components/decisions/CandidateCard";
import { TRIGGER_LABEL, TRIGGER_TONE } from "@/components/decisions/triggers";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { Kbd } from "@/components/ds/Kbd";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useResolutionDeck } from "@/hooks/useResolutionDeck";
import { cn } from "@/lib/utils";

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
  const {
    isLoading,
    isError,
    error,
    refetch,
    current,
    visibleCount,
    skipped,
    candidates,
    selected,
    setSelected,
    searchTitle,
    setSearchTitle,
    searchYear,
    setSearchYear,
    isSearching,
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
  } = useResolutionDeck(initialDecisionId);

  // ── Loading / error / empty ────────────────────────────────────────────
  if (isLoading) {
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

  if (isError) {
    return (
      <ErrorState
        title="Impossible de charger les décisions"
        {...(error instanceof Error ? { message: error.message } : {})}
        onRetry={refetch}
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
              {String(visibleCount)} restante(s)
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
          <Button type="submit" variant="outline" disabled={isSearching}>
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
