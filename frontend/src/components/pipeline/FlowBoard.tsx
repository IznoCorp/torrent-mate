/**
 * FlowBoard — the OBJ1 living-pipeline visualization (webui-overhaul).
 *
 * A horizontal board of nine stage "stations" (Arrivée → Dispatch), each a
 * {@link StageStation} showing a live count, a state ring and optional
 * sub-counts. Data comes from {@link usePipelineStages} (``GET
 * /api/pipeline/stages``), refreshed live off the WS stream. Clicking a station
 * opens a {@link Sheet} drawer with that stage's breakdown and a contextual
 * action (e.g. Matching → open the resolution queue).
 */

import {
  ArrowDownUp,
  ChevronRight,
  Clapperboard,
  Download,
  Inbox,
  Send,
  ShieldCheck,
  Sparkles,
  Tags,
  Target,
  type LucideIcon,
} from "lucide-react";
import { Fragment, useState, type ReactElement } from "react";
import { useNavigate } from "react-router-dom";

import type { StagesResponse } from "@/api/client";
import { ErrorState } from "@/components/ds/ErrorState";
import {
  StageStation,
  type StageSplit,
  type StageState,
} from "@/components/ds/StageStation";
import { StatusBadge, type StatusTone } from "@/components/ds/StatusBadge";
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

/** Per-stage icon, keyed by the stable stage ``key``. */
const STAGE_ICON: Record<string, LucideIcon> = {
  arrival: Download,
  staging: Inbox,
  cleaning: Sparkles,
  sorting: ArrowDownUp,
  matching: Target,
  scraping: Tags,
  trailers: Clapperboard,
  verify: ShieldCheck,
  dispatch: Send,
};

/** One-line French description of what each stage does (drawer body). */
const STAGE_DESC: Record<string, string> = {
  arrival:
    "Les téléchargements terminés sont récupérés depuis le client torrent.",
  staging: "Les médias sont déposés dans leur catégorie de la zone de transit.",
  cleaning: "Les fichiers et dossiers parasites sont supprimés.",
  sorting: "La structure et le nommage des dossiers sont normalisés.",
  matching:
    "Les identifications incertaines attendent une décision de votre part.",
  scraping: "Les métadonnées, jaquettes et NFO sont récupérées.",
  trailers: "Les bandes-annonces sont téléchargées quand elles existent.",
  verify: "La structure finale (NFO, jaquettes) est vérifiée.",
  dispatch: "Les médias sont déplacés vers le stockage définitif.",
};

/** state → (tone, French label) for the drawer status badge. */
const STATE_BADGE: Record<StageState, { tone: StatusTone; label: string }> = {
  idle: { tone: "neutral", label: "Au repos" },
  ok: { tone: "success", label: "À jour" },
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
  const navigate = useNavigate();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  if (query.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 pb-2 sm:flex-row sm:gap-2 sm:overflow-x-auto"
        aria-busy="true"
      >
        {Array.from({ length: 9 }).map((_, i) => (
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
        className="flex flex-col gap-2 pb-2 sm:flex-row sm:gap-2 sm:overflow-x-auto"
        aria-busy="true"
      >
        {Array.from({ length: 9 }).map((_, i) => (
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

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Flux du pipeline
        </h2>
        <StatusBadge tone={runBadge.tone} label={runBadge.label} />
      </div>

      {/* Stations stack vertically on mobile (readable + tappable, no lateral
          scroll); a horizontal scroll row on sm+ where the flow reads L→R. */}
      <div className="flex flex-col gap-2 pb-2 sm:flex-row sm:items-stretch sm:gap-1 sm:overflow-x-auto">
        {stages.map((stage, i) => {
          const split = toStationSplit(stage.split);
          const icon = STAGE_ICON[stage.key];
          return (
            <Fragment key={stage.key}>
              <StageStation
                label={stage.label}
                count={stage.count}
                state={stage.state}
                onClick={() => {
                  setSelectedKey(stage.key);
                }}
                {...(icon !== undefined ? { icon } : {})}
                {...(split !== null ? { split } : {})}
              />
              {/* Connector chevron only makes sense in the horizontal (sm+) flow. */}
              {i < stages.length - 1 && (
                <div
                  className="hidden shrink-0 items-center self-center text-muted-foreground/50 sm:flex"
                  aria-hidden="true"
                >
                  <ChevronRight className="size-4" />
                </div>
              )}
            </Fragment>
          );
        })}
      </div>

      <Sheet
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedKey(null);
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
                  {selected.key === "matching" ? "en attente" : "traités"}
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
                  {selected.blocked} élément(s) en erreur à cette étape.
                </p>
              )}

              {selected.key === "matching" && selected.count > 0 && (
                <Button
                  onClick={() => {
                    void navigate("/scraping");
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
                    void navigate("/scraping");
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
