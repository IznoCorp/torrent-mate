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

import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { getPipelineRunDetail, pipelineKeys } from "@/api/pipeline";
import {
  isTerminalRunOutcome,
  useRunToCompletion,
} from "@/hooks/useRunToCompletion";
import {
  useDismissDecision,
  useResolveDecision,
  useSearchDecision,
} from "@/hooks/useDecisions";
import type {
  DecisionCandidate,
  DecisionDetail as DecisionDetailType,
  ResolveRequest,
} from "@/api/decisions";
import { decisionsKeys } from "@/api/decisions";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { TRIGGER_LABEL, TRIGGER_TONE } from "@/components/decisions/triggers";
import {
  frenchErrorDetail,
  MSG_DECISION_BUSY,
} from "@/components/decisions/errors";
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

  /** True once the launched resolve run has reached a terminal outcome. */
  const [runDone, setRunDone] = useState(false);

  /**
   * The terminal outcome of the launched run (``success`` / ``error`` /
   * ``killed``), or ``null`` while still running / not yet launched.  Drives the
   * badge tone + label so a failed run does not masquerade as success (SF1).
   */
  const [runOutcome, setRunOutcome] = useState<string | null>(null);

  const triggerLabel = TRIGGER_LABEL[decision.trigger] ?? decision.trigger;
  const triggerExplanation =
    TRIGGER_EXPLANATION[decision.trigger] ??
    `Décision créée (déclencheur : ${decision.trigger}).`;

  /** The year to display in the header (or "—" when unknown). */
  const yearLabel =
    decision.extracted_year != null ? String(decision.extracted_year) : "—";

  // ---- mutations -------------------------------------------------------------

  const searchMutation = useSearchDecision({
    onResults: (data) => {
      setErrorDetail(null);
      setSearchResults(data.candidates);
      // Clear selection when results change.
      setSelectedCandidate(null);
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setErrorDetail(frenchErrorDetail(error));
        if (error.status === 410) {
          toast.error(
            "Cette décision a été remplacée par une version plus récente.",
          );
          void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
          // The detail panel is dead — deselect it like the resolve/dismiss
          // 410 handlers do (F37), instead of leaving it open re-toasting 410.
          onDecisionHandled();
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

  const resolveMutation = useResolveDecision({
    onResolved: (data) => {
      setErrorDetail(null);
      setRunUid(data.run_uid);
      setRunDone(false);
      toast.success("Résolu — le média poursuit son pipeline jusqu'au dispatch.");
      // The UNION invalidation set (decisions + pipeline history + Flow Board +
      // staging) already fired in the shared hook — an optimistic refresh at the
      // 202. The row is still 'pending' until the detached runner marks it
      // resolved; the completion poll below fires a second decisions
      // invalidation once the run is terminal (F19/F49).
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        if (error.status === 409) {
          // Since the resolve queue (2026-07-15) a held pipeline.lock never
          // 409s — the runner waits, visibly. The only remaining 409 is the
          // same-decision idempotence guard.
          toast.error(MSG_DECISION_BUSY);
        } else if (error.status === 410) {
          toast.error(
            "Cette décision a été remplacée par une version plus récente.",
          );
          void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
          onDecisionHandled();
        } else {
          toast.error(error.detail);
        }
        setErrorDetail(frenchErrorDetail(error));
      } else {
        toast.error("Erreur inattendue lors du re-scraping.");
      }
    },
  });

  const dismissMutation = useDismissDecision({
    onDismissed: () => {
      toast.success("Décision ignorée.");
      // The decisions list/badge invalidation fired in the shared hook so the
      // dismissed row leaves the queue immediately (F01).
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
        } else if (error.status === 409) {
          toast.error("Cette décision n'est plus en attente.");
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

  // ---- resolve-run completion poll (F19/F49) --------------------------------
  // Poll the launched run's history row (the shared launch-202 → poll → terminal
  // machine); when it reaches a terminal outcome, re-invalidate the decisions
  // list (the row is now really resolved) and flip the in-progress badge. Stops
  // polling once terminal — and, via ``stopOnError``, also once the GET
  // persistently errors so a 404 (row never written) does not poll forever (SF1
  // stuck-poll guard). ``onTerminal`` / ``onError`` share one fire-once latch.
  useRunToCompletion({
    queryKey: pipelineKeys.historyDetail(runUid),
    queryFn: () => getPipelineRunDetail(runUid ?? ""),
    enabled: runUid != null && !runDone,
    // Do not retry a failing run-detail GET forever — surface it via the
    // stopOnError guard so the 2s poll halts instead of hammering a dead row.
    retry: 2,
    stopOnError: true,
    intervalMs: 2000,
    isTerminal: (data) => isTerminalRunOutcome(data?.outcome),
    onTerminal: (data) => {
      setRunDone(true);
      setRunOutcome(data.outcome ?? null);
      // SF1: a terminal FAILURE (error/killed) must not look like success —
      // fire a single error toast alongside the danger badge below.
      if (data.outcome !== "success") {
        toast.error(
          "Le re-scraping a échoué. Consultez le journal ci-dessous.",
        );
      }
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
    },
    onError: () => {
      // If the run-detail GET persistently errors (e.g. the run row was never
      // written → 404), surface a failure instead of spinning the "en cours"
      // badge forever.
      setRunDone(true);
      setRunOutcome("error");
      toast.error(
        "Impossible de suivre le re-scraping (statut indisponible). Réessayez.",
      );
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
      searchMutation.mutate({ id: decision.id, body: { title: trimmed, year } });
    } else {
      searchMutation.mutate({
        id: decision.id,
        body: { title: trimmed, year: null },
      });
    }
  }

  /** Resolve with the given candidate. */
  function handleResolve(candidate: DecisionCandidate): void {
    setSelectedCandidate(candidate);
    setErrorDetail(null);
    // A candidate present in the live-search results was found via the
    // search-override flow; otherwise it was picked from the queue snapshot
    // (F09 — persisted in resolution_json.via).
    const via: ResolveRequest["via"] =
      searchResults?.some(
        (c) =>
          c.provider === candidate.provider &&
          c.provider_id === candidate.provider_id,
      ) === true
        ? "search_override"
        : "pick";
    resolveMutation.mutate({
      id: decision.id,
      body: {
        provider: candidate.provider,
        provider_id: candidate.provider_id,
        via,
      },
    });
  }

  /** Dismiss the decision. */
  function handleDismiss(): void {
    setErrorDetail(null);
    dismissMutation.mutate(decision.id);
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
