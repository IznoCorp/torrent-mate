/**
 * DecisionDetail — the full-detail panel for a single scrape decision.
 *
 * Displays the extracted title/year, trigger explanation, a grid of candidate
 * cards (reusing {@link CandidateCard}), a search-override form that replaces
 * candidates live, and action buttons ("Choisir" / "Ignorer").
 *
 * On resolve success, renders {@link RunLogFeed} with the returned ``run_uid``.
 * All data logic — the local state, the three shared decision mutations with
 * their 409/410 handling, and the launch-202 → poll → terminal completion
 * tracker — lives in {@link useDecisionDetailPanel}; this component is pure
 * presentation over that machine.
 */

import { type ReactElement } from "react";

import type { DecisionDetail as DecisionDetailType } from "@/api/decisions";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { TRIGGER_LABEL, TRIGGER_TONE } from "@/components/decisions/triggers";
import { RunLogFeed } from "@/components/pipeline/RunLogFeed";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDecisionDetailPanel } from "@/hooks/useDecisionDetailPanel";

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
 * Non-``pending`` decision status → its read-only result presentation.
 *
 * A decision that has already been handled (resolved / dismissed / superseded)
 * must NOT re-offer the candidate picker + "Choisir" (that let an operator
 * re-scrape an already-decided item and hit a confusing "not pending" 409).
 * Instead the detail shows this read-only outcome.
 */
const STATUS_RESULT: Record<
  string,
  { tone: "success" | "neutral" | "warning"; label: string; desc: string }
> = {
  resolved: {
    tone: "success",
    label: "Résolue",
    desc: "Un candidat a été choisi et le re-scraping ciblé a été lancé pour ce dossier.",
  },
  dismissed: {
    tone: "neutral",
    label: "Ignorée",
    desc: "Cette décision a été ignorée — le résultat du scraping automatique est conservé.",
  },
  superseded: {
    tone: "warning",
    label: "Remplacée",
    desc: "Cette décision a été remplacée par une version plus récente du dossier.",
  },
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
  const {
    selectedCandidate,
    setSelectedCandidate,
    searchTitle,
    setSearchTitle,
    searchYear,
    setSearchYear,
    candidates,
    runUid,
    errorDetail,
    dismissed,
    runDone,
    runOutcome,
    isSearchPending,
    isResolvePending,
    isDismissPending,
    handleSearch,
    handleResolve,
    handleDismiss,
  } = useDecisionDetailPanel(decision, onDecisionHandled);

  // ---- derived display -------------------------------------------------------

  const triggerLabel = TRIGGER_LABEL[decision.trigger] ?? decision.trigger;
  const triggerExplanation =
    TRIGGER_EXPLANATION[decision.trigger] ??
    `Décision créée (déclencheur : ${decision.trigger}).`;

  /** The year to display in the header (or "—" when unknown). */
  const yearLabel =
    decision.extracted_year != null ? String(decision.extracted_year) : "—";

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

  // A non-pending decision is read-only: show its outcome, never the picker
  // (issue: an already-resolved decision must show the result, not offer a
  // re-scrape that fails with a "not pending" 409).
  if (decision.status !== "pending") {
    const meta = STATUS_RESULT[decision.status] ?? {
      tone: "neutral" as const,
      label: decision.status,
      desc: "Cette décision a déjà été traitée.",
    };
    const resolution = decision.resolution_json as {
      provider?: string;
      provider_id?: number;
      via?: string;
    } | null;
    return (
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="min-w-0 break-words text-lg">
              {decision.extracted_title}{" "}
              <span className="font-normal text-muted-foreground">
                ({yearLabel})
              </span>
            </CardTitle>
            <Badge tone={meta.tone}>{meta.label}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">{meta.desc}</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {decision.status === "resolved" && resolution?.provider != null && (
            <div className="rounded-md border border-border bg-muted p-3 text-sm">
              <p className="font-medium">Correspondance retenue</p>
              <p className="mt-1 text-muted-foreground">
                {resolution.provider.toUpperCase()}
                {resolution.provider_id != null
                  ? ` #${String(resolution.provider_id)}`
                  : ""}
                {resolution.via != null
                  ? ` — ${resolution.via === "search_override" ? "recherche manuelle" : "sélection"}`
                  : ""}
              </p>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Pour relancer un scraping sur ce dossier, passez par la maintenance
            (re-scrape ciblé) — cette décision est clôturée.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="min-w-0 break-words text-lg">
            {decision.extracted_title}{" "}
            <span className="font-normal text-muted-foreground">
              ({yearLabel})
            </span>
          </CardTitle>
          <Badge tone={TRIGGER_TONE[decision.trigger] ?? "info"}>
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
                disabled={isSearchPending}
                onClick={handleSearch}
              >
                {isSearchPending ? "Recherche..." : "Re-chercher"}
              </Button>
            </div>
          </div>
        </div>

        {/* ---- Error display ------------------------------------------------- */}
        {errorDetail != null && (
          <div className="rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
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
              {/* SF1: a terminal FAILURE (error/killed) shows a danger badge —
                  it must not look like the success "terminé" state. */}
              {(() => {
                if (!runDone) {
                  return (
                    <Badge tone="success" dot>
                      Re-scraping en cours
                    </Badge>
                  );
                }
                if (runOutcome != null && runOutcome !== "success") {
                  return <Badge tone="danger">Re-scraping échoué</Badge>;
                }
                return <Badge tone="success">Re-scraping terminé</Badge>;
              })()}
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
            disabled={isDismissPending || isResolvePending}
            onClick={handleDismiss}
          >
            {isDismissPending ? "En cours..." : "Ignorer"}
          </Button>

          <Button
            type="button"
            disabled={
              selectedCandidate === null || isResolvePending || isDismissPending
            }
            onClick={() => {
              if (selectedCandidate != null) handleResolve(selectedCandidate);
            }}
          >
            {isResolvePending ? "Lancement..." : "Choisir"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
