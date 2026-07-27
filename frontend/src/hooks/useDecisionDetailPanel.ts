/**
 * useDecisionDetailPanel — the data machine behind {@link DecisionDetail}.
 *
 * Owns everything the detail panel needs beyond raw presentation: the local
 * search / selection / run state, the three shared decision mutations (resolve /
 * dismiss / search-override, from {@link useDecisions}) with their per-surface
 * toast + 409/410 handling, and the launch-202 → poll → terminal completion
 * tracker ({@link useRunToCompletion}). The presentation component
 * (``components/decisions/DecisionDetail.tsx``) consumes this hook's result and
 * renders it — no data logic lives in the view layer.
 *
 * Named ``useDecisionDetailPanel`` (not ``useDecisionDetail``) to stay distinct
 * from the {@link useDecisionDetail} *query* hook in {@link useDecisions}, which
 * fetches a single decision by id.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  decisionsKeys,
  type DecisionCandidate,
  type DecisionDetail as DecisionDetailType,
  type ResolveRequest,
} from "@/api/decisions";
import { getPipelineRunDetail, pipelineKeys } from "@/api/pipeline";
import {
  frenchErrorDetail,
  MSG_DECISION_BUSY,
} from "@/components/decisions/errors";
import {
  useDismissDecision,
  useResolveDecision,
  useSearchDecision,
} from "@/hooks/useDecisions";
import {
  isTerminalRunOutcome,
  useRunToCompletion,
} from "@/hooks/useRunToCompletion";

/** Everything {@link DecisionDetail} needs to render + drive the panel. */
export interface DecisionDetailPanelMachine {
  /** Currently selected candidate (for resolve), or ``null``. */
  readonly selectedCandidate: DecisionCandidate | null;
  /** Select a candidate (candidate-card click). */
  readonly setSelectedCandidate: (candidate: DecisionCandidate | null) => void;
  /** Search-override title input value. */
  readonly searchTitle: string;
  /** Set the search-override title. */
  readonly setSearchTitle: (value: string) => void;
  /** Search-override year input value. */
  readonly searchYear: string;
  /** Set the search-override year. */
  readonly setSearchYear: (value: string) => void;
  /** Candidates to render: live-search results override the originals. */
  readonly candidates: readonly DecisionCandidate[];
  /** The resolve ``run_uid``, set on a 202 response, or ``null``. */
  readonly runUid: string | null;
  /** Inline error (409 / 410 / validation), or ``null``. */
  readonly errorDetail: string | null;
  /** ``true`` once the decision has been locally dismissed. */
  readonly dismissed: boolean;
  /** ``true`` once the launched resolve run reached a terminal outcome. */
  readonly runDone: boolean;
  /** The terminal outcome (``success`` / ``error`` / ``killed``), or ``null``. */
  readonly runOutcome: string | null;
  /** ``true`` while the search-override mutation is in flight. */
  readonly isSearchPending: boolean;
  /** ``true`` while the resolve mutation is in flight. */
  readonly isResolvePending: boolean;
  /** ``true`` while the dismiss mutation is in flight. */
  readonly isDismissPending: boolean;
  /** Trigger the search-override mutation (validates the form first). */
  readonly handleSearch: () => void;
  /** Resolve with the given candidate (computes ``via`` provenance). */
  readonly handleResolve: (candidate: DecisionCandidate) => void;
  /** Dismiss the decision. */
  readonly handleDismiss: () => void;
}

/**
 * Drive a single scrape decision's detail panel.
 *
 * Args:
 *   decision: The full decision detail payload.
 *   onDecisionHandled: Called after a successful resolve / dismiss, or after a
 *       410 (superseded) so the parent can deselect / refetch.
 *
 * Returns:
 *   A {@link DecisionDetailPanelMachine} the presentation renders.
 */
export function useDecisionDetailPanel(
  decision: DecisionDetailType,
  onDecisionHandled: () => void,
): DecisionDetailPanelMachine {
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

  /** True once the launched resolve run has reached a terminal outcome. */
  const [runDone, setRunDone] = useState(false);

  /**
   * The terminal outcome of the launched run (``success`` / ``error`` /
   * ``killed``), or ``null`` while still running / not yet launched.  Drives the
   * badge tone + label so a failed run does not masquerade as success (SF1).
   */
  const [runOutcome, setRunOutcome] = useState<string | null>(null);

  // ---- derived --------------------------------------------------------------

  /** Candidates to render: search results override the originals. */
  const candidates = searchResults ?? decision.candidates;

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

  return {
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
    isSearchPending: searchMutation.isPending,
    isResolvePending: resolveMutation.isPending,
    isDismissPending: dismissMutation.isPending,
    handleSearch,
    handleResolve,
    handleDismiss,
  };
}
