/**
 * Acquisition + Watcher page (acq-watch feature).
 *
 * Four tabbed panels: Followed (CRUD), Wanted (status queue),
 * Obligations (seed/ratio), Watcher (status + toggle + recent runs).
 *
 * Live updates: the acquisition event stream (via useEventStreamContext)
 * invalidates the matching query when a relevant event arrives, using
 * the R13 new-events-only ref pattern.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { toast } from "sonner";

import {
  acqKeys,
  triggerFollowedSearch,
  type CreateFollowRequest,
  type FollowedSeriesItem,
  type ObligationItem,
} from "@/api/acquisition";
import { ApiError, setWatcher } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MediaCard } from "@/components/ds/MediaCard";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { MediaSearchAdd } from "@/components/acquisition/MediaSearchAdd";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useAcquisitionStatus,
  useFollow,
  useFollowed,
  useObligations,
  useUnfollow,
  useUpdateFollow,
  useWanted,
} from "@/hooks/useAcquisition";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Tab ids for the four panels. */
type TabId = "followed" | "wanted" | "obligations" | "watcher";

/** Event types the page listens for (DESIGN §Live invalidation). */
const ACQ_EVENT_TYPES = new Set([
  "SeriesFollowed",
  "SeriesUnfollowed",
  "WantedEnqueued",
  "WantedAbandoned",
  "GrabSucceeded",
  "GrabFailed",
  "SeedObligationRecorded",
  "SeedObligationBreached",
  "SeedObligationSatisfied",
  "RatioMeasured",
  "WatcherRunTriggered",
]);

/** Events that invalidate the entire acquisition namespace. */
const FULL_INVALIDATE_EVENTS = new Set(["SeriesFollowed", "SeriesUnfollowed"]);

/** Events that invalidate the wanted + followed queries. */
const WANTED_INVALIDATE_EVENTS = new Set([
  "WantedEnqueued",
  "WantedAbandoned",
  "GrabSucceeded",
  "GrabFailed",
]);

/** Events that invalidate the obligations queries. */
const OBLIGATION_INVALIDATE_EVENTS = new Set([
  "SeedObligationRecorded",
  "SeedObligationBreached",
  "SeedObligationSatisfied",
  "RatioMeasured",
]);

/** Tabs displayed in the page header. */
const TABS: readonly { id: TabId; label: string }[] = [
  { id: "followed", label: "Suivis" },
  { id: "wanted", label: "Recherches" },
  { id: "obligations", label: "Obligations" },
  { id: "watcher", label: "Watcher" },
];

/** Wanted status filter options. */
const WANTED_STATUS_OPTIONS = [
  { value: "all", label: "Tous" },
  { value: "pending", label: "En attente" },
  { value: "searching", label: "En recherche" },
  { value: "grabbed", label: "Récupéré" },
  { value: "done", label: "Terminé" },
  { value: "abandoned", label: "Abandonné" },
];

/** Obligation status filter options. */
const OBLIGATION_STATUS_OPTIONS = [
  { value: "all", label: "Toutes" },
  { value: "pending", label: "En cours" },
  { value: "breached", label: "Non respectée" },
  { value: "satisfied", label: "Respectée" },
];

/** Status → badge tone mapping. */
const STATUS_TONE: Record<
  string,
  "success" | "danger" | "warning" | "info" | "neutral"
> = {
  active: "success",
  inactive: "neutral",
  pending: "warning",
  searching: "info",
  grabbed: "info",
  done: "success",
  abandoned: "danger",
  satisfied: "success",
  breached: "danger",
  completed: "success",
  failed: "danger",
  killed: "warning",
};

/** Status → French label mapping. */
const STATUS_LABEL: Record<string, string> = {
  active: "Actif",
  inactive: "Inactif",
  pending: "En attente",
  searching: "En recherche",
  grabbed: "Récupéré",
  done: "Terminé",
  abandoned: "Abandonné",
  satisfied: "Respectée",
  breached: "Non respectée",
  completed: "Succès",
  failed: "Échec",
  killed: "Arrêté",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a Unix-epoch float as a relative-time string in French. */
function relativeTime(epoch: number | null | undefined): string {
  if (epoch == null) return "—";
  const diff = Date.now() - epoch * 1000;
  if (diff < 60_000) return "à l'instant";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `il y a ${String(mins)} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${String(hours)} h`;
  const days = Math.floor(hours / 24);
  return `il y a ${String(days)} j`;
}

/** Format a Unix-epoch float as a human-readable datetime in French. */
function formatDatetime(epoch: number | null | undefined): string {
  if (epoch == null) return "—";
  const d = new Date(epoch * 1000);
  return d.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Derive the obligation status from timestamps.
 *
 * The backend does not expose a ``status`` field on ObligationItem — the
 * status is implicit in the ``satisfied_at`` / ``breached_at`` columns.
 */
function obligationStatus(
  item: ObligationItem,
): "satisfied" | "breached" | "pending" {
  if (item.satisfied_at != null) return "satisfied";
  if (item.breached_at != null) return "breached";
  return "pending";
}

/** Extract ``interval_minutes`` from a cadence JSON blob, returning a safe default. */
function cadenceInterval(
  cadence: Record<string, unknown> | null | undefined,
): number {
  if (cadence == null) return 0;
  const v = cadence.interval_minutes;
  return typeof v === "number" ? v : 0;
}

/** Cadence temperature token colour (DS `--temp-*`), by tier. */
const TEMP_COLOR: Record<string, string> = {
  hot: "var(--temp-hot)",
  warm: "var(--temp-warm)",
  cold: "var(--temp-cold)",
  cutoff: "var(--temp-cutoff)",
};

/** French label for a cadence temperature tier. */
const TIER_LABEL: Record<string, string> = {
  hot: "recherche fréquente",
  warm: "recherche régulière",
  cold: "recherche espacée",
  cutoff: "abandonnée",
};

/** Relative human label until an epoch-seconds instant ("imminente" when due). */
function untilLabel(epochSec: number, nowMs: number): string {
  const deltaMs = epochSec * 1000 - nowMs;
  if (deltaMs <= 60_000) return "imminente";
  const mins = Math.round(deltaMs / 60_000);
  if (mins < 60) return `dans ~${String(mins)} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `dans ~${String(hours)} h`;
  return `dans ~${String(Math.round(hours / 24))} j`;
}

/** Truncate a long string for table display, appending "…" when cut. */
function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max)}…`;
}

// ---------------------------------------------------------------------------
// Panel: Followed
// ---------------------------------------------------------------------------

/** Props for the Followed panel sub-component. */
interface FollowedPanelProps {
  readonly data: readonly FollowedSeriesItem[];
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly error: unknown;
}

function FollowedPanel({
  data,
  isLoading,
  isError,
  error,
}: FollowedPanelProps): ReactElement {
  const followMutation = useFollow();
  const unfollowMutation = useUnfollow();
  const updateMutation = useUpdateFollow();

  // Per-series manual grab trigger (OBJ3). Fire-and-track: the 202 launches a
  // grab run; feedback is a toast (409 = already running, 404 = gone).
  const triggerMutation = useMutation({
    mutationFn: (id: number) => triggerFollowedSearch(id),
    onSuccess: () => {
      toast.success("Recherche lancée pour cette série.");
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          toast.error("Une recherche est déjà en cours pour cette série.");
        } else if (err.status === 404) {
          toast.error("Série introuvable.");
        } else {
          toast.error(err.detail);
        }
      } else {
        toast.error("Erreur lors du lancement de la recherche.");
      }
    },
  });

  // Add-form state
  const [tvdbId, setTvdbId] = useState("");
  const [title, setTitle] = useState("");

  // Edit-cadence dialog state
  const [editTarget, setEditTarget] = useState<FollowedSeriesItem | null>(null);
  const [editInterval, setEditInterval] = useState("");

  const handleAdd = (): void => {
    const tvdb = tvdbId.trim() ? Number(tvdbId.trim()) : null;
    if (tvdb === null || !Number.isFinite(tvdb)) return;
    const body: CreateFollowRequest = { tvdb_id: tvdb };
    if (title.trim()) body.title = title.trim();
    followMutation.mutate(body, {
      onSuccess: () => {
        setTvdbId("");
        setTitle("");
      },
    });
  };

  const handleUnfollow = (id: number): void => {
    unfollowMutation.mutate(id);
  };

  const openEditCadence = (item: FollowedSeriesItem): void => {
    setEditTarget(item);
    setEditInterval(String(cadenceInterval(item.cadence)));
  };

  const handleSaveCadence = (): void => {
    if (editTarget === null) return;
    const interval = Number(editInterval);
    if (!Number.isFinite(interval) || interval < 0) return;
    updateMutation.mutate(
      { id: editTarget.id, body: { cadence: { interval_minutes: interval } } },
      {
        onSuccess: () => {
          setEditTarget(null);
        },
      },
    );
  };

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, idx) => (
          <Skeleton key={`sk-f-${String(idx)}`} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  // Surface a real error instead of the empty state — otherwise a failed
  // query (e.g. an expired session → 401) would read as "you follow nothing"
  // and could trigger duplicate re-adds (adversarial-review finding).
  if (isError) {
    return (
      <p className="py-4 text-muted-foreground">
        Erreur de chargement des séries suivies :{" "}
        {error instanceof Error ? error.message : "Inconnue"}
      </p>
    );
  }

  // ── Add form (always visible) ──────────────────────────────────────────
  const addForm = (
    <Card>
      <CardContent className="pt-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1">
            <Label htmlFor="follow-tvdb-id">ID TVDB</Label>
            <Input
              id="follow-tvdb-id"
              type="number"
              placeholder="ex: 255968"
              value={tvdbId}
              onChange={(e) => {
                setTvdbId(e.target.value);
              }}
            />
          </div>
          <div className="min-w-0 flex-[2]">
            <Label htmlFor="follow-title">Titre (optionnel)</Label>
            <Input
              id="follow-title"
              type="text"
              placeholder="ex: Top Chef"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
              }}
            />
          </div>
          <Button
            size="sm"
            disabled={!tvdbId.trim() || followMutation.isPending}
            onClick={handleAdd}
          >
            {followMutation.isPending ? "Ajout…" : "Suivre"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  // ── Empty ──────────────────────────────────────────────────────────────
  if (data.length === 0) {
    return (
      <div className="space-y-4">
        {addForm}
        <div className="py-8 text-center">
          <p className="text-muted-foreground">
            Aucune série suivie. Ajoutez une série avec son identifiant TVDB
            pour commencer.
          </p>
        </div>
      </div>
    );
  }

  // ── Normal ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {addForm}

      {/* Automatic-search cadence caption (grab cron — see schedulers registry). */}
      <p className="text-xs text-muted-foreground">
        Recherche automatique : tous les jours à 03:20 et 15:20.
      </p>

      {/* Card grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((item) => {
          const interval = cadenceInterval(item.cadence);
          const seasons = item.season_count ?? 0;
          return (
            <MediaCard
              key={`f-${String(item.id)}`}
              title={item.title}
              year={item.year ?? null}
              kind="tv"
              posterUrl={item.poster_url ?? null}
              overview={item.overview ?? null}
              badges={
                <>
                  {/* Derived état: Désactivé / En cours / À jour. */}
                  {!item.active ? (
                    <Badge tone="neutral" dot>
                      Désactivé
                    </Badge>
                  ) : item.wanted_pending > 0 ? (
                    <Badge tone="warning" dot>
                      En cours
                    </Badge>
                  ) : (
                    <Badge tone="success" dot>
                      À jour
                    </Badge>
                  )}
                  {/* TVDB id kept as its own node (test + operator reference). */}
                  {item.media_ref.tvdb_id != null && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {String(item.media_ref.tvdb_id)}
                    </span>
                  )}
                  {seasons > 0 && (
                    <span className="text-xs text-muted-foreground">
                      {seasons} saison{seasons > 1 ? "s" : ""}
                    </span>
                  )}
                  {item.wanted_pending > 0 && (
                    <Badge tone="warning">
                      {String(item.wanted_pending)} en attente
                    </Badge>
                  )}
                  {item.active &&
                  item.cadence_tier != null &&
                  item.next_search_at != null ? (
                    <span
                      className="inline-flex items-center gap-1 text-xs font-medium"
                      style={{
                        color: TEMP_COLOR[item.cadence_tier] ?? "var(--muted-foreground)",
                      }}
                      title={TIER_LABEL[item.cadence_tier] ?? item.cadence_tier}
                    >
                      <span
                        className="size-1.5 rounded-full"
                        style={{
                          backgroundColor: TEMP_COLOR[item.cadence_tier] ?? "currentColor",
                        }}
                        aria-hidden
                      />
                      Prochaine recherche {untilLabel(item.next_search_at, Date.now())}
                    </span>
                  ) : (
                    interval > 0 && (
                      <span className="text-xs text-muted-foreground">
                        cadence {String(interval)} min
                      </span>
                    )
                  )}
                  {item.quality_profile != null && (
                    <Badge tone="info">Personnalisé</Badge>
                  )}
                </>
              }
              footer={
                <>
                  <Button
                    size="sm"
                    onClick={() => {
                      triggerMutation.mutate(item.id);
                    }}
                    disabled={
                      !item.active ||
                      (triggerMutation.isPending &&
                        triggerMutation.variables === item.id)
                    }
                    title={
                      item.active
                        ? "Lancer une recherche maintenant pour cette série"
                        : "Série désactivée — réactivez-la pour lancer une recherche"
                    }
                  >
                    {triggerMutation.isPending &&
                    triggerMutation.variables === item.id
                      ? "Lancement…"
                      : "Déclencher"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      openEditCadence(item);
                    }}
                  >
                    Cadence
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      handleUnfollow(item.id);
                    }}
                    disabled={unfollowMutation.isPending}
                  >
                    Retirer
                  </Button>
                </>
              }
            />
          );
        })}
      </div>

      {/* Edit-cadence dialog */}
      <Dialog
        open={editTarget !== null}
        onOpenChange={(open) => {
          if (!open) setEditTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifier la cadence</DialogTitle>
            <DialogDescription>
              {editTarget?.title ?? ""} — définissez l&apos;intervalle en
              minutes entre deux vérifications.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div>
              <Label htmlFor="cadence-interval">Intervalle (minutes)</Label>
              <Input
                id="cadence-interval"
                type="number"
                min={0}
                value={editInterval}
                onChange={(e) => {
                  setEditInterval(e.target.value);
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setEditTarget(null);
              }}
            >
              Annuler
            </Button>
            <Button
              onClick={handleSaveCadence}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel: Wanted
// ---------------------------------------------------------------------------

/** Allowed status filter values for the wanted queue (includes "all"). */
type WantedFilter =
  "all" | "pending" | "searching" | "grabbed" | "done" | "abandoned";

function WantedPanel(): ReactElement {
  const [status, setStatus] = useState<WantedFilter>("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const { data, isLoading, isError, error } = useWanted({
    ...(status !== "all" ? { status } : {}),
    page,
    page_size: pageSize,
  });

  const items = data?.items ?? [];
  const totalItems = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, idx) => (
          <Skeleton key={`sk-w-${String(idx)}`} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  if (isError) {
    return (
      <p className="py-4 text-muted-foreground">
        Erreur de chargement :{" "}
        {error instanceof Error ? error.message : "Inconnue"}
      </p>
    );
  }

  // ── Normal ─────────────────────────────────────────────────────────────
  // The status filter stays visible even when the current filter is empty, so
  // the operator can always switch filters (UX: no dead-end empty view).
  return (
    <div className="space-y-3">
      {/* Status filter + pagination info */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Label className="text-xs">Statut :</Label>
          <Select
            value={status}
            onValueChange={(v) => {
              setStatus(v as WantedFilter);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WANTED_STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <span className="text-xs text-muted-foreground">
          Page {String(page)} / {String(totalPages)} ({String(totalItems)}{" "}
          résultats)
        </span>
      </div>

      {items.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-muted-foreground">
            {status === "all"
              ? "Aucune recherche en file. Suivez des séries pour remplir cette liste."
              : `Aucune recherche avec le statut « ${STATUS_LABEL[status] ?? status} ».`}
          </p>
        </div>
      ) : (
        <>
          {/* Table */}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Titre</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Saison</TableHead>
                <TableHead>Épisode</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Tentatives</TableHead>
                <TableHead>Ajouté</TableHead>
                <TableHead>Dernière recherche</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={`w-${String(item.id)}`}>
                  <TableCell className="font-medium">{item.title}</TableCell>
                  <TableCell className="text-xs">{item.kind}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.season ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.episode ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge tone={STATUS_TONE[item.status] ?? "neutral"}>
                      {STATUS_LABEL[item.status] ?? item.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.attempts}
                  </TableCell>
                  <TableCell className="text-xs">
                    {relativeTime(item.enqueued_at)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {relativeTime(item.last_search_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => {
                setPage((p) => Math.max(1, p - 1));
              }}
            >
              ← Précédent
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => {
                setPage((p) => p + 1);
              }}
            >
              Suivant →
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel: Obligations
// ---------------------------------------------------------------------------

/** Allowed status filter values for obligations (includes "all"). */
type ObligationFilter = "all" | "pending" | "breached" | "satisfied";

function ObligationsPanel(): ReactElement {
  const [status, setStatus] = useState<ObligationFilter>("all");

  const { data, isLoading, isError, error } = useObligations({
    ...(status !== "all" ? { status } : {}),
  });

  // Trust the SERVER filter (the route already filters by status) — do NOT
  // re-filter client-side: a row with both satisfied_at and breached_at set is
  // classified "breached" by the server but "satisfied" by obligationStatus(),
  // so a client re-filter would silently drop it (adversarial-review finding).
  // obligationStatus() stays in use only for the per-row status BADGE.
  const items = data?.items ?? [];

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, idx) => (
          <Skeleton key={`sk-o-${String(idx)}`} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  if (isError) {
    return (
      <p className="py-4 text-muted-foreground">
        Erreur de chargement :{" "}
        {error instanceof Error ? error.message : "Inconnue"}
      </p>
    );
  }

  // ── Empty ──────────────────────────────────────────────────────────────
  if (items.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-muted-foreground">
          {status === "all"
            ? "Aucune obligation de seed enregistrée."
            : `Aucune obligation avec le statut « ${STATUS_LABEL[status] ?? status} ».`}
        </p>
      </div>
    );
  }

  // ── Normal ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-3">
      {/* Status filter */}
      <div className="flex items-center gap-2">
        <Label className="text-xs">Statut :</Label>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v as ObligationFilter);
          }}
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OBLIGATION_STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Info Hash</TableHead>
            <TableHead>Tracker</TableHead>
            <TableHead>Ratio min</TableHead>
            <TableHead>Ratio obs.</TableHead>
            <TableHead>Seed min</TableHead>
            <TableHead>HnR</TableHead>
            <TableHead>Statut</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const obs = obligationStatus(item);
            return (
              <TableRow key={`o-${item.info_hash}-${item.source_tracker}`}>
                <TableCell className="font-mono text-xs">
                  {truncate(item.info_hash, 12)}
                </TableCell>
                <TableCell className="text-xs">{item.source_tracker}</TableCell>
                <TableCell className="font-mono text-xs">
                  {item.min_ratio.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {item.observed_ratio != null
                    ? item.observed_ratio.toFixed(2)
                    : "—"}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {item.min_seed_time_s > 0
                    ? `${String(Math.round(item.min_seed_time_s / 3600))} h`
                    : "—"}
                </TableCell>
                <TableCell>
                  {item.hnr_count != null && item.hnr_count > 0 ? (
                    <Badge tone="danger">{String(item.hnr_count)}</Badge>
                  ) : (
                    "0"
                  )}
                </TableCell>
                <TableCell>
                  <Badge tone={STATUS_TONE[obs] ?? "neutral"}>
                    {STATUS_LABEL[obs] ?? obs}
                  </Badge>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel: Watcher
// ---------------------------------------------------------------------------

function WatcherPanel(): ReactElement {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useAcquisitionStatus();

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => setWatcher({ enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: acqKeys.status() });
    },
  });

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <p className="py-4 text-muted-foreground">
        Erreur de chargement :{" "}
        {error instanceof Error ? error.message : "Inconnue"}
      </p>
    );
  }

  const { watcher_enabled, last_successful_run_at, recent_runs } = data;

  // ── Normal ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Status card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">État du watcher</CardTitle>
          <Badge tone={watcher_enabled ? "success" : "neutral"}>
            {watcher_enabled ? "Activé" : "Désactivé"}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                Dernière exécution
              </p>
              <p className="text-sm font-medium">
                {last_successful_run_at != null
                  ? `${formatDatetime(last_successful_run_at)} (${relativeTime(last_successful_run_at)})`
                  : "Jamais"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="watcher-toggle" className="text-xs">
                Activé
              </Label>
              <Switch
                id="watcher-toggle"
                checked={watcher_enabled}
                onCheckedChange={(checked) => {
                  toggleMutation.mutate(checked);
                }}
                disabled={toggleMutation.isPending}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent runs */}
      <div>
        <h3 className="mb-2 text-sm font-semibold">
          Exécutions récentes du watcher
        </h3>
        {recent_runs.length === 0 ? (
          <p className="py-4 text-center text-muted-foreground">
            Aucune exécution récente enregistrée.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run UID</TableHead>
                <TableHead>Démarré</TableHead>
                <TableHead>Terminé</TableHead>
                <TableHead>Résultat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recent_runs.map((run) => (
                <TableRow key={run.run_uid}>
                  <TableCell className="font-mono text-xs">
                    {truncate(run.run_uid, 12)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {formatDatetime(run.started_at)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {formatDatetime(run.ended_at)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      tone={
                        run.outcome != null
                          ? (STATUS_TONE[run.outcome] ?? "neutral")
                          : "neutral"
                      }
                    >
                      {run.outcome != null
                        ? (STATUS_LABEL[run.outcome] ?? run.outcome)
                        : "—"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * AcquisitionPage — the authenticated acquisition route (``/acquisition``).
 *
 * Four tabbed panels for followed series CRUD, wanted queue, seed
 * obligations, and watcher status.  Live events from the WebSocket
 * invalidate the matching TanStack Query caches (R13 — processes only
 * new events, not the whole ring on every render).
 *
 * Returns:
 *   The acquisition page element.
 */
export default function AcquisitionPage(): ReactElement {
  const [activeTab, setActiveTab] = useState<TabId>("followed");
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  // Only invalidate on fresh events, not re-scanning the ring every render
  // (AppShell R13 ref pattern, coherence study F13).
  const lastProcessedRef = useRef(0);
  useEffect(() => {
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;

    for (const msg of fresh) {
      if (!ACQ_EVENT_TYPES.has(msg.type)) continue;

      if (FULL_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({ queryKey: acqKeys.all });
        continue;
      }
      if (WANTED_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({ queryKey: acqKeys.wanted({}) });
        void queryClient.invalidateQueries({ queryKey: acqKeys.followed({}) });
        continue;
      }
      if (OBLIGATION_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({
          queryKey: acqKeys.obligations({}),
        });
        continue;
      }
      if (msg.type === "WatcherRunTriggered") {
        void queryClient.invalidateQueries({ queryKey: acqKeys.status() });
      }
    }
  }, [events, queryClient]);

  // ── Followed data (shared across tabs — prefetched but only rendered in
  //    its tab; the query is kept alive by the hook at page level). ──────
  const followedQuery = useFollowed({ active: "all" });

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Acquisition</h1>

      {/* Tabs */}
      <div role="tablist" className="flex gap-1 rounded-lg bg-muted p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => {
              setActiveTab(tab.id);
            }}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active panel */}
      <Card>
        <CardContent className="pt-4">
          {activeTab === "followed" && (
            <div className="flex flex-col gap-6">
              <MediaSearchAdd />
              <FollowedPanel
                data={followedQuery.data?.items ?? []}
                isLoading={followedQuery.isLoading}
                isError={followedQuery.isError}
                error={followedQuery.error}
              />
            </div>
          )}
          {activeTab === "wanted" && <WantedPanel />}
          {activeTab === "obligations" && <ObligationsPanel />}
          {activeTab === "watcher" && <WatcherPanel />}
        </CardContent>
      </Card>
    </section>
  );
}
