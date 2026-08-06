/**
 * MaintenantPanel — the five-section urgency-ordered « Maintenant » view.
 *
 * Five building blocks shipped in earlier tasks are composed here:
 * ``AcquisitionCard`` (T5), ``JourneyStrip`` (T6), ``FollowDetailSheet`` (T10),
 * the ``actionWords`` vocabulary (T4), and the ``useToHandle`` hook (T3).
 *
 * Section order is DATA, not a rendering accident (§3.1): what is stopped and
 * waiting on the operator comes BEFORE what advances alone.
 *
 * « À traiter » = blocked media that came from ONE OF OUR acquisitions
 * (``useToHandle().items``).  The crossref line carries ``orphan_count`` —
 * blocked media with NO acquisition provenance — linking to ``/controle``.
 * §méthode: never under-count what needs attention.
 *
 * The journey strip renders ONLY for « En vol » and « À traiter » (A5).
 * On a takeable item it would say nothing.  A blocked card's reason must NOT
 * truncate — it is what the operator decides on.  Pass it as ``reason`` (which
 * wraps to two lines), never as ``subtitle`` (which truncates).  §12: an
 * essential piece of information does not share its line.
 */

import { type ReactElement, useState } from "react";

import { Link } from "react-router-dom";

import type { FollowedSeriesItem, ToHandleItem, WantedItem } from "@/api/acquisition";
import {
  useDownloads,
  useFollowed,
  useToHandle,
  useWanted,
} from "@/hooks/useAcquisition";

import { AcquisitionCard } from "./AcquisitionCard";
import { FollowDetailSheet } from "./FollowDetailSheet";
import { JourneyStrip } from "./JourneyStrip";
import type { FollowStatus, MediaKind } from "./meta";

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
  "a-recuperer": { label: "À récupérer", pipClass: "border-warning bg-warning" },
  "a-traiter": { label: "À traiter", pipClass: "border-danger bg-danger" },
  "en-vol": { label: "En vol", pipClass: "border-info bg-info" },
  "cherche-rien-trouve": {
    label: "Cherché, rien trouvé",
    pipClass: "border-waiting bg-waiting",
  },
  "range-aujourdhui": {
    label: "Rangé aujourd'hui",
    pipClass: "border-success bg-success",
  },
};

// ---------------------------------------------------------------------------
// Resolve href — same shape as ``ATraiterList.tsx:74``
// ---------------------------------------------------------------------------

/**
 * Build the resolve link for a blocked decision item.
 *
 * Reuses the EXACT href shape from ``ATraiterList.tsx:72-74`` —
 * ``/medias?decision=<id>``.  Do NOT invent a second builder; the resolution
 * deck is the single destination for every blocked decision.
 *
 * Args:
 *   item: The blocked item from ``useToHandle()``.
 *
 * Returns:
 *   A router ``to`` value for a ``<Link>``.
 */
function resolveHref(item: ToHandleItem): string {
  return `/medias?decision=${String(item.decision_id)}`;
}

// ---------------------------------------------------------------------------
// Narrowing helpers
// ---------------------------------------------------------------------------

/**
 * Narrow a server ``kind`` string to the ``MediaKind`` union.
 *
 * Falls back to ``"show"`` for unknown values — never crashes on a new kind.
 */
function asMediaKind(kind: string): MediaKind {
  if (kind === "movie" || kind === "show" || kind === "season") return kind;
  return "show";
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
export function MaintenantPanel(): ReactElement {
  const followed = useFollowed();
  const wanted = useWanted({ status: "grabbed" });
  const toHandle = useToHandle();
  // Polled for live progress; consumed by a later task that augments
  // « En vol » cards with download progress bars.
  void useDownloads();

  // ── Detail-sheet state ────────────────────────────────────────────────

  const [sheet, setSheet] = useState<{
    followedId: number;
    status: FollowStatus;
    kind: MediaKind;
  } | null>(null);

  // ── Derived sections ──────────────────────────────────────────────────

  /** « À récupérer » — followed items the server says are takeable right now. */
  const aRecuperer: readonly FollowedSeriesItem[] =
    followed.data?.items.filter((i) => i.status === "a_recuperer") ?? [];

  /** « À traiter » — blocked items from our acquisitions. */
  const aTraiter: readonly ToHandleItem[] = toHandle.data?.items ?? [];
  const orphanCount = toHandle.data?.orphan_count ?? 0;

  /** « En vol » — wanted items currently in the pipeline (status=grabbed). */
  const enVol: readonly WantedItem[] = wanted.data?.items ?? [];

  /** « Cherché, rien trouvé » — searched, nothing conforming (§14.1 rest state). */
  const chercheRienTrouve: readonly FollowedSeriesItem[] =
    followed.data?.items.filter((i) => i.status === "en_attente") ?? [];

  /** « Rangé aujourd'hui » — fully acquired, everything is on the disks. */
  const rangeAujourdhui: readonly FollowedSeriesItem[] =
    followed.data?.items.filter((i) => i.status === "a_jour") ?? [];

  // ── Section visibility ────────────────────────────────────────────────

  const sectionList = SECTION_SLUGS.map((slug) => {
    const count =
      slug === "a-recuperer"
        ? aRecuperer.length
        : slug === "a-traiter"
          ? aTraiter.length
          : slug === "en-vol"
            ? enVol.length
            : slug === "cherche-rien-trouve"
              ? chercheRienTrouve.length
              : rangeAujourdhui.length;

    // « À traiter » renders when items>0 OR orphans>0 (§3.2).
    const visible =
      slug === "a-traiter"
        ? aTraiter.length > 0 || orphanCount > 0
        : count > 0;

    return { slug, count, visible };
  });

  const allEmpty = sectionList.every((s) => !s.visible);

  // ── Render helpers ────────────────────────────────────────────────────

  /** Render the section header — count is items.length (§3.2). */
  function renderHeader(slug: SectionSlug, count: number): ReactElement {
    const m = SECTION_META[slug];
    return (
      <button
        type="button"
        data-testid="section-head"
        className="mb-2 flex w-full items-center gap-2 text-left"
      >
        <span
          aria-hidden="true"
          className={`inline-block size-[9px] shrink-0 rounded-full border-[1.5px] ${m.pipClass}`}
        />
        <span className="text-sm font-medium">{m.label}</span>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {String(count)}
        </span>
      </button>
    );
  }

  /** Render one followed-item card (used in three sections). */
  function renderFollowedCard(item: FollowedSeriesItem): ReactElement {
    const kind = asMediaKind(item.kind);
    return (
      <AcquisitionCard
        key={item.id}
        title={item.title}
        posterUrl={item.poster_url ?? null}
        {...(item.year != null ? { subtitle: String(item.year) } : {})}
        meta={null}
        onOpen={() => {
          setSheet({ followedId: item.id, status: item.status, kind });
        }}
        {...(item.tvdb_unresolved
          ? {}
          : {
              onPoster: () => {
                /* Poster tap → media sheet (A13). Wired in a later task. */
              },
            })}
      />
    );
  }

  /** Render one « à traiter » card with its journey strip + resolve action. */
  function renderATraiterCard(item: ToHandleItem): ReactElement {
    return (
      <AcquisitionCard
        key={item.decision_id}
        title={item.title}
        posterUrl={null}
        {...(item.year != null ? { subtitle: String(item.year) } : {})}
        // §12: blocking reason wraps, never truncates — `reason`, not `subtitle`.
        reason={item.reason}
        meta={null}
        onOpen={() => {
          /* Blocked items have no detail sheet — « Résoudre → » is their action. */
        }}
        // Blocked items have no resolved provider id — no poster link (§11).
        strip={<JourneyStrip stage={item.stage} blocked />}
        // « Résoudre → » lives in footer (full width, under the strip),
        // NOT in meta — nested interactive regions are invalid HTML
        // (carried forward from Task 5's review, resolution 4).
        footer={
          <Link
            to={resolveHref(item)}
            className="mt-[10px] block w-full rounded-md border border-border py-2 text-center text-sm hover:bg-accent"
          >
            Résoudre →
          </Link>
        }
      />
    );
  }

  /** Render one « en vol » card with its journey strip. */
  function renderEnVolCard(item: WantedItem): ReactElement {
    return (
      <AcquisitionCard
        key={item.id}
        title={item.title}
        posterUrl={null}
        {...(item.season != null
          ? {
              subtitle: `S${String(item.season).padStart(2, "0")}${
                item.episode != null ? `E${String(item.episode).padStart(2, "0")}` : ""
              }`,
            }
          : {})}
        meta={null}
        onOpen={() => {
          /* Grabbed items have no detail sheet yet — future tasks may wire
             a pipeline-progress detail here. */
        }}
        strip={<JourneyStrip stage="pris" />}
      />
    );
  }

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <>
      <div className="flex flex-col gap-4 px-3 py-3">
        {sectionList.map((s) => {
          if (!s.visible) return null;

          return (
            <section key={s.slug} data-testid={`section-${s.slug}`}>
              {renderHeader(s.slug, s.count)}

              {/* « À récupérer » */}
              {s.slug === "a-recuperer" && aRecuperer.map(renderFollowedCard)}

              {/* « À traiter » — cards + crossref for orphans */}
              {s.slug === "a-traiter" && (
                <>
                  {aTraiter.map(renderATraiterCard)}
                  {/* Crossref — orphans with NO acquisition provenance (§3.1). */}
                  {aTraiter.length === 0 && orphanCount > 0 && (
                    <Link
                      to="/controle"
                      className="block rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent"
                    >
                      {orphanCount === 1
                        ? "1 autre média à traiter ne vient pas d'une acquisition → Contrôle"
                        : `${String(orphanCount)} autres médias à traiter ne viennent pas d'une acquisition → Contrôle`}
                    </Link>
                  )}
                </>
              )}

              {/* « En vol » */}
              {s.slug === "en-vol" && enVol.map(renderEnVolCard)}

              {/* « Cherché, rien trouvé » */}
              {s.slug === "cherche-rien-trouve" &&
                chercheRienTrouve.map(renderFollowedCard)}

              {/* « Rangé aujourd'hui » */}
              {s.slug === "range-aujourdhui" &&
                rangeAujourdhui.map(renderFollowedCard)}
            </section>
          );
        })}

        {/* Empty state — all five sections are empty.
            MUST NOT appear when any pile is non-zero (test asserts this). */}
        {allEmpty && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Rien à signaler — tout est en ordre.
          </p>
        )}
      </div>

      {/* ── Detail sheet ─────────────────────────────────────────────── */}
      {sheet != null && (
        <FollowDetailSheet
          followedId={sheet.followedId}
          status={sheet.status}
          kind={sheet.kind}
          open
          onOpenChange={() => {
            setSheet(null);
          }}
        />
      )}
    </>
  );
}
