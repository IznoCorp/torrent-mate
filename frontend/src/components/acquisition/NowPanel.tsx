/**
 * NowPanel — the five-section urgency-ordered « Maintenant » view.
 *
 * Composes five building blocks — ``MediaRow``, ``JourneyStrip``,
 * ``FollowDetailSheet``, the ``actionWords`` vocabulary, and the
 * ``useToHandle`` hook — each tested in its own module. This component
 * owns the composition: card/strip linkage, section ordering, and the
 * loading/error/empty guards.
 *
 * Section order is DATA, not a rendering accident (§3.1): what is stopped and
 * waiting on the operator comes BEFORE what advances alone.
 *
 * « À traiter » = blocked media that came from ONE OF OUR acquisitions
 * (``useToHandle().items``).  The crossref line carries ``orphan_count`` —
 * blocked media with NO acquisition provenance — linking to ``/control``.
 * §méthode: never under-count what needs attention.
 *
 * The journey strip renders ONLY for « En vol » and « À traiter » (A5).
 * On a takeable item it would say nothing.  A blocked card's reason must NOT
 * truncate — it is what the operator decides on.  Pass it as ``reason`` (which
 * wraps to two lines), never as ``subtitle`` (which truncates).  §12: an
 * essential piece of information does not share its line.
 */

import { type ReactElement, useCallback, useState } from "react";

import { Link, useNavigate } from "react-router-dom";

import type {
  FollowedSeriesItem,
  JourneyItem,
  ToHandleItem,
  WantedItem,
} from "@/api/acquisition";
import {
  useFollowed,
  useJourneys,
  useDownloads,
  useOverview,
  useToHandle,
  useWanted,
} from "@/hooks/useAcquisition";

import { ErrorState } from "@/components/ds/ErrorState";

import type { AcquisitionDownload } from "@/api/acquisition";
import type { MediaFact } from "@/components/ds/MediaRow";
import { MediaRow } from "@/components/ds/MediaRow";
import { SwipeActions } from "./SwipeActions";
import { useFollowActions } from "./followActions";
import { useBackCloses } from "@/lib/use-back-closes";

import { FollowDetailSheet } from "./FollowDetailSheet";
import { JourneyDetailSheet } from "./JourneyDetailSheet";
import { deriveStage, formatSince, journeyMatchKey, stageElapsed } from "./journey";
import { PendingRunLine } from "./PendingRunLine";
import { DownloadRow, formatEta } from "./DownloadRow";
import { StalledGrabsAlert } from "./StalledGrabsAlert";
import {
  asMediaKind,
  DOWNLOAD_STATE_LABEL,
  DOWNLOAD_STATE_TONE,
  FOLLOW_STATUS_TONE,
  GRAB_FAILURE_LABEL,
  followMediaRef,
  followStatusLabel,
  followWaitingReason,
  followFraction,
  relativeTime,
} from "./meta";

// ---------------------------------------------------------------------------
// Section order — CONSTANT (§3.1)
// ---------------------------------------------------------------------------

/**
 * Section slugs in display order.
 *
 * « À traiter » sits between « À récupérer » and « En vol » because what is
 * stopped and waiting on the operator comes before what advances alone.
 * Tested by the section-order assertion in the test file.
 */
const SECTION_SLUGS = [
  "a-recuperer",
  "a-traiter",
  "en-vol",
  "cherche-rien-trouve",
  "range-aujourdhui",
] as const;

type SectionSlug = (typeof SECTION_SLUGS)[number];

/** Section metadata — pip colour tokens + French label. */
interface SectionMeta {
  readonly label: string;
  readonly pipClass: string;
}

const SECTION_META: Record<SectionSlug, SectionMeta> = {
  "a-recuperer": { label: "À récupérer", pipClass: "bg-warning" },
  "a-traiter": { label: "À traiter", pipClass: "bg-danger" },
  "en-vol": { label: "En vol", pipClass: "bg-info" },
  "cherche-rien-trouve": {
    label: "Cherché, rien trouvé",
    pipClass: "bg-waiting",
  },
  "range-aujourdhui": {
    label: "Rangé aujourd'hui",
    pipClass: "bg-success",
  },
};

// ---------------------------------------------------------------------------
// Resolve href — same shape as ``ToHandleList.tsx:74``
// ---------------------------------------------------------------------------

/**
 * Build the resolve link for a blocked decision item.
 *
 * Reuses the EXACT href shape from ``ToHandleList.tsx:72-74`` —
 * ``/media?decision=<id>``.  Do NOT invent a second builder; the resolution
 * deck is the single destination for every blocked decision.
 *
 * Args:
 *   item: The blocked item from ``useToHandle()``.
 *
 * Returns:
 *   A router ``to`` value for a ``<Link>``.
 */
function resolveHref(item: ToHandleItem): string {
  return `/media?decision=${String(item.decision_id)}`;
}

// ---------------------------------------------------------------------------
// Stage derivation from journey timestamps
// ---------------------------------------------------------------------------


/**
 * The facts an « en vol » card carries, in reading order.
 *
 * Built here rather than inline in the card so what is TRUE about an
 * acquisition in flight is stated once: how far the download is, what state it
 * is in, how long it has been there, and which release was actually grabbed.
 *
 * Args:
 *   download: The live download correlated through the journey, if any.
 *   journey: The correlated acquisition journey, if any.
 *   journeysEnErreur: Whether the journeys read itself failed.
 *
 * Returns:
 *   The facts line, possibly empty.
 */
function enVolFacts(
  download: AcquisitionDownload | undefined,
  journey: JourneyItem | undefined,
  journeysEnErreur: boolean,
): readonly MediaFact[] {
  // A failed journeys read with no live download says nothing here: the
  // section-level error already names the failure, and anything else would
  // claim knowledge we do not have.
  if (journeysEnErreur && download == null) {
    return [];
  }
  const facts: MediaFact[] = [];
  if (download != null) {
    // Live progress folded into the card — percentage, state, and a broken
    // torrent's reason in French (§8).
    facts.push({
      kind: "gauge",
      tone: DOWNLOAD_STATE_TONE[download.state] ?? "neutral",
      text: `${String(Math.round(download.progress * 100))} %`,
    });
    facts.push({
      kind: "note",
      text: DOWNLOAD_STATE_LABEL[download.state] ?? "état inconnu",
    });
    // Maquette FROM card: « 12 min restantes » folded into the card — only
    // while downloading AND known (addition B).
    if (download.state === "downloading" && download.eta_seconds != null) {
      facts.push({ kind: "note", text: formatEta(download.eta_seconds) });
    }
    if (download.error_reason != null && download.error_reason !== "") {
      facts.push({ kind: "alert", text: download.error_reason });
    }
  }
  // Maquette « depuis 4 min » — time spent in the CURRENT stage, when no live
  // download carries the pace; « ~ » marks the spine computed rather than
  // observed (§13).
  if (download == null && journey != null) {
    const ecoule = stageElapsed(journey);
    if (ecoule != null) {
      facts.push({
        kind: "note",
        text: `${ecoule.approx ? "~ " : ""}${formatSince(ecoule.seconds)}`,
      });
    }
  }
  if (!journeysEnErreur) {
    // §14 — two DIFFERENT unknowns, never merged into one sentence: a
    // correlated acquisition whose release name was not recorded, versus a
    // download we could not tie to any recorded acquisition at all. « Non
    // enregistré » claims we consulted the record; that is only true in the
    // first case.
    facts.push({
      kind: "release",
      text:
        journey == null
          ? "Acquisition non corrélée"
          : (journey.release_name ?? "Nom de release non enregistré"),
      hint: journey?.release_name ?? undefined,
    });
  }
  return facts;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Render the « Maintenant » panel — five urgency-ordered sections.
 *
 * Args: none — all data comes from the four TanStack Query hooks consumed
 * internally.
 *
 * Returns:
 *   The panel element.
 */
export function NowPanel(): ReactElement {
  const navigate = useNavigate();
  const followed = useFollowed();
  const wanted = useWanted({ status: "grabbed" });
  // Addition A: the takeable card's « S02E05 · 1080p WEB-DL · 42 sources »
  // reads the follow's pending wanted rows (label + last-search facts).
  // "available", not "pending": a search that concluded takeable PARKS the
  // row as available until the grab pass takes it — pending rows are the
  // not-yet-searched ones and never carry last-search facts.
  // page_size is raised past the server default: the correlation is per
  // FOLLOW, so a page-1 cut would silently strip the detail (and any failure
  // explanation) from the follows whose rows fell off the page.
  const takeableWanted = useWanted({ status: "available", page_size: 200 });
  const toHandle = useToHandle();
  const journeys = useJourneys();
  const overview = useOverview();
  const toHandleDegraded = toHandle.data?.degraded ?? false;
  const actions = useFollowActions();
  const [journeySheet, setJourneySheet] = useState<{
    journey: JourneyItem;
    title: string;
  } | null>(null);
  const downloadsQuery = useDownloads();
  const downloads = downloadsQuery.data?.downloads ?? [];
  const clientAvailable = downloadsQuery.data?.client_available ?? true;

  // Follow poster lookup — the in-flight and takeable cards correlate to
  // their follow by id; a card with a known follow must never fall back to
  // the monogram while the poster exists (operator report, Ninja Turtles).
  const posterByFollow = new Map<number, string | null>();
  for (const f of followed.data?.items ?? []) {
    posterByFollow.set(f.id, f.poster_url ?? null);
  }

  // Build a lookup from (title+kind+season+episode) → journey so each
  // « En vol » card can derive its real stage instead of hardcoding « pris ».
  const journeyByKey = new Map<string, JourneyItem>();
  for (const j of journeys.data?.journeys ?? []) {
    const key = journeyMatchKey(
      j.follow_title ?? "",
      j.kind ?? "show",
      j.season ?? null,
      j.episode ?? null,
    );
    // First journey wins for each key (most-recent-grabbed-first from the API).
    if (!journeyByKey.has(key)) journeyByKey.set(key, j);
  }

  // ── Detail-sheet state ────────────────────────────────────────────────

  // The sheet keeps the whole item: every derived prop (status, kind, href,
  // next search, cadence target) reads ONE source instead of a copied subset
  // that drifts the moment the item gains a field.
  const [sheet, setSheet] = useState<FollowedSeriesItem | null>(null);
  // Back gesture closes whichever detail layer is open instead of leaving
  // the page. One hook per layer; only the open one holds a marker entry.
  useBackCloses(
    journeySheet != null,
    useCallback(() => {
      setJourneySheet(null);
    }, []),
  );
  useBackCloses(
    sheet != null,
    useCallback(() => {
      setSheet(null);
    }, []),
  );

  // ── Derived sections ──────────────────────────────────────────────────

  /** « À récupérer » — followed items the server says are takeable right now. */
  const aRecuperer: readonly FollowedSeriesItem[] =
    followed.data?.items.filter((i) => i.status === "to_grab") ?? [];

  /** « À traiter » — blocked items from our acquisitions. */
  const toHandleItems: readonly ToHandleItem[] = toHandle.data?.items ?? [];
  const orphanCount = toHandle.data?.orphan_count ?? 0;

  /** « En vol » — wanted items currently in the pipeline (status=grabbed). */
  const enVol: readonly WantedItem[] = wanted.data?.items ?? [];

  /** « Cherché, rien trouvé » — searched, nothing conforming (§14.1 rest
   *  state), PLUS active never-verified follows (maquette renderNow: a
   *  follow the machine has not checked yet is also waiting on nothing). */
  const searchedNothingFound: readonly FollowedSeriesItem[] =
    followed.data?.items.filter(
      (i) =>
        i.active && (i.status === "pending" || i.status === "unverified"),
    ) ?? [];

  /** « Rangé aujourd'hui » — follows whose journey DISPATCHED today.
   *
   * NOT every `a_jour` follow: that status is the permanent steady state of
   * every complete série, and rendering them all here flooded the
   * urgency-ordered screen with what needs nothing. « aujourd'hui » is a
   * date, so the derivation reads one: a correlated journey dispatched since
   * local midnight. */
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  // title → most recent dispatch: the compact row says WHEN it landed and,
  // for a série, WHICH episode did (maquette: « Friends · S10E12 »).
  const dispatchedToday = new Map<
    string,
    { at: number; season: number | null; episode: number | null }
  >();
  for (const j of journeys.data?.journeys ?? []) {
    if (
      j.dispatched_at == null ||
      j.dispatched_at * 1000 < startOfToday.getTime()
    )
      continue;
    const t = j.follow_title;
    if (t == null || t === "") continue;
    const prev = dispatchedToday.get(t);
    if (prev == null || j.dispatched_at > prev.at) {
      dispatchedToday.set(t, {
        at: j.dispatched_at,
        season: j.season ?? null,
        episode: j.episode ?? null,
      });
    }
  }
  const rangeAujourdhui: readonly FollowedSeriesItem[] =
    followed.data?.items.filter(
      // Both settled statuses, not just « à jour »: a série whose LAST episode
      // landed today reads « Terminé » from that moment on, and it is exactly
      // the one the operator most wants to see in « rangé aujourd'hui ».
      (i) =>
        (i.status === "up_to_date" || i.status === "ended") &&
        dispatchedToday.has(i.title),
    ) ?? [];

  // ── Download ↔ journey correlation (info_hash) ────────────────────────
  // A download correlated with an « En vol » card folds INTO that card — the
  // progress belongs to the media it advances. Only downloads no card claims
  // keep a standalone row, so nothing is shown twice and nothing is dropped.
  const downloadByHash = new Map(downloads.map((d) => [d.info_hash, d]));
  const correlatedHashes = new Set<string>();
  for (const item of enVol) {
    const j = journeyByKey.get(
      journeyMatchKey(item.title, item.kind, item.season ?? null, item.episode ?? null),
    );
    if (j != null && downloadByHash.has(j.info_hash)) correlatedHashes.add(j.info_hash);
  }
  const uncorrelatedDownloads = downloads.filter(
    (d) => !correlatedHashes.has(d.info_hash),
  );

  // ── Section visibility ────────────────────────────────────────────────

  const sectionList = SECTION_SLUGS.map((slug) => {
    const count =
      slug === "a-recuperer"
        ? aRecuperer.length
        : slug === "a-traiter"
          ? toHandleItems.length
          : slug === "en-vol"
            ? // A correlated download IS its card — counting both would
              // announce more in-flight items than exist.
              enVol.length + uncorrelatedDownloads.length
            : slug === "cherche-rien-trouve"
              ? searchedNothingFound.length
              : rangeAujourdhui.length;

    // « À traiter » renders when items>0 OR orphans>0 (§3.2),
    // OR when the hook errored — panne ≠ absence: a failed fetch must
    // never collapse the section that was supposed to alert the operator.
    // « En vol » follows the same rule for its own reasons to speak: a torrent
    // still downloading, an unreachable client, or a failed read. Any of them
    // alone must open the section — gating it on "are there wanted rows" would
    // re-create the silence this section exists to end.
    const visible =
      slug === "a-traiter"
        ? toHandleItems.length > 0 ||
          orphanCount > 0 ||
          toHandle.isError ||
          toHandleDegraded
        : slug === "en-vol"
          ? count > 0 ||
            downloads.length > 0 ||
            !clientAvailable ||
            wanted.isError ||
            downloadsQuery.isError ||
            journeys.isError
          : slug === "a-recuperer"
            ? count > 0 || followed.isError
            : count > 0;

    return { slug, count, visible };
  });

  const allEmpty = sectionList.every((s) => !s.visible);

  // ── Loading / error guards ────────────────────────────────────────────
  // § panne ≠ absence : a failure to know must never be rendered as
  // knowledge that there is nothing (§14.1 rest-state rule, applied to
  // the client side).

  // journeys and downloads included: without them the first paint showed
  // stripless, percentless cards — indistinguishable from items that simply
  // have no progress, which is a false statement made briefly on every load.
  const anyLoading =
    followed.isLoading ||
    wanted.isLoading ||
    toHandle.isLoading ||
    journeys.isLoading ||
    downloadsQuery.isLoading;
  const anyData =
    followed.data != null || wanted.data != null || toHandle.data != null;
  const anyError =
    followed.isError || wanted.isError || toHandle.isError;

  // ── Render helpers ────────────────────────────────────────────────────

  /** Render the section header — count is items.length (§3.2). */
  function renderHeader(slug: SectionSlug, count: number): ReactElement {
    const m = SECTION_META[slug];
    return (
      /* A heading, NOT a button: it had no onClick, and a focusable control
         announced as actionable that does nothing is a dead control (§11) —
         five of them per screen for assistive tech. */
      <h3
        data-testid="section-head"
        className="mb-2 flex w-full items-center gap-2 text-left text-sm font-normal"
      >
        <span
          aria-hidden="true"
          className={`inline-block size-2 shrink-0 rounded-[2px] ${m.pipClass}`}
        />
        {/* Uppercase via CSS: the DOM keeps the French label as data. */}
        <span className="text-[11px] font-bold uppercase tracking-[0.07em] text-muted-foreground">
          {m.label}
        </span>
        <span className="ml-auto text-xs font-semibold text-foreground tabular-nums">
          {String(count)}
        </span>
      </h3>
    );
  }

  /**
   * The « Cherché, rien trouvé » meta line: the search verdict (films carry
   * one per unit) and the next scheduled check — WHY nothing landed and WHEN
   * the machine looks again, which is what a resting card owes the operator.
   */
  function searchMetaLine(item: FollowedSeriesItem): string {
    // Maquette waiting card: the verdict, then WHEN the machine last looked
    // (« rien de conforme au profil · il y a 3 h ») — the LAST search, not
    // the next-check substitute (backend addition C). A never-verified
    // follow says WHY it rests instead of faking a verdict (§14).
    const reason =
      item.status === "unverified"
        ? "pas encore vérifié sur les trackers"
        : (followWaitingReason(item) ?? "rien de conforme au dernier passage");
    return item.last_search_at != null
      ? `${reason} · ${relativeTime(item.last_search_at)}`
      : reason;
  }

  /** Earliest takeable wanted row carried by this follow, or null. */
  function takeableRow(item: FollowedSeriesItem): WantedItem | null {
    const rows = (takeableWanted.data?.items ?? []).filter(
      (w) => w.followed_id === item.id,
    );
    if (rows.length === 0) return null;
    return (
      [...rows].sort(
        (a, b) =>
          (a.season ?? 0) - (b.season ?? 0) || (a.episode ?? 0) - (b.episode ?? 0),
      )[0] ?? null
    );
  }

  /** Maquette takeable sub: earliest takeable gap + last-search facts —
   *  each segment only when truly known (no invented quality, §14). */
  function takeableDetail(item: FollowedSeriesItem): string | null {
    const w = takeableRow(item);
    if (w == null) return null;
    const parts: string[] = [];
    if (w.season != null && w.episode != null) {
      parts.push(
        `S${String(w.season).padStart(2, "0")}E${String(w.episode).padStart(2, "0")}`,
      );
    }
    const quality = [w.last_search_best?.resolution, w.last_search_best?.source]
      .filter((v): v is string => v != null && v !== "")
      .join(" ");
    if (quality !== "") parts.push(quality);
    if (w.last_search_found != null) {
      parts.push(`${String(w.last_search_found)} source${w.last_search_found > 1 ? "s" : ""}`);
    }
    return parts.length > 0 ? parts.join(" · ") : null;
  }

  /** Why the last grab attempt for this takeable item failed — French, or null.
   *
   *  §8 (rien en silence): a takeable card whose grabs keep failing must SAY
   *  so — the operator watched « Ninja Turtles » freeze through four
   *  identical fetch failures that only Telegram ever saw. */
  function grabFailureLine(item: FollowedSeriesItem): string | null {
    const w = takeableRow(item);
    if (w?.last_grab_reason == null) return null;
    const label =
      GRAB_FAILURE_LABEL[w.last_grab_reason] ?? "la récupération a échoué";
    // No attempt count: `attempts` counts every tracker interaction (search
    // claims included, and it is refunded on an inconclusive search), so
    // rendering it as « n tentatives » of RÉCUPÉRATION would state a number
    // that means something else. The timestamp carries the « it is stuck »
    // signal on its own.
    const when =
      w.last_grab_at != null ? ` · ${relativeTime(w.last_grab_at)}` : "";
    return `Récupération en échec : ${label}${when}`;
  }

  /** Render one followed-item card (used by two sections). */
  function renderFollowedCard(
    item: FollowedSeriesItem,
    searchMeta = false,
  ): ReactElement {
    const sheetHref = followMediaRef(item);
    return (
      /* A10/A11 — same gesture and kebab grammar as « Suivis », from the same
         builder (§13). The takeable card's swipe pares down to the two verbs
         of the moment (maquette): Récupérer / Pause — no Retirer here. */
      <SwipeActions
        key={item.id}
        {...actions.swipeFor(item, { remove: searchMeta })}
      >
        <MediaRow
          title={item.title}
          posterUrl={item.poster_url ?? null}
          {...(searchMeta
            ? { subtitle: searchMetaLine(item) }
            : item.status === "to_grab" && takeableDetail(item) != null
              ? { subtitle: takeableDetail(item) ?? "" }
              : {})}
          {...(!searchMeta &&
          item.status === "to_grab" &&
          grabFailureLine(item) != null
            ? { reason: grabFailureLine(item) ?? "" }
            : {})}
          /* Maquette followRow: mono fraction + dotted status chip on the
             takeable card; the resting card carries its verdict as the
             subtitle and NOTHING else — no fraction there (maquette). */
          facts={[
            ...(!searchMeta && followFraction(item) != null
              ? [{ kind: "fraction" as const, text: followFraction(item) ?? "" }]
              : []),
            ...(!searchMeta
              ? [{
                  kind: "chip" as const,
                  tone: FOLLOW_STATUS_TONE[item.status],
                  text: followStatusLabel(item.status, item.kind),
                }]
              : []),
            ...(item.tvdb_unresolved
              ? [{
                  kind: "chip" as const,
                  tone: "warning",
                  text: "Sans ID TVDB",
                  hint: "Détection d'épisodes indisponible : l'ID TVDB n'a pas pu être résolu.",
                }]
              : []),
          ]}
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

  /**
   * Compact « rangé aujourd'hui » row — done work earns one line, not a card.
   *
   * §12: the urgency-ordered screen spends its height on what still needs the
   * operator; what already landed is an acknowledgement. The row still opens
   * the detail sheet — done is not dead (§11).
   */
  function renderRangeRow(item: FollowedSeriesItem): ReactElement {
    const disp = dispatchedToday.get(item.title);
    const ep =
      disp?.season != null && disp.episode != null
        ? ` · S${String(disp.season).padStart(2, "0")}E${String(disp.episode).padStart(2, "0")}`
        : "";
    return (
      <button
        key={item.id}
        type="button"
        data-testid="range-row"
        className="flex w-full items-center gap-2 rounded-md px-1 py-1.5 text-left text-sm hover:bg-accent"
        onClick={() => {
          setSheet(item);
        }}
      >
        <span aria-hidden="true" className="shrink-0 text-success">
          ✓
        </span>
        <span className="min-w-0 truncate">
          {item.title}
          {ep !== "" && <span className="text-muted-foreground">{ep}</span>}
        </span>
        {disp != null && (
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {relativeTime(disp.at)}
          </span>
        )}
      </button>
    );
  }

  /** Render one « à traiter » card with its journey strip + resolve action. */
  function renderToHandleCard(item: ToHandleItem): ReactElement {
    // Maquette blocked sub: « S16E12 · titre ambigu — … » — the episode
    // identity from the provenance spine opens the reason line.
    const epLabel =
      item.season != null && item.episode != null
        ? `S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")}`
        : null;
    return (
      <MediaRow
        key={item.decision_id}
        title={item.title}
        posterUrl={null}
        {...(item.year != null ? { subtitle: String(item.year) } : {})}
        // §12: blocking reason wraps, never truncates — `reason`, not `subtitle`.
        reason={epLabel != null ? `${epLabel} · ${item.reason}` : item.reason}
        // Blocked items have no resolved provider id — no poster link (§11).
        // No onOpen either — a button that does nothing is a dead control (§11).
        journey={{ stage: item.stage, blocked: true }}
        // « Résoudre → » is the card's own action (full width, under the
        // strip), NOT a fact — nested interactive regions are invalid HTML, so
        // a link inside the facts line would put a button inside another
        // button at any width below md.
        action={{ label: "Résoudre →", href: resolveHref(item), tone: "danger" }}
      />
    );
  }

  /** Render one « en vol » card with its journey strip. */
  function renderEnVolCard(item: WantedItem): ReactElement {
    const matchKey = journeyMatchKey(
      item.title,
      item.kind,
      item.season ?? null,
      item.episode ?? null,
    );
    const journey = journeyByKey.get(matchKey);
    const stage = deriveStage(journey);
    // The live download correlated through the journey's info_hash — its
    // progress belongs ON this card, not in a separate list (§12).
    const download =
      journey != null ? downloadByHash.get(journey.info_hash) : undefined;
    // The wanted row carries no provider ids, but its correlated journey does:
    // an identified in-flight media leads to its sheet like any other (§11).
    const sheetHref =
      journey != null
        ? followMediaRef({ media_ref: journey.media_ref, kind: item.kind })
        : null;

    return (
      <MediaRow
        key={item.id}
        title={item.title}
        // Operator report: the in-flight card showed a bare monogram while
        // the FOLLOW carries the poster — correlate through followed_id.
        posterUrl={
          item.followed_id != null
            ? (posterByFollow.get(item.followed_id) ?? null)
            : null
        }
        {...(sheetHref != null
          ? {
              onPoster: () => {
                void navigate(sheetHref);
              },
            }
          : {
              // Identified (the title comes from the follow) — merely not
              // linkable from here. « Média non identifié » would be false.
              posterHint: "Pas de lien vers la fiche depuis cette carte.",
            })}
        {...(item.season != null
          ? {
              subtitle: `S${String(item.season).padStart(2, "0")}${
                item.episode != null ? `E${String(item.episode).padStart(2, "0")}` : ""
              }`,
            }
          : {})}
        // The release ACTUALLY grabbed — what tells a FLAC soundtrack apart
        // from the film of the same name. Never a media title standing in for
        // it. Three cases, three renders: a name (show it), a journey without
        // one (admit it was not recorded), and a FAILED journeys read (say
        // nothing here — the section-level error already names the failure,
        // and « non enregistré » would claim knowledge we do not have).
        facts={enVolFacts(download, journey, journeys.isError)}
        // §3 — « Voir le parcours » per item: the body opens the journey
        // detail when a correlated journey exists. Without one there is
        // nothing to open, so no onOpen (§11).
        {...(journey != null
          ? {
              onOpen: () => {
                setJourneySheet({ journey, title: item.title });
              },
            }
          : {})}
        // Stage derived from the real journey, not hardcoded « pris ».
        // When the stage cannot be established (no journey match or a
        // reconstructed row with gaps), the strip is omitted entirely —
        // §14.3: « inconnue » is NOT « pas faite ».
        {...(stage != null ? { journey: { stage } } : {})}
      />
    );
  }

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <>
      {/* `touch-pan-y`: vertical belongs to the browser, horizontal to the view
          swipe. This panel has no horizontal scroller of its own, so the whole
          of it can say so. */}
      <div className="flex touch-pan-y flex-col gap-4 px-[14px] py-2">
        {/* Above the sections, not inside one: this is work that has STOPPED,
            and it belongs to no stage — an acquisition parked at « récupéré »
            is neither takeable nor in flight. It renders nothing when nothing
            is parked, because a permanent alert stops being one. */}
        {/* A failed overview read is NOT « nothing is parked »: the count
            falling back to 0 would silence the one alert built to end that
            exact silence. */}
        {overview.isError ? (
          <ErrorState title="Impossible de vérifier les acquisitions parquées." />
        ) : (
          <>
            <StalledGrabsAlert count={overview.data?.stalled_grabs ?? 0} />
            {/* §8/DOIT-2 — the watcher's wait, said out loud. */}
            <PendingRunLine pending={overview.data?.pending_run} />
          </>
        )}

        {sectionList.map((s) => {
          if (!s.visible) return null;

          return (
            <section key={s.slug} data-testid={`section-${s.slug}`}>
              {renderHeader(s.slug, s.count)}

              {/* Error states — panne ≠ absence: a failed fetch must never
                   render as an empty section (§14.1 rest-state rule). */}
              {s.slug === "a-traiter" && toHandle.isError && (
                <ErrorState title="Impossible de charger les éléments à traiter." />
              )}
              {/* The server answered, but could not read: an empty list and a
                  failed read are different facts. Saying « rien à traiter »
                  here would state the one thing we do not know. */}
              {s.slug === "a-traiter" && !toHandle.isError && toHandleDegraded && (
                <ErrorState title="Impossible de savoir ce qui est à traiter — la lecture n'a pas abouti." />
              )}
              {s.slug === "en-vol" && wanted.isError && (
                <ErrorState title="Impossible de charger les éléments en vol." />
              )}
              {/* A failed journeys fetch drops every strip; a failed downloads
                  fetch drops every percentage. Silently, the cards would look
                  like items that simply have no progress to show — panne ≠
                  absence applies to a PART of a section, not only to all of it. */}
              {s.slug === "en-vol" && journeys.isError && (
                <ErrorState title="Impossible de charger les parcours — les étapes ne sont pas affichées." />
              )}
              {s.slug === "en-vol" && downloadsQuery.isError && (
                <ErrorState title="Impossible de charger la progression des téléchargements." />
              )}
              {(s.slug === "a-recuperer" ||
                s.slug === "cherche-rien-trouve" ||
                s.slug === "range-aujourdhui") &&
                followed.isError && (
                  <ErrorState title="Impossible de charger les suivis." />
                )}

              {/* « À récupérer » */}
              {s.slug === "a-recuperer" &&
                aRecuperer.map((i) => renderFollowedCard(i))}

              {/* « À traiter » — cards + crossref for orphans */}
              {s.slug === "a-traiter" && (
                <>
                  {!toHandle.isError && toHandleItems.map(renderToHandleCard)}
                  {/* Crossref — orphans with NO acquisition provenance (§3.1).
                       Renders whenever orphans exist, even alongside items —
                       §méthode: never under-count what needs attention. */}
                  {orphanCount > 0 && (
                    /* Maquette .crossref: dashed border, destination pinned
                       right in primary — the row reads as a signpost, not a
                       card. */
                    <Link to="/control" className="crossref">
                      {orphanCount === 1
                        ? "1 autre média à traiter ne vient pas d'une acquisition"
                        : `${String(orphanCount)} autres médias à traiter ne viennent pas d'une acquisition`}
                      <span>Contrôle →</span>
                    </Link>
                  )}
                </>
              )}

              {/* « En vol » */}
              {s.slug === "en-vol" && (
                <>
                  {/* Fail-soft, and deliberately OUTSIDE the list: it must show
                      even when the list is empty. An unreachable client makes
                      progress unknowable — saying nothing would let the absence
                      of rows read as « nothing is downloading », which is a
                      different and false statement (§8, panne ≠ absence). */}
                  {!clientAvailable && (
                    <p className="mb-3 text-xs text-warning">
                      Client torrent injoignable — progression indisponible, les
                      éléments récupérés restent listés.
                    </p>
                  )}
                  {enVol.map(renderEnVolCard)}
                  {/* Downloads NO card claims — grabs the follow layer does
                      not know about. Correlated ones already live on their
                      card; dropping these would hide real in-flight work. */}
                  {uncorrelatedDownloads.length > 0 && (
                    <div className="mt-3 flex flex-col gap-4">
                      {uncorrelatedDownloads.map((d) => (
                        <DownloadRow key={d.info_hash || d.name} d={d} />
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* « Cherché, rien trouvé » — verdict + next check, not counts. */}
              {s.slug === "cherche-rien-trouve" &&
                searchedNothingFound.map((i) => renderFollowedCard(i, true))}

              {/* « Rangé aujourd'hui » — compact acknowledgement rows. */}
              {s.slug === "range-aujourdhui" &&
                rangeAujourdhui.map((i) => renderRangeRow(i))}
            </section>
          );
        })}

        {/* Loading — all sections empty, data hasn't landed yet.
            MUST NOT show « Rien à signaler » while a fetch is in flight.
            Maquette grammar: .skel shimmer cards, never bare text. */}
        {allEmpty && anyLoading && !anyData && (
          <div aria-busy="true" className="flex flex-col gap-2 py-2">
            <p className="sr-only">Chargement…</p>
            <div className="skel" />
            <div className="skel" />
            <div className="skel" />
          </div>
        )}

        {/* Empty state — all five sections are empty AND data has loaded
            AND no hook is in error (§ panne ≠ absence). */}
        {allEmpty && !anyLoading && !anyError && (
          <div className="empty">
            <b>Rien à signaler</b>
            — tout est en ordre.
          </div>
        )}

        {/* All hooks errored with no data — the panel cannot render anything
            but must NOT read as « there is nothing » (§14.1). */}
        {allEmpty && !anyLoading && anyError && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Impossible de charger les données — veuillez réessayer.
          </p>
        )}
      </div>

      {actions.dialog}

      {journeySheet != null && (
        <JourneyDetailSheet
          journey={journeySheet.journey}
          title={journeySheet.title}
          open
          onOpenChange={(open) => {
            if (!open) setJourneySheet(null);
          }}
        />
      )}

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
