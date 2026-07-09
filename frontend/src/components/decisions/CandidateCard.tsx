/**
 * CandidateCard — a selectable provider-match card for the scrape-arbiter
 * decision flow.
 *
 * Each card shows a poster thumbnail, title, year, confidence score bar, and a
 * provider badge. Clicking the card selects it for the resolve action; the
 * selected state is shown with a ring highlight.
 */

import { useState, type ReactElement } from "react";

import type { DecisionCandidate } from "@/api/decisions";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Provider badge labels in French.
 *
 * TMDB and TVDB are proper nouns — kept as-is.  Other providers would be added
 * here when the backend supports them.
 */
const PROVIDER_LABEL: Record<string, string> = {
  tmdb: "TMDB",
  tvdb: "TVDB",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Map a confidence score (0.0–1.0) to a CSS colour class for the score bar.
 *
 * Mirrors the DisksPanel capacity-bar pattern: a coloured ``<div>`` inside a
 * rounded-full muted track.  Tones follow the DS signal palette:
 *
 * - ≥ 0.7 → ``bg-success`` (green — high confidence)
 * - ≥ 0.4 → ``bg-warning`` (amber — medium confidence)
 * - < 0.4 → ``bg-destructive`` (red — low confidence)
 *
 * Args:
 *   score: Confidence score between 0.0 and 1.0.
 *
 * Returns:
 *   A Tailwind background colour class.
 */
function scoreBarColor(score: number): string {
  if (score >= 0.7) return "bg-success";
  if (score >= 0.4) return "bg-warning";
  return "bg-destructive";
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Props for {@link CandidateCard}.  All props are read-only. */
export interface CandidateCardProps {
  /** The provider candidate to render. */
  readonly candidate: DecisionCandidate;
  /** Whether this card is the currently-selected candidate. */
  readonly isSelected: boolean;
  /** Called when the user clicks the card to select it. */
  readonly onClick: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * CandidateCard — a selectable card showing a single provider match.
 *
 * Layout (mobile-first, single column):
 *
 * - Poster image (lazy-loaded, neutral fallback on error or null URL).
 * - Title + year line.
 * - Confidence score bar (0–100 % fill, colour-coded).
 * - Provider badge (TMDB / TVDB).
 *
 * The selected state adds a ring border using the primary colour.
 *
 * Args:
 *   candidate: The {@link DecisionCandidate} to render.
 *   isSelected: ``true`` when this card is the active selection.
 *   onClick: Selection callback.
 *
 * Returns:
 *   The candidate card element.
 */
export function CandidateCard({
  candidate,
  isSelected,
  onClick,
}: CandidateCardProps): ReactElement {
  const [posterFailed, setPosterFailed] = useState(false);

  const scorePct = Math.round(Math.min(1, Math.max(0, candidate.score)) * 100);
  const barColor = scoreBarColor(candidate.score);
  const providerLabel =
    PROVIDER_LABEL[candidate.provider] ?? candidate.provider;

  return (
    <Card
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        "cursor-pointer transition-all hover:shadow-md",
        isSelected && "ring-2 ring-primary ring-offset-2",
      )}
    >
      <CardContent className="flex flex-col gap-3 p-3">
        {/* Poster */}
        <div className="relative aspect-[2/3] w-full overflow-hidden rounded-md bg-muted">
          {candidate.poster_url && !posterFailed ? (
            <img
              src={candidate.poster_url}
              alt={`Affiche de ${candidate.title}`}
              loading="lazy"
              onError={() => {
                setPosterFailed(true);
              }}
              className="absolute inset-0 size-full object-cover"
            />
          ) : (
            <div className="flex size-full items-center justify-center text-xs text-muted-foreground">
              Aucune affiche
            </div>
          )}
        </div>

        {/* Title + year */}
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium leading-tight">
            {candidate.title}
          </span>
          {candidate.year != null && (
            <span className="text-xs text-muted-foreground">
              {candidate.year}
            </span>
          )}
        </div>

        {/* Score bar */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-[length:var(--text-2xs)] text-muted-foreground">
              Confiance
            </span>
            <span className="text-[length:var(--text-2xs)] tabular-nums text-muted-foreground">
              {scorePct}&thinsp;%
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full transition-all", barColor)}
              style={{ width: `${String(scorePct)}%` }}
            />
          </div>
        </div>

        {/* Provider badge */}
        <div className="flex items-center justify-between">
          <Badge tone="neutral">{providerLabel}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}
