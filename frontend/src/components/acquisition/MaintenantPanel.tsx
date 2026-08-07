/**
 * MaintenantPanel — the five-section urgency-ordered « Maintenant » view.
 *
 * Composes five building blocks — ``AcquisitionCard``, ``JourneyStrip``,
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

import { AcquisitionCard } from "./AcquisitionCard";
import { SwipeActions } from "./SwipeActions";
import { useFollowActions } from "./followActions";
import { FollowDetailSheet } from "./FollowDetailSheet";
import { JourneyDetailSheet } from "./JourneyDetailSheet";
import { deriveStage, journeyMatchKey } from "./journey";
import { PendingRunLine } from "./PendingRunLine";
import { JourneyStrip } from "./JourneyStrip";
import { DownloadRow } from "./DownloadRow";
import { StalledGrabsAlert } from "./StalledGrabsAlert";
import {
  asMediaKind,
  type FollowStatus,
  followMediaRef,
  type MediaKind,
  followCountsCaption,
  followFraction,
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
// Stage derivation from journey timestamps
// ---------------------------------------------------------------------------


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
  const navigate = useNavigate();
  const followed = useFollowed();
  const wanted = useWanted({ status: "grabbed" });
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

  const [sheet, setSheet] = useState<{
    followedId: number;
    status: FollowStatus;
    kind: MediaKind;
    mediaHref: string | null;
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

  /** « Rangé aujourd'hui » — follows whose journey DISPATCHED today.
   *
   * NOT every `a_jour` follow: that status is the permanent steady state of
   * every complete série, and rendering them all here flooded the
   * urgency-ordered screen with what needs nothing. « aujourd'hui » is a
   * date, so the derivation reads one: a correlated journey dispatched since
   * local midnight. */
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const dispatchedTodayTitles = new Set(
    (journeys.data?.journeys ?? [])
      .filter(
        (j) =>
          j.dispatched_at != null &&
          j.dispatched_at * 1000 >= startOfToday.getTime(),
      )
      .map((j) => j.follow_title)
      .filter((t): t is string => t != null && t !== ""),
  );
  const rangeAujourdhui: readonly FollowedSeriesItem[] =
    followed.data?.items.filter(
      (i) => i.status === "a_jour" && dispatchedTodayTitles.has(i.title),
    ) ?? [];

  // ── Section visibility ────────────────────────────────────────────────

  const sectionList = SECTION_SLUGS.map((slug) => {
    const count =
      slug === "a-recuperer"
        ? aRecuperer.length
        : slug === "a-traiter"
          ? aTraiter.length
          : slug === "en-vol"
            ? enVol.length + downloads.length
            : slug === "cherche-rien-trouve"
              ? chercheRienTrouve.length
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
        ? aTraiter.length > 0 ||
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
          className={`inline-block size-[9px] shrink-0 rounded-full border-[1.5px] ${m.pipClass}`}
        />
        <span className="text-sm font-medium">{m.label}</span>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {String(count)}
        </span>
      </h3>
    );
  }

  /** Render one followed-item card (used in three sections). */
  function renderFollowedCard(item: FollowedSeriesItem): ReactElement {
    const kind = asMediaKind(item.kind);
    const sheetHref = followMediaRef(item);
    return (
      /* A10/A11 — same gesture and kebab grammar as « Suivis », from the same
         builder (§13): three surfaces, one action source. */
      <SwipeActions key={item.id} right={actions.swipeFor(item)}>
        <AcquisitionCard
          title={item.title}
          posterUrl={item.poster_url ?? null}
          {...(item.year != null ? { subtitle: String(item.year) } : {})}
          meta={
            /* Same composition as the Suivis card — one card anatomy (§4). */
            <>
              {followFraction(item) != null && (
                <span className="rounded bg-muted px-1.5 py-px text-xs font-medium text-muted-foreground">
                  {followFraction(item)}
                </span>
              )}
              {followCountsCaption(item) != null && (
                <span className="text-xs text-muted-foreground">
                  {followCountsCaption(item)}
                </span>
              )}
            </>
          }
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
        // Blocked items have no resolved provider id — no poster link (§11).
        // No onOpen either — a button that does nothing is a dead control (§11).
        strip={<JourneyStrip stage={item.stage} blocked />}
        // « Résoudre → » lives in footer (full width, under the strip),
        // NOT in meta — nested interactive regions are invalid HTML,
        // so placing a Link inside the meta span would produce a button
        // inside another button at any width below md.
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
    const matchKey = journeyMatchKey(
      item.title,
      item.kind,
      item.season ?? null,
      item.episode ?? null,
    );
    const journey = journeyByKey.get(matchKey);
    const stage = deriveStage(journey);
    // The wanted row carries no provider ids, but its correlated journey does:
    // an identified in-flight media leads to its sheet like any other (§11).
    const sheetHref =
      journey != null
        ? followMediaRef({ media_ref: journey.media_ref, kind: item.kind })
        : null;

    return (
      <AcquisitionCard
        key={item.id}
        title={item.title}
        posterUrl={null}
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
        meta={
          journeys.isError ? null : (
            <span
              className="min-w-0 truncate font-mono text-[length:var(--text-2xs)] text-muted-foreground"
              title={journey?.release_name ?? undefined}
            >
              {journey?.release_name ?? "Nom de release non enregistré"}
            </span>
          )
        }
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
        strip={stage != null ? <JourneyStrip stage={stage} /> : undefined}
      />
    );
  }

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <>
      <div className="flex flex-col gap-4 px-3 py-3">
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
              {s.slug === "a-recuperer" && aRecuperer.map(renderFollowedCard)}

              {/* « À traiter » — cards + crossref for orphans */}
              {s.slug === "a-traiter" && (
                <>
                  {!toHandle.isError && aTraiter.map(renderATraiterCard)}
                  {/* Crossref — orphans with NO acquisition provenance (§3.1).
                       Renders whenever orphans exist, even alongside items —
                       §méthode: never under-count what needs attention. */}
                  {orphanCount > 0 && (
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
                  {/* Live progress of what is actually downloading, with its
                      percentage and, when a torrent breaks, the REASON in
                      French — a stalled download that only says « en cours »
                      is the silence §8 exists to end. */}
                  {downloads.length > 0 && (
                    <div className="mt-3 flex flex-col gap-4">
                      {downloads.map((d) => (
                        <DownloadRow key={d.info_hash || d.name} d={d} />
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* « Cherché, rien trouvé » */}
              {s.slug === "cherche-rien-trouve" &&
                chercheRienTrouve.map(renderFollowedCard)}

              {/* « Rangé aujourd'hui » */}
              {s.slug === "range-aujourdhui" &&
                rangeAujourdhui.map(renderFollowedCard)}
            </section>
          );
        })}

        {/* Loading — all sections empty, data hasn't landed yet.
            MUST NOT show « Rien à signaler » while a fetch is in flight. */}
        {allEmpty && anyLoading && !anyData && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Chargement…
          </p>
        )}

        {/* Empty state — all five sections are empty AND data has loaded
            AND no hook is in error (§ panne ≠ absence). */}
        {allEmpty && !anyLoading && !anyError && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Rien à signaler — tout est en ordre.
          </p>
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
