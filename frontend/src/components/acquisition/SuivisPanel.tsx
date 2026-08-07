/**
 * SuivisPanel — the « Suivis » catalogue view with filter pills, three display
 * modes, and a mode switcher.
 *
 * Replaces the old ``FollowedPanel`` (two tab levels, two search fields).  What
 * disappears:
 * - Séries / Films sub-tabs → filter pills carrying their counts.
 * - The second search field → only the **filter** remains, sticky.  Adding lives
 *   on the « + » floating action button.
 * - The always-rendered « Détail par épisode » accordion → the detail sheet
 *   (tap the card).
 *
 * Mode persisted in ``localStorage``, **never** in the URL: it is a preference,
 * not a location (DOIT-10).  Switcher placement B — pinned at the end of the
 * pill train with a hard ``border-l`` divider and solid ``bg-background`` (A9).
 *
 * Three display modes (A6):
 * - **Liste** (default) — one card per follow, urgency first, status chip on each row.
 * - **Groupé** — same card, status moves to the section header and leaves the row
 *   (§12: no repetition).
 * - **Grille** — 3-up poster grid; the badge carries a NUMBER, not a mute colour.
 */

import { type ReactElement, useMemo, useState } from "react";

import { useNavigate } from "react-router-dom";

import type { FollowedSeriesItem } from "@/api/acquisition";
import { useFollowed } from "@/hooks/useAcquisition";

import { MediaPoster } from "@/components/ds/MediaPoster";
import { ErrorState } from "@/components/ds/ErrorState";

import { AcquisitionCard } from "./AcquisitionCard";
import { SwipeActions } from "./SwipeActions";
import { useFollowActions } from "./followActions";
import { useSchedulers } from "@/hooks/useSchedulers";
import { FollowDetailSheet } from "./FollowDetailSheet";
import type { FollowStatus, MediaKind } from "./meta";
import {
  FOLLOW_STATUS_LABEL,
  FOLLOW_STATUS_TONE,
  GRAB_JOB_NAME,
  TONE_CHIP_CLASS,
  asMediaKind,
  followCountsCaption,
  followFraction,
  followMediaRef,
  followStatusHint,
  followStatusLabel,
} from "./meta";
import { type ViewMode, useViewMode } from "./useViewMode";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Urgency sort order — lower = more urgent, shown first.
 *
 * §5.1: « a_recuperer » is what the operator can act on RIGHT NOW;
 * « a_jour » is information, not a call to action.
 */
/** A follow added within this window is « new » — §7's post-add promise:
 *  sorted to the top of « Suivis » with a « Nouveau » chip, so the operator
 *  sees their add LAND rather than hunting it through the urgency order. */
const NEW_WINDOW_S = 24 * 3600;

function isNew(item: FollowedSeriesItem): boolean {
  return Date.now() / 1000 - item.added_at < NEW_WINDOW_S;
}

const URGENCY: Record<string, number> = {
  a_recuperer: 0,
  en_acquisition: 1,
  // Being verified is in motion — between « acquiring » and « waiting ».
  verification_en_cours: 2,
  en_attente: 3,
  non_verifie: 4,
  a_jour: 5,
  disabled: 6,
};

/** Filter pill keys. */
type FilterPill = "tout" | "series" | "films" | "pause";

interface PillMeta {
  readonly label: string;
  /** Compute the count from the full (unfiltered) list. */
  count(items: readonly FollowedSeriesItem[]): number;
  /** Whether this item matches the pill. */
  matches(item: FollowedSeriesItem): boolean;
}

const PILLS: Record<FilterPill, PillMeta> = {
  tout: {
    label: "Tout",
    count: (items) => items.filter((i) => i.active).length,
    matches: (i) => i.active,
  },
  series: {
    label: "Séries",
    count: (items) => items.filter((i) => i.active && i.kind !== "movie").length,
    matches: (i) => i.active && i.kind !== "movie",
  },
  films: {
    label: "Films",
    count: (items) => items.filter((i) => i.active && i.kind === "movie").length,
    matches: (i) => i.active && i.kind === "movie",
  },
  pause: {
    label: "En pause",
    // status "disabled" is the server's derivation of active=0 — the old
    // predicate ANDed it with i.active, a combination the server can never
    // produce. One derivation (§13): read the derived status alone.
    count: (items) => items.filter((i) => i.status === "disabled").length,
    matches: (i) => i.status === "disabled",
  },
};

/**
 * Group keys for « groupé » mode.
 *
 * Ordered by urgency — same as the sort.
 */
const GROUP_KEYS: FollowStatus[] = [
  "a_recuperer",
  "en_acquisition",
  "verification_en_cours",
  "en_attente",
  "non_verifie",
  "a_jour",
  "disabled",
];

// ---------------------------------------------------------------------------
// Sort
// ---------------------------------------------------------------------------

/**
 * Sort followed items by urgency then by title (localeCompare fr).
 *
 * Args:
 *   items: The items to sort (copied first so the source is not mutated).
 *
 * Returns:
 *   A new sorted array.
 */
function sortItems(items: readonly FollowedSeriesItem[]): FollowedSeriesItem[] {
  return [...items].sort((a, b) => {
    // §7 — a fresh add outranks everything: the operator just acted, and the
    // list must show the consequence where they look first.
    const na = isNew(a) ? 0 : 1;
    const nb = isNew(b) ? 0 : 1;
    if (na !== nb) return na - nb;
    const ua = URGENCY[a.status] ?? 99;
    const ub = URGENCY[b.status] ?? 99;
    if (ua !== ub) return ua - ub;
    return a.title.localeCompare(b.title, "fr");
  });
}

// ---------------------------------------------------------------------------
// Name filter
// ---------------------------------------------------------------------------

/**
 * Accent- and case-insensitive name normalisation.
 *
 * A filter that demands the exact diacritics is a filter the operator has to
 * fight — this is the same normalisation the backend matching uses.
 */
function normalise(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase();
}

function matchesName(item: FollowedSeriesItem, term: string): boolean {
  return term === "" || normalise(item.title).includes(term);
}

// ---------------------------------------------------------------------------
// Grid badge
// ---------------------------------------------------------------------------

/**
 * Compute the grid badge content for one followed item.
 *
 * §5.2 fixes what an ABSENT badge means: « a follow with nothing to do carries
 * no badge at all ». A grid tile is a poster plus this badge and nothing else —
 * unlike a list row, it carries no status chip. So absence is a STATEMENT here,
 * and the two ways to get it wrong are symmetric: inventing a number the data
 * cannot support, and staying silent about something that needs attention.
 *
 * The honesty rules mirror ``followFraction`` (meta.ts:468-472):
 * - No verdict yet (``non_verifie`` / ``verification_en_cours``) — « ? ».
 * - Nothing to do (``a_jour`` / ``disabled``) — no badge.
 * - A film has NO episode catalogue, so its gap cannot be COUNTED — but it can
 *   be MARKED: « ! ». Returning null instead would tell the operator, about a
 *   film that needs attention, that it needs none.
 * - ``aired_count == null`` means the catalogue is unknown — « ? », never a
 *   fabricated number.
 * - A computed number ONLY for actionable states with a known catalogue.
 *
 * Returns:
 *   ``"1"`` for one takeable episode, ``"22"`` for 22 waiting, ``"!"`` for an
 *   actionable film, ``"?"`` for unknown / no-verdict states, or ``null`` for
 *   ``a_jour`` / ``disabled`` — absence IS the signal that there is nothing
 *   to do.
 */
function gridBadge(item: FollowedSeriesItem): string | null {
  // No verdict yet: both mean "we don't know what's missing".
  if (item.status === "non_verifie" || item.status === "verification_en_cours") return "?";
  // Nothing to do — absence IS the signal.
  if (item.status === "a_jour" || item.status === "disabled") return null;
  // Everything below is an ACTIONABLE state.
  // A film has no episode catalogue: mark it, do not count it.
  if (item.kind === "movie") return "!";
  // Unknown catalogue → honest ignorance, not a fabricated number.
  if (item.aired_count == null) return "?";
  // Actionable states with a known catalogue — how many aired episodes are not
  // owned. Stale counts can disagree with the status (aired === owned on an
  // actionable row): that is a data conflict, and « ? » is the honest render —
  // Math.max(1, …) used to fabricate an episode out of the disagreement.
  const missing = item.aired_count - (item.owned_count ?? 0);
  return missing >= 1 ? String(missing) : "?";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Render the « Suivis » panel — catalogue with filter pills and three modes.
 *
 * Args: none — all data comes from ``useFollowed`` (TanStack Query).
 *
 * Returns:
 *   The panel element.
 */
export function SuivisPanel(): ReactElement {
  const navigate = useNavigate();
  // active:"all", deliberately: the server derives status "disabled" ONLY for
  // active=0 rows, and the default fetch excludes exactly those. With the
  // default, pausing a follow made it vanish from every mounted surface and
  // the « En pause » pill was a permanent zero by construction — a filter that
  // can never match is a lie with a control attached.
  const followed = useFollowed({ active: "all" });
  const actions = useFollowActions();
  // C15 — the automatic-search cadence, read from the LIVE scheduler and never
  // hardcoded; omitted entirely when the job is absent (§8: we do not narrate
  // a schedule we do not know).
  const schedulers = useSchedulers();
  const grabJob = (schedulers.data?.schedulers ?? []).find(
    (j) => j.name === GRAB_JOB_NAME,
  );
  const cadenceCaption =
    grabJob?.schedule != null && grabJob.schedule !== ""
      ? `Recherche automatique : ${grabJob.schedule}`
      : null;
  const [viewMode, setViewMode] = useViewMode();

  // ── State ──────────────────────────────────────────────────────────────────

  /** Active filter pill. */
  const [pill, setPill] = useState<FilterPill>("tout");
  /** Name filter text. */
  const [nameFilter, setNameFilter] = useState("");

  // Detail-sheet state.
  const [sheet, setSheet] = useState<{
    followedId: number;
    status: FollowStatus;
    kind: MediaKind;
    mediaHref: string | null;
  } | null>(null);

  // ── Derived data ───────────────────────────────────────────────────────────

  const { data, isLoading, isError } = followed;

  const items = useMemo(() => data?.items ?? [], [data]);
  const filterTerm = normalise(nameFilter.trim());

  // Apply pill filter + name filter then sort.
  const visible = useMemo(() => {
    const pillMeta = PILLS[pill];
    const filtered = items.filter(
      (i) => pillMeta.matches(i) && matchesName(i, filterTerm),
    );
    return sortItems(filtered);
  }, [items, pill, filterTerm]);

  // ── Loading / error / empty guards ─────────────────────────────────────────
  // § panne ≠ absence : a failed load must never read as « you follow nothing ».

  const anyData = data != null;

  // ── Render helpers ─────────────────────────────────────────────────────────

  /** Render one row in liste or groupé mode. */
  function renderCard(item: FollowedSeriesItem, showStatus: boolean): ReactElement {
    const kind = asMediaKind(item.kind);
    const label = followStatusLabel(item.status, kind === "movie" ? "movie" : "show");
    const hint = followStatusHint(item.status, kind);
    const caption = followCountsCaption(item);
    const fraction = followFraction(item);

    // Meta line: fraction, status chip, counts caption.
    // In groupé mode (showStatus=false), the status chip is omitted — it lives in
    // the section header instead (§12: no repetition).
    const metaPieces: ReactElement[] = [];
    if (isNew(item)) {
      metaPieces.push(
        <span
          key="nouveau"
          data-testid="chip-nouveau"
          className="rounded bg-info/20 px-1.5 py-px text-xs font-medium text-info"
        >
          Nouveau
        </span>,
      );
    }
    if (fraction != null) {
      metaPieces.push(
        <span
          key="fraction"
          className="rounded bg-muted px-1.5 py-px text-xs font-medium text-muted-foreground"
        >
          {fraction}
        </span>,
      );
    }
    if (showStatus) {
      metaPieces.push(
        <span
          key="status"
          data-slot="badge"
          className={`rounded px-1.5 py-px text-xs font-medium ${TONE_CHIP_CLASS[FOLLOW_STATUS_TONE[item.status]] ?? "bg-muted text-muted-foreground"}`}
          title={hint}
        >
          {label}
        </span>,
      );
    }
    if (caption != null) {
      metaPieces.push(
        <span
          key="caption"
          className="text-xs text-muted-foreground"
        >
          {caption}
        </span>,
      );
    }

    const sheetHref = followMediaRef(item);

    return (
      /* A10 — the card's own gesture: swipe reveals suspend/remove. The pager
         hands back any drag born inside data-swipe, so the two horizontal
         gestures never fight. The « ··· » renders on fine pointers only —
         the card enforces A11 itself. */
      <SwipeActions key={item.id} right={actions.swipeFor(item)}>
        <AcquisitionCard
          title={item.title}
          posterUrl={item.poster_url ?? null}
          {...(item.year != null ? { subtitle: String(item.year) } : {})}
          meta={metaPieces.length > 0 ? <>{metaPieces}</> : null}
          menu={actions.menuFor(item)}
          onOpen={() => {
            setSheet({ followedId: item.id, status: item.status, kind, mediaHref: sheetHref });
          }}
          {...(sheetHref != null
            ? {
                onPoster: () => {
                  void navigate(sheetHref);
                },
              }
            : {})}
        />
      </SwipeActions>
    );
  }

  /** Render one tile in grid mode. */
  function renderTile(item: FollowedSeriesItem): ReactElement {
    const badge = gridBadge(item);
    const dimmed = item.status === "disabled";

    return (
      <button
        key={item.id}
        type="button"
        data-testid={`tile-${String(item.id)}`}
        className={`relative flex aspect-[2/3] w-full items-center justify-center overflow-hidden rounded-lg border border-border ${
          dimmed ? "opacity-50" : ""
        }`}
        aria-label={
          badge != null ? `${item.title} — ${badge === "?" ? "état à vérifier" : badge === "!" ? "action requise" : `${badge} épisode(s) à récupérer`}` : item.title
        }
        onClick={() => {
          const kind = asMediaKind(item.kind);
          setSheet({ followedId: item.id, status: item.status, kind, mediaHref: followMediaRef(item) });
        }}
      >
        <MediaPoster title={item.title} src={item.poster_url ?? null} className="!w-full" />
        {badge != null && (
          <span
            data-badge
            className={`absolute right-1 top-1 flex size-6 items-center justify-center rounded-full text-xs font-bold text-white ${
              badge === "?" ? "bg-muted-foreground" : "bg-warning"
            }`}
          >
            {badge}
          </span>
        )}
      </button>
    );
  }

  /** Render the mode switcher buttons. */
  function renderSwitcher(): ReactElement {
    const modes: { key: ViewMode; label: string; ariaLabel: string }[] = [
      { key: "list", label: "Liste", ariaLabel: "Liste" },
      { key: "group", label: "Groupé", ariaLabel: "Groupé par état" },
      { key: "grid", label: "Grille", ariaLabel: "Grille d'affiches" },
    ];

    return (
      <div
        className="flex-none border-l border-border bg-background pl-2"
        // Switcher placement B mitigation (A9): hard divider + solid background,
        // never a gradient — the pills filter DATA, the switcher changes
        // PRESENTATION, and the two natures must not read as one train.
      >
        <div role="group" aria-label="Mode d'affichage" className="flex items-center gap-0.5">
          {modes.map((m) => (
            <button
              key={m.key}
              type="button"
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                viewMode === m.key
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              aria-label={m.ariaLabel}
              aria-pressed={viewMode === m.key}
              onClick={() => {
                setViewMode(m.key);
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      <div className="flex flex-col gap-4 px-3 py-3">
        {/* ── Sticky filter zone ──────────────────────────────────────── */}

        {/* Search field — the ONE that filters (D2). */}
        <input
          type="search"
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground"
          placeholder="Filtrer par nom"
          value={nameFilter}
          onChange={(e) => {
            setNameFilter(e.target.value);
          }}
        />

        {/* Pill train + switcher — STICKY (§5.1: « only the filter remains,
            and it is sticky »; D7 was losing the filter after two screens of
            scroll). The pills scroll horizontally in their OWN container; the
            switcher sits outside it, so at 390 px it never scrolls away with
            the train — a mode control the operator cannot see is a mode the
            operator does not know exists. */}
        <div className="sticky top-0 z-10 -mx-3 flex items-center gap-1 bg-background px-3 py-2">
          <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
          {(["tout", "series", "films", "pause"] as const).map((k) => {
            const pm = PILLS[k];
            const count = pm.count(items);
            return (
              <button
                key={k}
                type="button"
                className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  pill === k
                    ? "bg-foreground text-background"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
                aria-pressed={pill === k}
                onClick={() => {
                  setPill(k);
                }}
              >
                {pm.label} {String(count)}
              </button>
            );
          })}
          </div>
          {renderSwitcher()}
        </div>
        {cadenceCaption != null && (
          <p
            data-testid="cadence-caption"
            className="px-1 text-xs text-muted-foreground"
          >
            {cadenceCaption}
          </p>
        )}

        {/* ── Loading ────────────────────────────────────────────────── */}
        {isLoading && !anyData && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Chargement…
          </p>
        )}

        {/* ── Error ──────────────────────────────────────────────────── */}
        {isError && (
          <ErrorState title="Impossible de charger les suivis." />
        )}

        {/* ── Empty ──────────────────────────────────────────────────── */}
        {!isLoading && !isError && items.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Aucun suivi — utilisez le « + » pour en ajouter un.
          </p>
        )}

        {/* ── Normal — data loaded, items present ─────────────────────── */}
        {!isLoading && !isError && visible.length === 0 && items.length > 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Aucun suivi ne correspond au filtre.
          </p>
        )}

        {/* List mode — flat card list. */}
        {!isLoading && !isError && viewMode === "list" && visible.length > 0 && (
          <div className="flex flex-col gap-2" data-testid="list-container">
            {visible.map((item) => renderCard(item, true))}
          </div>
        )}

        {/* Grouped mode — cards under status headers. */}
        {!isLoading && !isError && viewMode === "group" && visible.length > 0 && (
          <div className="flex flex-col gap-4" data-testid="group-container">
            {GROUP_KEYS.map((status) => {
              const groupItems = visible.filter((i) => i.status === status);
              if (groupItems.length === 0) return null;

              return (
                <section key={status} data-testid={`group-${status}`}>
                  <div
                    data-testid="section-head"
                    className="mb-2 flex items-center gap-2 text-sm font-medium"
                  >
                    {FOLLOW_STATUS_LABEL[status]}
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {String(groupItems.length)}
                    </span>
                  </div>
                  <div className="flex flex-col gap-2">
                    {groupItems.map((item) => renderCard(item, false))}
                  </div>
                </section>
              );
            })}
          </div>
        )}

        {/* Grid mode — 3-up poster grid. */}
        {!isLoading && !isError && viewMode === "grid" && visible.length > 0 && (
          <div
            className="grid grid-cols-3 gap-3"
            data-testid="grid-container"
          >
            {visible.map(renderTile)}
          </div>
        )}
      </div>

      {actions.dialog}

      {/* ── Detail sheet ─────────────────────────────────────────────── */}
      {sheet != null && (
        <FollowDetailSheet
          followedId={sheet.followedId}
          status={sheet.status}
          kind={sheet.kind}
          mediaHref={sheet.mediaHref}
          open
          onOpenChange={(open) => {
            if (!open) setSheet(null);
          }}
        />
      )}
    </>
  );
}
