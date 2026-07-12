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

import { useMutation, useQueryClient } from "@tanstack/react-query";
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
  dismissDecision,
  resolveDecision,
  searchDecisionCandidates,
  type DecisionCandidate,
  type ResolveRequest,
} from "@/api/decisions";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { TRIGGER_LABEL, TRIGGER_TONE } from "@/components/decisions/triggers";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { Kbd } from "@/components/ds/Kbd";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDecisionDetail, useDecisions } from "@/hooks/useDecisions";

/** Whether the current focus is a text field (so shortcuts don't hijack typing). */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || target.isContentEditable;
}

/**
 * ResolutionDeck — one-at-a-time keyboard resolution of pending decisions.
 *
 * Returns:
 *   The resolution deck element.
 */
export function ResolutionDeck(): ReactElement {
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
  const clampedCursor = visible.length === 0 ? 0 : Math.min(cursor, visible.length - 1);
  const current = visible[clampedCursor];
  const currentId = current?.id;

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

  // Reset per-decision state whenever the current decision changes.
  useEffect(() => {
    setOverrides([]);
    setSelected(0);
    setSearchTitle(current?.extracted_title ?? "");
    setSearchYear(current?.extracted_year != null ? String(current.extracted_year) : "");
  }, [currentId, current?.extracted_title, current?.extracted_year]);

  const markProcessed = useCallback(
    (id: number) => {
      setProcessed((prev) => new Set(prev).add(id));
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
    },
    [queryClient],
  );

  const resolveMut = useMutation({
    mutationFn: (vars: { id: number; body: ResolveRequest }) =>
      resolveDecision(vars.id, vars.body),
    onSuccess: (_data, vars) => {
      toast.success("Décision validée — re-scraping lancé");
      markProcessed(vars.id);
    },
    onError: (err: unknown) => {
      toast.error(
        err instanceof Error ? err.message : "Échec de la validation",
      );
    },
  });

  const dismissMut = useMutation({
    mutationFn: (id: number) => dismissDecision(id),
    onSuccess: (_data, id) => {
      toast.success("Décision ignorée — dossier laissé tel quel");
      markProcessed(id);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Échec de l'action");
    },
  });

  const searchMut = useMutation({
    mutationFn: (vars: { id: number; title: string; year: number | null }) =>
      searchDecisionCandidates(vars.id, {
        title: vars.title,
        ...(vars.year != null ? { year: vars.year } : {}),
      }),
    onSuccess: (data) => {
      setOverrides(data.candidates);
      setSelected(baseCandidates.length);
      toast.success(
        `${String(data.candidates.length)} résultat(s) trouvé(s)`,
      );
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
    setCursor((c) => c + 1);
  }, []);

  const handleSearchSubmit = useCallback(
    (e: SyntheticEvent) => {
      e.preventDefault();
      if (current == null || searchTitle.trim() === "") return;
      const yearNum = Number.parseInt(searchYear, 10);
      searchMut.mutate({
        id: current.id,
        title: searchTitle.trim(),
        year: Number.isFinite(yearNum) ? yearNum : null,
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

  // ── Deck ───────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-4">
      {/* Header: extracted media + trigger + progress + shortcuts */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold">
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
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
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
        <Button type="submit" variant="outline" disabled={searchMut.isPending}>
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
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {candidates.map((candidate, idx) => (
            <CandidateCard
              key={`${candidate.provider}-${String(candidate.provider_id)}-${String(idx)}`}
              candidate={candidate}
              isSelected={idx === selected}
              onClick={() => {
                setSelected(idx);
              }}
            />
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={handleResolve}
          disabled={busy || candidates.length === 0}
        >
          Valider le choix
        </Button>
        <Button variant="outline" onClick={handleDismiss} disabled={busy}>
          Ignorer
        </Button>
        <Button variant="ghost" onClick={handleSkip} disabled={busy}>
          Passer
        </Button>
      </div>
    </div>
  );
}
