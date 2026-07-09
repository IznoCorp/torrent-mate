/**
 * DecisionDetail — the full-detail panel for a single scrape decision.
 *
 * Displays the extracted title/year, trigger explanation, a grid of candidate
 * cards (reusing {@link CandidateCard}), a search-override form that replaces
 * candidates live, and action buttons ("Choisir" / "Ignorer").
 *
 * On resolve success, renders {@link RunLogFeed} with the returned ``run_uid``.
 * All backend errors surface via ``sonner`` toasts, with dedicated handling for
 * 409 (lock-held retry hint) and 410 (superseded — refetch list).
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import type {
  DecisionCandidate,
  DecisionDetail as DecisionDetailType,
  ResolveResponse,
  SearchResponse,
} from "@/api/decisions";
import {
  decisionsKeys,
  resolveDecision,
  searchDecisionCandidates,
  dismissDecision,
} from "@/api/decisions";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { RunLogFeed } from "@/components/pipeline/RunLogFeed";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Trigger → French explanation text.
 *
 * Each value explains *why* the decision was created so the operator can make
 * an informed choice during resolution.
 */
const TRIGGER_EXPLANATION: Record<string, string> = {
  below_threshold:
    "Le score de confiance du scraping automatique est trop faible. " +
    "Choisissez un candidat pour relancer un scraping ciblé, ou ignorez " +
    "la décision si le dossier doit être traité manuellement.",
  mid_band:
    "Le score de confiance est dans la zone grise — le résultat automatique " +
    "est plausible mais pas certain. Vérifiez les candidats et choisissez le " +
    "bon, ou ignorez pour conserver le résultat automatique.",
  ambiguous:
    "Plusieurs correspondances sont possibles pour ce dossier. " +
    "Sélectionnez le bon candidat parmi les propositions, ou utilisez la " +
    "recherche pour trouver une correspondance plus précise.",
};

/**
 * Trigger → French label.
 *
 * Mirrors the labels in {@link ../DecisionList.tsx} for consistency.
 */
const TRIGGER_LABEL: Record<string, string> = {
  below_threshold: "Score faible",
  mid_band: "Zone grise",
  ambiguous: "Ambigu",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Props for {@link DecisionDetail}. */
export interface DecisionDetailProps {
  /** The full decision detail payload from the API. */
  readonly decision: DecisionDetailType;
  /** Called when the decision has been resolved or dismissed (remove from list). */
  readonly onDecisionHandled: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * DecisionDetail — inspect and act on a single scrape decision.
 *
 * Layout (mobile-first, stacked):
 *
 * 1. Header: extracted title + year, trigger badge, trigger explanation.
 * 2. Search override form: title + year inputs, "Re-chercher" button.
 * 3. Candidate grid (2 cols mobile, 3 desktop).
 * 4. Action bar: "Choisir" (resolve selected) + "Ignorer" (dismiss).
 * 5. Live output: {@link RunLogFeed} with the resolve ``run_uid``.
 *
 * Args:
 *   decision: The full decision detail from ``useDecisionDetail``.
 *   onDecisionHandled: Called after a successful resolve or dismiss so the
 *       parent can deselect or refetch.
 *
 * Returns:
 *   The decision-detail element.
 */
export function DecisionDetail({
  decision,
  onDecisionHandled,
}: DecisionDetailProps): ReactElement {
  const queryClient = useQueryClient();

  // ---- local state ----------------------------------------------------------

  /** Currently selected candidate (for resolve). */
  const [selectedCandidate, setSelectedCandidate] =
    useState<DecisionCandidate | null>(null);

  /** Search override form values. */
  const [searchTitle, setSearchTitle] = useState(decision.extracted_title);
  const [searchYear, setSearchYear] = useState(
    decision.extracted_year != null ? String(decision.extracted_year) : "",
  );

  /**
   * Ephemeral search results, or ``null`` when the original candidates should
   * be displayed.
   */
  const [searchResults, setSearchResults] = useState<
    DecisionCandidate[] | null
  >(null);

  /** The resolve run_uid, set on a 202 response. */
  const [runUid, setRunUid] = useState<string | null>(null);

  /** Inline error (409 / 410 / validation), cleared on next action. */
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  /** Whether the decision has been locally dismissed. */
  const [dismissed, setDismissed] = useState(false);

  // ---- derived --------------------------------------------------------------

  /** Candidates to render: search results override the originals. */
  const candidates = searchResults ?? decision.candidates;

  const triggerLabel = TRIGGER_LABEL[decision.trigger] ?? decision.trigger;
  const triggerExplanation =
    TRIGGER_EXPLANATION[decision.trigger] ??
    `Décision créée (déclencheur : ${decision.trigger}).`;

  /** The year to display in the header (or "—" when unknown). */
  const yearLabel =
    decision.extracted_year != null ? String(decision.extracted_year) : "—";

  // ---- mutations -------------------------------------------------------------

  const searchMutation = useMutation<
    SearchResponse,
    Error,
    { title: string; year?: number | null }
  >({
    mutationFn: ({ title, year: yr }) =>
      searchDecisionCandidates(decision.id, {
        title,
        year: yr ?? null,
      }),
    onSuccess: (data) => {
      setErrorDetail(null);
      setSearchResults(data.candidates);
      // Clear selection when results change.
      setSelectedCandidate(null);
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setErrorDetail(error.detail);
        if (error.status === 410) {
          toast.error(
            "Cette décision a été remplacée par une version plus récente.",
          );
          void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
        } else if (error.status === 502) {
          toast.error(
            "Le fournisseur de métadonnées est indisponible. Réessayez plus tard.",
          );
        } else {
          toast.error(error.detail);
        }
      } else {
        setErrorDetail("Erreur inattendue lors de la recherche.");
      }
    },
  });

  const resolveMutation = useMutation<
    ResolveResponse,
    Error,
    DecisionCandidate
  >({
    mutationFn: (candidate) =>
      resolveDecision(decision.id, {
        provider: candidate.provider,
        provider_id: candidate.provider_id,
      }),
    onSuccess: (data) => {
      setErrorDetail(null);
      setRunUid(data.run_uid);
      toast.success("Re-scraping lancé.");
      // Invalidate decisions list so the resolved item disappears.
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", "history"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        if (error.status === 409) {
          toast.error(
            "Un autre re-scraping est déjà en cours. " +
              "Attendez qu'il se termine avant de réessayer.",
          );
        } else if (error.status === 410) {
          toast.error(
            "Cette décision a été remplacée par une version plus récente.",
          );
          void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
          onDecisionHandled();
        } else {
          toast.error(error.detail);
        }
        setErrorDetail(error.detail);
      } else {
        toast.error("Erreur inattendue lors du re-scraping.");
      }
    },
  });

  const dismissMutation = useMutation({
    mutationFn: () => dismissDecision(decision.id),
    onSuccess: () => {
      toast.success("Décision ignorée.");
      setDismissed(true);
      onDecisionHandled();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        if (error.status === 410) {
          toast.error(
            "Cette décision a été remplacée par une version plus récente.",
          );
          void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
          onDecisionHandled();
        } else {
          toast.error(error.detail);
        }
      } else {
        toast.error("Erreur inattendue.");
      }
    },
  });

  // ---- event handlers --------------------------------------------------------

  /** Trigger the search-override mutation. */
  function handleSearch(): void {
    const trimmed = searchTitle.trim();
    if (trimmed === "") {
      setErrorDetail("Le titre de recherche ne peut pas être vide.");
      return;
    }
    const yearStr = searchYear.trim();
    if (yearStr !== "") {
      const year = Number(yearStr);
      if (Number.isNaN(year) || year < 0) {
        setErrorDetail("L'année doit être un nombre valide.");
        return;
      }
      searchMutation.mutate({ title: trimmed, year });
    } else {
      searchMutation.mutate({ title: trimmed, year: null });
    }
  }

  /** Resolve with the given candidate. */
  function handleResolve(candidate: DecisionCandidate): void {
    setSelectedCandidate(candidate);
    setErrorDetail(null);
    resolveMutation.mutate(candidate);
  }

  /** Dismiss the decision. */
  function handleDismiss(): void {
    setErrorDetail(null);
    dismissMutation.mutate();
  }

  // ---- render ----------------------------------------------------------------

  if (dismissed) {
    return (
      <Card>
        <CardContent className="p-4">
          <p className="text-sm text-muted-foreground">
            Cette décision a été ignorée.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-lg">
            {decision.extracted_title}{" "}
            <span className="font-normal text-muted-foreground">
              ({yearLabel})
            </span>
          </CardTitle>
          <Badge
            tone={
              decision.trigger === "below_threshold"
                ? "danger"
                : decision.trigger === "mid_band"
                  ? "warning"
                  : "info"
            }
          >
            {triggerLabel}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{triggerExplanation}</p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* ---- Search override form ------------------------------------------ */}
        <div className="flex flex-col gap-3 rounded-md border border-border bg-muted p-3">
          <p className="text-xs font-medium text-muted-foreground">
            Recherche manuelle
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_auto]">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="search-title">Titre</Label>
              <Input
                id="search-title"
                type="text"
                value={searchTitle}
                onChange={(e) => {
                  setSearchTitle(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSearch();
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="search-year">Année</Label>
              <Input
                id="search-year"
                type="number"
                value={searchYear}
                onChange={(e) => {
                  setSearchYear(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSearch();
                }}
                className="w-24"
              />
            </div>
            <div className="flex items-end">
              <Button
                type="button"
                variant="outline"
                disabled={searchMutation.isPending}
                onClick={handleSearch}
              >
                {searchMutation.isPending ? "Recherche..." : "Re-chercher"}
              </Button>
            </div>
          </div>
        </div>

        {/* ---- Error display ------------------------------------------------- */}
        {errorDetail != null && (
          <div className="rounded-md border border-[color-mix(in_oklch,var(--danger)_34%,transparent)] bg-[color-mix(in_oklch,var(--danger)_12%,transparent)] p-3 text-sm text-[var(--danger)]">
            {errorDetail}
          </div>
        )}

        {/* ---- Candidate grid ------------------------------------------------ */}
        {candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun candidat disponible pour cette décision.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {candidates.map((candidate, idx) => {
              const isSelected =
                selectedCandidate?.provider === candidate.provider &&
                selectedCandidate.provider_id === candidate.provider_id;
              return (
                <CandidateCard
                  key={`${candidate.provider}-${String(candidate.provider_id)}-${String(idx)}`}
                  candidate={candidate}
                  isSelected={isSelected}
                  onClick={() => {
                    setSelectedCandidate(candidate);
                  }}
                />
              );
            })}
          </div>
        )}

        {/* ---- Live resolve output ------------------------------------------- */}
        {runUid != null && (
          <div className="flex flex-col gap-2 rounded-md border border-border bg-muted p-3">
            <div className="flex items-center gap-2">
              <Badge tone="success" dot>
                Re-scraping en cours
              </Badge>
              <span className="text-xs text-muted-foreground">
                run_uid : <span className="font-mono">{runUid}</span>
              </span>
            </div>
            <RunLogFeed runUid={runUid} />
          </div>
        )}

        {/* ---- Action buttons ------------------------------------------------ */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
          <Button
            type="button"
            variant="outline"
            disabled={dismissMutation.isPending || resolveMutation.isPending}
            onClick={handleDismiss}
          >
            {dismissMutation.isPending ? "En cours..." : "Ignorer"}
          </Button>

          <Button
            type="button"
            disabled={
              selectedCandidate === null ||
              resolveMutation.isPending ||
              dismissMutation.isPending
            }
            onClick={() => {
              if (selectedCandidate != null) handleResolve(selectedCandidate);
            }}
          >
            {resolveMutation.isPending ? "Lancement..." : "Choisir"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
