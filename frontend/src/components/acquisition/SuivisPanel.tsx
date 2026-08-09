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

import { type ReactElement, useCallback, useMemo, useRef, useState } from "react";

import { AlignLeft, LayoutGrid, List, Search as SearchIcon, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import type { FollowedSeriesItem } from "@/api/acquisition";
import { useFollowed } from "@/hooks/useAcquisition";

import { MediaPoster } from "@/components/ds/MediaPoster";
import { ErrorState } from "@/components/ds/ErrorState";

import { AcquisitionCard } from "./AcquisitionCard";
import { Chip } from "./Chip";
import { SwipeActions } from "./SwipeActions";
import { useFollowActions } from "./followActions";
import { useSchedulers } from "@/hooks/useSchedulers";
import { VIEWTABS_HEIGHT_VAR } from "@/components/layout/bottom-bar-metrics";
import { scrollRootToTop } from "@/lib/scroll-root";
import { posterThumb } from "@/lib/poster-thumb";
import { useBackCloses } from "@/lib/use-back-closes";

import { FollowDetailSheet } from "./FollowDetailSheet";
import type { FollowStatus } from "./meta";
import {
  FOLLOW_STATUS_TONE,
  GRAB_JOB_NAME,
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

const URGENCY: Record<FollowStatus, number> = {
  a_recuperer: 0,
  en_acquisition: 1,
  // Being verified is in motion — between « acquiring » and « waiting ».
  verification_en_cours: 2,
  en_attente: 3,
  non_verifie: 4,
  a_jour: 5,
  // A finished series asks for less than a running one that happens to be
  // caught up: nothing will ever move it again. It sits below « À jour » and
  // above the follows the operator themself put down.
  termine: 6,
  disabled: 7,
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

/* Maquette FILTERS semantics: « Tout » is ALL follows — a paused follow
 * stays visible (dimmed, urgency-sorted last, « en pause » tile fraction)
 * instead of vanishing from the default view; « Séries »/« Films » cut by
 * nature only. « En pause » remains the dedicated lens. */
const PILLS: Record<FilterPill, PillMeta> = {
  tout: {
    label: "Tout",
    count: (items) => items.length,
    matches: () => true,
  },
  series: {
    label: "Séries",
    count: (items) => items.filter((i) => i.kind !== "movie").length,
    matches: (i) => i.kind !== "movie",
  },
  films: {
    label: "Films",
    count: (items) => items.filter((i) => i.kind === "movie").length,
    matches: (i) => i.kind === "movie",
  },
  pause: {
    label: "En pause",
    // status "disabled" is the server's derivation of active=0 — one
    // derivation (§13): read the derived status alone.
    count: (items) => items.filter((i) => i.status === "disabled").length,
    matches: (i) => i.status === "disabled",
  },
};

/**
 * The « groupé » mode groups — the maquette's URGENCY classes, not the raw
 * statuses: what asks for something, what runs alone, what rests, what is
 * paused. Cards inside a heterogeneous group KEEP their status chip (the
 * header alone cannot say which of its three statuses a card carries).
 */
const GROUPS: readonly {
  readonly key: string;
  readonly label: string;
  readonly pipClass: string;
  readonly of: readonly FollowStatus[];
}[] = [
  {
    key: "demandent",
    label: "Demandent quelque chose",
    pipClass: "bg-warning",
    of: ["a_recuperer", "en_attente", "non_verifie"],
  },
  {
    key: "en-cours",
    label: "En cours",
    pipClass: "bg-info",
    of: ["en_acquisition", "verification_en_cours"],
  },
  { key: "a-jour", label: "À jour", pipClass: "bg-success", of: ["a_jour"] },
  // Its own group rather than a second tenant of « À jour »: folding it in
  // would bury the very distinction the operator asked for (2026-08-09), and
  // « mes séries finies » is a list they want to be able to look at.
  {
    key: "terminees",
    label: "Terminées",
    pipClass: "bg-muted-foreground",
    of: ["termine"],
  },
  {
    key: "en-pause",
    label: "En pause",
    pipClass: "bg-muted-foreground",
    of: ["disabled"],
  },
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
 * Compute the grid badge content for one followed item — maquette rule:
 * « la pastille porte un NOMBRE ; rien à faire = pas de pastille ».
 *
 * Every actionable status carries the count of missing units — a film counts
 * as its single unit (operator arbitration: the number, never a « ! »). No
 * verdict yet reads « ? »; nothing to do renders NO badge at all.
 */
function gridBadge(item: FollowedSeriesItem): string | null {
  if (
    item.status === "a_recuperer" ||
    item.status === "en_acquisition" ||
    item.status === "en_attente"
  ) {
    // A FILM is one unit: « 1 » counts nothing the operator did not already
    // know from the tile being there at all (their words: « ça n'a pas
    // vraiment de sens »). The dot says « this one wants something » without
    // pretending to count.
    if (item.kind === "movie") return "•";
    return String(
      Math.max(1, (item.aired_count ?? 0) - (item.owned_count ?? 0)),
    );
  }
  if (item.status === "non_verifie" || item.status === "verification_en_cours")
    return "?";
  return null;
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
  // staleTime keeps a tab switch instant: within the window the cached list
  // renders with NO refetch flash; the interval keeps it live while mounted.
  const followed = useFollowed(
    { active: "all" },
    { staleTime: 55_000, refetchInterval: 60_000 },
  );
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
  /** The filter box — the clear button hands focus straight back to it. */
  const filterInputRef = useRef<HTMLInputElement | null>(null);
  /** Anchor inside the scrollport — how « back to top » finds it. */
  const switcherRef = useRef<HTMLDivElement | null>(null);

  // Detail-sheet state.
  const [sheet, setSheet] = useState<FollowedSeriesItem | null>(null);
  // Back gesture closes the sheet instead of leaving the Suivis tab.
  useBackCloses(
    sheet != null,
    useCallback(() => {
      setSheet(null);
    }, []),
  );

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
    if (fraction != null) {
      metaPieces.push(
        <span
          key="fraction"
          className="font-mono text-xs text-muted-foreground tabular-nums"
        >
          {fraction}
        </span>,
      );
    }
    if (showStatus) {
      metaPieces.push(
        <Chip key="status" tone={FOLLOW_STATUS_TONE[item.status]} title={hint}>
          {label}
        </Chip>,
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
    if (item.tvdb_unresolved) {
      // The identity gap, named on the card — the sheet explains what it
      // blocks; hiding it would let a « Non vérifié » read as a search issue.
      metaPieces.push(
        <Chip
          key="sans-id"
          tone="warning"
          title="Détection d'épisodes indisponible : l'ID TVDB n'a pas pu être résolu."
        >
          Sans ID TVDB
        </Chip>,
      );
    }
    if (isNew(item)) {
      // Maquette order: the freshtag closes the meta row, after every chip.
      metaPieces.push(
        <span key="nouveau" data-testid="chip-nouveau" className="freshtag">
          Nouveau
        </span>,
      );
    }

    const sheetHref = followMediaRef(item);

    return (
      /* A10 — the card's own gesture: swipe reveals suspend/remove. The pager
         hands back any drag born inside data-swipe, so the two horizontal
         gestures never fight. The « ··· » renders on fine pointers only —
         the card enforces A11 itself. */
      <SwipeActions
        key={item.id}
        {...actions.swipeFor(item)}
        {...(isNew(item) ? { className: "fresh" } : {})}
      >
        {/* No year subtitle here — the maquette's followRow is title + meta
            row only; the year lives in the sheet (§12 density). */}
        <AcquisitionCard
          title={item.title}
          posterUrl={item.poster_url ?? null}
          meta={metaPieces.length > 0 ? <>{metaPieces}</> : null}
          onOpen={() => {
            setSheet(item);
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
        className={`tile${dimmed ? " off" : ""}`}
        aria-label={
          badge != null ? `${item.title} — ${badge === "?" ? "état à vérifier" : `${badge} épisode(s) manquant(s)`}` : item.title
        }
        onClick={() => {
          setSheet(item);
        }}
      >
        {/* Maquette .tile grammar: the .p poster box (aspect 2/3, radius 6,
            no border), badge as a .tile child, .nm/.fr text rows. */}
        <span className="p">
          <MediaPoster
            title={item.title}
            src={posterThumb(item.poster_url ?? null)}
            className="!h-full !w-full"
          />
        </span>
        {badge != null && (
          <span
            data-badge
            className={`absolute right-[5px] top-[5px] grid h-[17px] min-w-[17px] place-items-center rounded-full border-2 border-background px-1 text-[9.5px] font-bold text-white ${
              badge === "?"
                ? "bg-muted-foreground"
                : item.status === "en_acquisition"
                  ? "bg-info"
                  : item.status === "en_attente"
                    ? "bg-waiting"
                    : "bg-warning"
            }`}
          >
            {badge}
          </span>
        )}
        <span className="nm">{item.title}</span>
        <span className="fr">
          {/* Maquette: a paused tile SAYS so where the fraction went \u2014 the
              dimming alone does not answer \u00AB pourquoi rien ne bouge \u00BB. */}
          {dimmed
            ? "en pause"
            : item.kind === "movie"
              ? item.status === "a_jour"
                ? "acquis"
                : "non acquis"
              : (followFraction(item) ?? "\u00A0")}
        </span>
      </button>
    );
  }

  /** Render the mode switcher — three ICON buttons, per the maquette.
   *
   * Text labels (« Liste Groupé Grille ») ate half the 375 px row and forced
   * the pills into a permanent horizontal scroll; the icon triplet costs
   * ~100 px and the pills get the rest. The names stay for assistive tech.
   */
  function renderSwitcher(): ReactElement {
    const modes: { key: ViewMode; icon: ReactElement; ariaLabel: string }[] = [
      { key: "list", icon: <List aria-hidden="true" className="size-4" />, ariaLabel: "Liste" },
      { key: "group", icon: <AlignLeft aria-hidden="true" className="size-4" />, ariaLabel: "Groupé par état" },
      { key: "grid", icon: <LayoutGrid aria-hidden="true" className="size-4" />, ariaLabel: "Grille d'affiches" },
    ];

    return (
      /* Maquette .vswwrap: hard 1px divider then the icon triplet — the pills
         filter DATA, the switcher changes PRESENTATION, and the two natures
         must not read as one train (A9). */
      <div className="vswwrap" ref={switcherRef}>
        <div role="group" aria-label="Mode d'affichage" className="vsw">
          {modes.map((m) => (
            <button
              key={m.key}
              type="button"
              aria-label={m.ariaLabel}
              aria-pressed={viewMode === m.key}
              onClick={() => {
                setViewMode(m.key);
                // Operator report: switching display mode left the list
                // mid-scroll — a new view reads from its top. The scrollport
                // is the shell's `main`, not the window (AppShell frame).
                scrollRootToTop(switcherRef.current);
              }}
            >
              {m.icon}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      <div className="flex flex-col gap-4 px-[14px] py-2">
        {/* ── Sticky filter zone ──────────────────────────────────────── */}

        {/* Filter zone — the maquette's .filters block, pinned under the
            view tabs (measured heights, no hardcoded offsets): search field,
            then pill train + view switcher behind a hard divider. Only the
            list below scrolls (§5.1); the block's border-bottom is the
            separator the maquette draws. */}
        {/* Pinned directly under the view tabs, inside the scrollport.
            `- 1rem` cancels the shell's `main` padding, exactly as the tabs do
            — the two are one slab and must pin against the same edge.
            `- 1px` closes the seam: the published height is CEILED (61.55 →
            62), so aligning on it exactly left a 0.45 px hairline through
            which the list was visible, scrolling. A sub-pixel gap on a 3×
            screen is over a physical pixel of moving content — the « ça
            tremble » the operator kept seeing. Overlapping is free: the tabs
            paint above (z-30 vs z-20). */}
        <div
          className="filters sticky z-20 -mx-[14px]"
          style={{ top: `calc(var(${VIEWTABS_HEIGHT_VAR}, 58px) - 1rem - 1px)` }}
        >
          <label className="search">
            <SearchIcon aria-hidden="true" />
            <input
              ref={filterInputRef}
              type="search"
              placeholder="Filtrer par nom"
              value={nameFilter}
              onChange={(e) => {
                setNameFilter(e.target.value);
              }}
            />
            {nameFilter !== "" && (
              /* One tap back to the full list — a dozen backspaces was the
                 only way out of a filter on a phone. */
              <button
                type="button"
                className="searchclear"
                aria-label="Effacer le filtre"
                onClick={() => {
                  setNameFilter("");
                  filterInputRef.current?.focus();
                }}
              >
                <X aria-hidden="true" />
              </button>
            )}
          </label>
          {/* data-noswipe: dragging the pill train sideways is how the
              operator reaches the filters that overflow — it must never be
              read as « change view » (operator, 2026-08-08). */}
          <div className="pillbar" data-noswipe>
            <div className="pillscroll">
              {(["tout", "series", "films", "pause"] as const).map((k) => {
                const pm = PILLS[k];
                const count = pm.count(items);
                return (
                  <button
                    key={k}
                    type="button"
                    className="pill"
                    aria-pressed={pill === k}
                    onClick={() => {
                      setPill(k);
                    }}
                  >
                    {pm.label}
                    <span className="c">{String(count)}</span>
                  </button>
                );
              })}
            </div>
            {renderSwitcher()}
          </div>
        </div>
        {/* Everything BELOW the filters declares `touch-pan-y`: vertical to the
            browser, horizontal to the view swipe. The filter zone stays out of
            it on purpose — touch-action intersects down the chain, and a
            `pan-y` ancestor is exactly what stopped the pill train from
            scrolling sideways. */}
        <div className="flex min-w-0 touch-pan-y flex-col gap-4">
        {cadenceCaption != null && (
          <p
            data-testid="cadence-caption"
            className="px-1 text-xs text-muted-foreground"
          >
            {cadenceCaption}
          </p>
        )}

        {/* ── Loading — maquette .skel shimmer, never bare text ──────── */}
        {isLoading && !anyData && (
          <div aria-busy="true" className="flex flex-col gap-2 py-2">
            <p className="sr-only">Chargement…</p>
            <div className="skel" />
            <div className="skel" />
            <div className="skel" />
          </div>
        )}

        {/* ── Error ──────────────────────────────────────────────────── */}
        {isError && (
          <ErrorState title="Impossible de charger les suivis." />
        )}

        {/* ── Empty ──────────────────────────────────────────────────── */}
        {!isLoading && !isError && items.length === 0 && (
          <div className="empty">
            <b>Aucun suivi</b>
            Utilisez le « + » pour en ajouter un.
          </div>
        )}

        {/* ── Filter matched nothing — maquette copy verbatim ─────────── */}
        {!isLoading && !isError && visible.length === 0 && items.length > 0 && (
          <div className="empty">
            <b>Aucun suivi ne correspond</b>
            Change de filtre, ou ajoute un média avec le bouton +.
          </div>
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
            {GROUPS.map((group) => {
              const groupItems = visible.filter((i) =>
                group.of.includes(i.status),
              );
              if (groupItems.length === 0) return null;

              return (
                <section key={group.key} data-testid={`group-${group.key}`}>
                  {/* Same header grammar as the « Maintenant » sections (§13):
                      square tone pip, uppercase-via-CSS label, count at end. */}
                  <h3
                    data-testid="section-head"
                    className="mb-2 flex items-center gap-2 text-left text-sm font-normal"
                  >
                    <span
                      aria-hidden="true"
                      className={`inline-block size-2 shrink-0 rounded-[2px] ${group.pipClass}`}
                    />
                    <span className="text-[11px] font-bold uppercase tracking-[0.07em] text-muted-foreground">
                      {group.label}
                    </span>
                    <span className="ml-auto text-xs font-semibold text-foreground tabular-nums">
                      {String(groupItems.length)}
                    </span>
                  </h3>
                  <div className="flex flex-col gap-2">
                    {groupItems.map((item) => renderCard(item, group.of.length > 1))}
                  </div>
                </section>
              );
            })}
          </div>
        )}

        {/* Grid mode — 3-up poster grid. */}
        {!isLoading && !isError && viewMode === "grid" && visible.length > 0 && (
          <div
            className="grid grid-cols-3 gap-2.5"
            data-testid="grid-container"
          >
            {visible.map(renderTile)}
          </div>
        )}
        </div>
      </div>

      {actions.dialog}

      {/* ── Detail sheet ─────────────────────────────────────────────── */}
      {sheet != null && (
        <FollowDetailSheet
          followedId={sheet.id}
          status={sheet.status}
          kind={asMediaKind(sheet.kind)}
          mediaHref={followMediaRef(sheet)}
          nextSearchAt={sheet.next_search_at ?? null}
          posterUrl={sheet.poster_url ?? null}
          onEditCadence={() => {
            actions.openCadence(sheet);
          }}
          open
          onOpenChange={(open) => {
            if (!open) setSheet(null);
          }}
        />
      )}
    </>
  );
}
