/**
 * FlowBoard — the living-pipeline visualization (P0-A).
 *
 * A horizontal board of eight stage "stations" (Arrivée → Dispatch), each a
 * {@link StageStation} showing the CURRENT STOCK of media at that position
 * (single-position axiom — one media, one station). Data comes from
 * {@link usePipelineStages} (``GET /api/pipeline/stages``), refreshed live
 * off the WS stream; the last run's throughput lives in the header caption,
 * never on the stations. Clicking a station opens a {@link Sheet} drawer that
 * is URL-addressable (``?stage=<key>`` — Back closes it, deep links restore
 * it), listing exactly the media at that position.
 */

import {
  ArrowDownUp,
  ChevronRight,
  Clapperboard,
  Download,
  Send,
  ShieldCheck,
  Sparkles,
  Tags,
  Target,
  type LucideIcon,
} from "lucide-react";
import {
  Fragment,
  useCallback,
  useEffect,
  useState,
  type ReactElement,
} from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import type { StagesResponse } from "@/api/client";
import { ErrorState } from "@/components/ds/ErrorState";
import {
  StageStation,
  type StageSplit,
  type StageState,
} from "@/components/ds/StageStation";
import { StatusBadge, type StatusTone } from "@/components/ds/StatusBadge";
import { triggerLabel } from "@/components/pipeline/triggers";
import {
  StageMediaList,
  type StageKey,
} from "@/components/staging/StageMediaList";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { usePipelineStages } from "@/hooks/usePipelineStages";

/** One stage as returned by ``GET /api/pipeline/stages``. */
type ApiStage = StagesResponse["stages"][number];

/** Per-stage icon, keyed by the stable stage ``key`` (eight stations). */
const STAGE_ICON: Record<string, LucideIcon> = {
  arrival: Download,
  sorting: ArrowDownUp,
  cleaning: Sparkles,
  matching: Target,
  scraping: Tags,
  trailers: Clapperboard,
  verify: ShieldCheck,
  dispatch: Send,
};

/** One-line French description of what each stage does (drawer body). */
const STAGE_DESC: Record<string, string> = {
  arrival: "Intégrés depuis le client torrent, en attente de tri.",
  sorting: "Les médias sont rangés et nommés dans leur catégorie.",
  cleaning: "Les fichiers et dossiers parasites sont supprimés.",
  matching: "Les médias non identifiés attendent une décision de votre part.",
  scraping: "Les métadonnées, jaquettes et NFO sont récupérées.",
  trailers: "Les bandes-annonces sont téléchargées quand elles existent.",
  verify: "La conformité finale est vérifiée avant le dispatch.",
  dispatch: "Les médias vérifiés partent vers le stockage définitif.",
};

/** state → (tone, French label) for the drawer status badge (stock model). */
const STATE_BADGE: Record<StageState, { tone: StatusTone; label: string }> = {
  idle: { tone: "neutral", label: "Vide" },
  ok: { tone: "info", label: "En attente" },
  active: { tone: "info", label: "En cours" },
  attention: { tone: "warning", label: "Attention requise" },
  blocked: { tone: "danger", label: "Bloqué" },
};

/** run_state → (tone, French label) for the board header badge. */
const RUN_STATE_BADGE: Record<
  StagesResponse["run_state"],
  { tone: StatusTone; label: string }
> = {
  idle: { tone: "neutral", label: "Au repos" },
  running: { tone: "info", label: "En cours" },
  paused: { tone: "warning", label: "En pause" },
};

/** Relative "il y a …" label for a past epoch-seconds instant. */
function agoLabel(epochSec: number): string {
  const mins = Math.max(0, Math.round(Date.now() / 1000 - epochSec) / 60);
  if (mins < 1) return "à l'instant";
  if (mins < 60) return `il y a ${String(Math.round(mins))} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `il y a ${String(hours)} h`;
  return `il y a ${String(Math.round(hours / 24))} j`;
}

/** The board's run-provenance caption ("Run en cours" / "Dernier run · …").
 *  Carries the last run's throughput (P0-A.3 — it lives here, never on the
 *  stations). The trigger label reuses the canonical {@link triggerLabel} map. */
function runCaption(
  data: StagesResponse | undefined,
  running: boolean,
): string {
  if (running) return "Run en cours";
  if (data?.updated_at == null) return "Aucun run enregistré";
  const processed =
    data.run_processed != null
      ? ` · ${String(data.run_processed)} média${data.run_processed > 1 ? "s" : ""} traité${data.run_processed > 1 ? "s" : ""}`
      : "";
  const trig = data.run_trigger
    ? ` · déclenché par ${triggerLabel(data.run_trigger).toLowerCase()}`
    : "";
  return `Dernier run · ${agoLabel(data.updated_at)}${processed}${trig}`;
}

/** Map an API stage's split to the {@link StageStation} split prop shape. */
function toStationSplit(
  split: ApiStage["split"],
): readonly StageSplit[] | null {
  if (split === null || split === undefined || split.length === 0) {
    return null;
  }
  return split.map((s) => ({
    label: s.label,
    count: s.count,
    tone: s.tone,
  }));
}

/**
 * FlowBoard — the pipeline Flow Board with a per-stage detail drawer.
 *
 * Returns:
 *   The Flow Board element.
 */
export function FlowBoard(): ReactElement {
  const query = usePipelineStages();
  // sm: breakpoint (640px) drives compact vs sm-size variant. Guarded for
  // jsdom where matchMedia may be absent or return a stub without addEventListener.
  const [isDesktop, setIsDesktop] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    try {
      return window.matchMedia("(min-width: 40em)").matches;
    } catch {
      return true;
    }
  });
  useEffect(() => {
    try {
      const mql = window.matchMedia("(min-width: 40em)");
      const handler = (e: MediaQueryListEvent) => {
        setIsDesktop(e.matches);
      };
      mql.addEventListener("change", handler);
      return () => {
        mql.removeEventListener("change", handler);
      };
    } catch {
      // jsdom or environments without matchMedia — leave as-is.
      return;
    }
  }, []);
  const navigate = useNavigate();
  // The open stage drawer is URL-addressable (?stage=<key>) so the browser
  // Back button closes it like any route — same discipline as ?media/?decision
  // (open pushes a history entry; close replaces it, no dangling entry).
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedKey = searchParams.get("stage");
  const openStage = useCallback(
    (key: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("stage", key);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );
  const closeStage = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("stage");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);

  if (query.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 pb-2 sm:flex-row sm:flex-wrap sm:gap-2"
        aria-busy="true"
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton
            key={`stage-sk-${String(i)}`}
            className="h-20 w-full sm:h-28 sm:w-auto sm:min-w-36"
          />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        title="Impossible de charger le flux du pipeline"
        {...(query.error instanceof Error
          ? { message: query.error.message }
          : {})}
        onRetry={() => {
          void query.refetch();
        }}
      />
    );
  }

  const data = query.data;
  const stages: readonly ApiStage[] = data?.stages ?? [];

  // Defensive: a settled query that yielded no stages (undefined data / a
  // truncated response) must never paint a blank board — fall back to the
  // skeleton so the section reads as "loading", not "broken".
  if (stages.length === 0) {
    return (
      <div
        className="flex flex-col gap-2 pb-2 sm:flex-row sm:flex-wrap sm:gap-2"
        aria-busy="true"
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton
            key={`stage-empty-sk-${String(i)}`}
            className="h-20 w-full sm:h-28 sm:w-auto sm:min-w-36"
          />
        ))}
      </div>
    );
  }

  const runBadge = data
    ? RUN_STATE_BADGE[data.run_state]
    : RUN_STATE_BADGE.idle;
  const selected = stages.find((s) => s.key === selectedKey) ?? null;

  // Run context drives the connectors + station shimmer: during a run, the
  // connector entering the active stage animates (flow), passed connectors are
  // solid ambre, later ones stay neutral. At rest the board is calm.
  const running = data?.run_state === "running";
  const activeIndex = stages.findIndex((s) => s.state === "active");

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Flux du pipeline
          </h2>
          <span className="text-[length:var(--text-2xs)] text-muted-foreground/80">
            {runCaption(data, running)}
          </span>
        </div>
        <StatusBadge tone={runBadge.tone} label={runBadge.label} />
      </div>

      {/* Mobile: vertical list (readable + tappable, no lateral scroll).
          Desktop: horizontal wrapping row — stations wrap instead of
          overflowing so the anomaly signal is always visible (DOIT-2, §8). */}
      <div className="flex flex-col gap-2 pb-2 sm:flex-row sm:flex-wrap sm:items-stretch sm:gap-1">
        {stages.map((stage, i) => {
          const split = toStationSplit(stage.split);
          const icon = STAGE_ICON[stage.key];
          // Every station shows current stock (P0-A.3) — one caption for all.
          const timeframe = stage.count > 0 ? "en attente" : undefined;
          const conn: "flow" | "done" | "todo" =
            running && activeIndex >= 0
              ? i + 1 === activeIndex
                ? "flow"
                : i + 1 < activeIndex
                  ? "done"
                  : "todo"
              : "todo";
          return (
            <Fragment key={stage.key}>
              <StageStation
                label={stage.label}
                count={stage.count}
                state={stage.state}
                blocked={stage.blocked}
                // Desktop: compact quiet stations (idle/ok) only show icon+count
                // so the rail never overflows. Anomalous always stay expanded.
                // Mobile: sm-sized rows (~40 px) with full labels visible.
                compact={isDesktop}
                onClick={() => {
                  openStage(stage.key);
                }}
                {...(timeframe !== undefined ? { timeframe } : {})}
                {...(icon !== undefined ? { icon } : {})}
                {...(split !== null ? { split } : {})}
                {...(isDesktop ? {} : ({ size: "sm" } as const))}
              />
              {i < stages.length - 1 &&
                (running ? (
                  // During a run: a flow rail (vertical on mobile, horizontal on sm+).
                  <div
                    className="flex shrink-0 items-center justify-center self-center py-0.5 sm:py-0"
                    aria-hidden="true"
                  >
                    {conn === "flow" ? (
                      <>
                        <span className="ps-flow-line-vertical h-4 w-0.5 rounded-full sm:hidden" />
                        <span className="ps-flow-line hidden h-0.5 w-6 rounded-full sm:block" />
                      </>
                    ) : conn === "done" ? (
                      <>
                        <span className="h-4 w-0.5 rounded-full bg-primary/50 sm:hidden" />
                        <span className="hidden h-0.5 w-6 rounded-full bg-primary/50 sm:block" />
                      </>
                    ) : (
                      <>
                        <span className="h-4 w-0.5 rounded-full bg-border sm:hidden" />
                        <ChevronRight className="hidden size-4 text-muted-foreground/40 sm:block" />
                      </>
                    )}
                  </div>
                ) : (
                  // At rest: a subtle chevron on the horizontal (sm+) flow only.
                  <div
                    className="hidden shrink-0 items-center self-center text-muted-foreground/40 sm:flex"
                    aria-hidden="true"
                  >
                    <ChevronRight className="size-4" />
                  </div>
                ))}
            </Fragment>
          );
        })}
      </div>

      <Sheet
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) {
            closeStage();
          }
        }}
      >
        <SheetContent className="flex w-full flex-col gap-4 overflow-y-auto px-6 pb-6 sm:max-w-md">
          {selected !== null && (
            <>
              <SheetHeader className="pr-8">
                <div className="flex flex-wrap items-center gap-2">
                  <SheetTitle>{selected.label}</SheetTitle>
                  <StatusBadge
                    tone={STATE_BADGE[selected.state].tone}
                    label={STATE_BADGE[selected.state].label}
                  />
                </div>
                <SheetDescription>
                  {STAGE_DESC[selected.key] ?? ""}
                </SheetDescription>
              </SheetHeader>

              <div className="flex items-baseline gap-2">
                <span className="font-mono text-4xl font-semibold tabular-nums">
                  {selected.count}
                </span>
                <span className="text-sm text-muted-foreground">
                  à cette étape
                </span>
              </div>

              {toStationSplit(selected.split) !== null && (
                <ul className="flex flex-col gap-1 text-sm">
                  {(toStationSplit(selected.split) ?? []).map((s) => (
                    <li
                      key={s.label}
                      className="flex items-center justify-between gap-2 border-b border-border/60 py-1 last:border-b-0"
                    >
                      <span className="text-muted-foreground">{s.label}</span>
                      <span className="font-mono tabular-nums">{s.count}</span>
                    </li>
                  ))}
                </ul>
              )}

              {selected.blocked > 0 && (
                <p className="text-sm text-danger">
                  {selected.blocked} média{selected.blocked > 1 ? "s" : ""}{" "}
                  bloqué{selected.blocked > 1 ? "s" : ""} à cette étape — le
                  détail ci-dessous donne la raison et l'action.
                </p>
              )}

              {selected.key === "matching" && selected.count > 0 && (
                <Button
                  onClick={() => {
                    void navigate("/medias");
                  }}
                >
                  <Target className="size-4" aria-hidden="true" />
                  Ouvrir la file de résolution
                </Button>
              )}

              {/* Per-media drill-down: the staged media at/awaiting this stage,
                  each expanding to its full pipeline timeline (OBJ1 tail). */}
              <div className="flex flex-col gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Médias à cette étape
                </span>
                <StageMediaList
                  stageKey={selected.key as StageKey}
                  onOpenResolution={() => {
                    void navigate("/medias");
                  }}
                  onOpenMedia={(mediaId) => {
                    void navigate(`/medias?media=${mediaId}`);
                  }}
                />
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
