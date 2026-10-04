// The season matrix, and the legend that reads it.
//
// It lives with Acquisitions because that is what makes it change: a season, an
// episode, and what « owned » means for one. It is drawn inside the bottom
// panel, which is a `ui/` primitive — so rather than the panel knowing what a
// season is, this file DECLARES the block to the panel's contract and
// REGISTERS what draws it. The panel stays domain-free; the domain stays here.
//
// Markup is the legacy `saisonsHTML`'s, transplanted rather than translated:
// same tags, same classes, same `data-*`, so the document-level delegation
// (`.ep[data-ep]`) keeps working unchanged.
import { useTranslation } from "react-i18next";
import { Disclosure } from "../../ui/disclosure";
import { today } from "../../lib/clock";
import { useQueryClient } from "@tanstack/react-query";
import { useRights } from "../../lib/account";
import { seasonTakeOffered } from "../../lib/rights";
import { heldIdentity, providerAddress } from "../../lib/held-identity";
import { useServerStateVersion } from "../../lib/query-client";
import { offCatalogueBySeason, ownedSeason, useMediaSeasons, useMediaSheet, type MediaSeasons } from "./queries";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";
import { seasonGrabSpacing, seasonGrabTaken, episodeCell, episodeSet, seasonFraction, type EpisodeState } from "./variants";
import { actionButton, chip } from "../../ui/variants";
import { EpisodeLegend } from "./episode-legend";
import { askForSeason, useAskedInFlight } from "./season-grab";
import { episodeStateLabel } from "./format";
import { useQueuedSeasons } from "./queued-seasons";
import { useAskedSeasons } from "./asked-seasons";
import { SeasonRequested } from "./season-requested";
import { SeasonOffCatalogue } from "./season-off-catalogue";

// The slice of a "follow" record the season blocks read: `ids` for the medium's
// two served reads — the owned numbers and the episode catalogue — `title` for
// the cache to be asked when the record carries no `ids`, and `status` as the fallback
// state when a season has no per-episode ownership data.
export type Follow = {
  title: string;
  status?: string;
  ids?: Record<string, number | string> | null;
  /** Who asked for it (F27) — what decides whether its seasons are the account's to take. */
  requesters?: readonly { id: string }[];
};

/** A season of a series: its number, the episodes aired (null when unknown), the episodes owned. */
export type Season = [number, number | null, number];

// The kind this file adds to the panel's block map. Declared here, beside what
// draws it, so the two halves of the contract cannot drift apart.
declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    saisons: { follow: Follow; seasons: Season[] };
  }
}

type EpisodeCatalog = { number: number; airDate?: string | null }[];

/** What the medium's two served reads answered, as the season blocks read them. */
type Served = {
  owned: MediaSeasons["owned"] | undefined;
  episodes: Record<string, EpisodeCatalog> | undefined;
  /** How many held numbers each season's catalogue does not list, by season number (BK7). */
  offCatalogue: Record<string, number>;
};

// Presence is read from the LIST of owned numbers when the seasons read
// knows it, never from a `num <= owned` threshold that assumes the hole is
// at the end of the season — the same correction the media sheet applies.
function epState(
  served: Served,
  follow: Follow,
  seasonNum: number,
  number: number,
  owned: number,
): string {
  const held = ownedSeason(served.owned, seasonNum);
  if (held)
    return held.has(number)
      ? "in_library"
      : follow.status === "pending"
        ? "pending"
        : follow.status === "acquiring"
          ? "acquiring"
          : "to_grab";
  if (number <= owned) return "in_library";
  if (follow.status === "pending") return "pending";
  if (follow.status === "acquiring") return "acquiring";
  return "to_grab";
}

function catalogFor(served: Served, number: number): EpisodeCatalog | null {
  return served.episodes?.[String(number)] ?? null;
}

function SeasonDetails({
  follow,
  season,
  served,
  owns,
}: {
  follow: Follow;
  season: Season;
  served: Served;
  /** Whether the library holds the medium. */
  owns: boolean;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  // WHICH SEASONS ARE WAITING on the pipeline, read from the cache so the row
  // redraws the moment one is answered « queued ».
  const waiting = useQueuedSeasons(follow.title);
  const askedInFlight = useAskedInFlight();
  // WHETHER THE SEASON'S WHOLE RECOVERY IS LIVE, followed or not (Q5), and
  // whether the engine launched it (Q19) — undefined when nothing recovers it.
  const recovery = useAskedSeasons(follow.title).get(season[0]);
  const askedOnce = recovery !== undefined;
  // PILOTING, ON ONE'S OWN FOLLOW (§ 17) — absent otherwise, never refused.
  const takeOffered = seasonTakeOffered(follow.requesters === undefined ? undefined : follow, useRights());
  const [num, rawAired, owned] = season;
  const aired = rawAired ?? 0;
  const complete = owned >= aired;
  const missing = aired - owned;
  // An ANNOUNCED episode appears in the matrix but NEVER in the
  // denominator: it is not missing, it is not out yet. The provider
  // catalogue knows more than what has aired.
  const catalog = catalogFor(served, num);
  const total = Math.max(aired, catalog ? catalog.length : 0);
  const cells = Array.from({ length: total }, (_, index) => {
    const number = index + 1;
    const info = catalog?.find((entry) => entry.number === number) ?? null;
    const upcoming = Boolean(info?.airDate && info.airDate > today());
    const state = upcoming
      ? "announced"
      : epState(served, follow, num, number, owned);
    return (
      <button
        key={number}
        className={episodeCell({ state: state as EpisodeState })}
        data-part="episode"
        data-state={state}
        data-announced={state === "announced" || undefined}
        data-in-library={state === "in_library" || undefined}
        data-ep={`${follow.title}|${num}|${number}|${state}`}
        aria-label={`S${String(num).padStart(2, "0")}E${String(number).padStart(2, "0")} — ${episodeStateLabel(state)}`}
      >
        {String(number).padStart(2, "0")}
      </button>
    );
  });
  return (
    <Disclosure kind="season" data-part="season" open={!complete} summary={<>
        {/* The blanks between these children are NOT decoration: the legacy
            `saisonsHTML` carried a line break at each of them, and JSX drops
            the whitespace it finds between an expression and an element. Left
            out, `summary.textContent` reads « Saison 2211/11 » — the season
            number welded to its own counter, for anything that reads the row
            as one string (a rule deriving the number from it, an assistive
            technology announcing it). `summary` is a flex container, so a
            whitespace-only node draws nothing: the fix is invisible and the
            text is right again. */}
        {t("common.season")} {num}{" "}
        <span className={seasonFraction()}>
          {/* THE SHEET'S THREE CONVENTIONS, so the panel and the sheet say one
              thing about one season: nothing aired is « à venir », an unknown
              count is « ? », and a medium the library does not hold states
              what aired and no fraction — a fraction is an assertion about what
              one holds. */}
          {rawAired === 0
            ? t("screens.media.seasonUpcoming")
            : owns
              ? `${owned}/${rawAired ?? "?"}`
              : `${rawAired ?? "?"} ${t("screens.media.episodesShort")}`}
        </span>{" "}
        {/* DOIT-4's VISIBLE HALF, ON THE SURFACE THE ASK WAS MADE FROM. The
            button below is where the operator acts, so this is where he looks
            afterwards: the verb's message is gone in four seconds and the
            pastille is what he can come back to. Drawn on the sheet's own
            season list too, because the two are one fact about one season and a
            fact stated on only one of two surfaces is a fact the reader has to
            know where to look for. */}
        {waiting.includes(num) ? (
          <span className={chip({ tone: "info" })} data-part="season/queued" data-tone="info">
            {t("screens.media.seasonWaitingOnPipeline")}
          </span>
        ) : null}{" "}
        {/* « DEMANDÉE » WHILE THE SEASON'S RECOVERY LIVES, and the act below is
            withdrawn: the surface pressed says what the ask did. ONE MARK AT A
            TIME (DECIDED 4): « En file » while the ask waits, then « Demandée ». */}
        {askedOnce && !waiting.includes(num) ? (
          <SeasonRequested title={follow.title} season={num} automatic={recovery === true} />
        ) : null}{" "}
        {/* A shortfall is an episode that AIRED and is not held — never one
            of a medium nobody holds, nor of a count nobody knows. */}
        {complete || !owns || rawAired === null ? null : (
          <span className={chip({ tone: "warning" })} data-part="season/missing" data-tone="warning">
            {missing}{" "}
            {missing > 1 ? t("common.missingPlural") : t("common.missing")}
          </span>
        )}{" "}
        {/* WHAT IS HELD BEYOND THE CATALOGUE (§ 1.10, B-475 = B), under the
            row and outside its fraction — the sheet's row says it the same way. */}
        <SeasonOffCatalogue count={owns ? served.offCatalogue[String(num)] : 0} />
      </>}>
      <div className={episodeSet()} data-part="episode/set">
        {cells}
      </div>
      {/* THE VERB, DRAWN ONLY OVER A HOLE (B-301).

          IT IS A PANEL ACTION, drawn as the panel's own actions are:
          `actionButton({ kind: "panelAction" })`, which wears `sact` and carries
          the border, the ground and the colours. A first version wore the
          layout alone, with no colour at all, and the button drew as a pale
          label on a pale panel, which is how the operator saw it on the phone.
          The matrix showed « 1
          manquant » and offered nothing; DOIT-3 is « agir là où l'on observe ».
          A complete season carries no button, because a button that can only
          say « nothing to do » is worse than no button.

          `data-grab-season` is what the RULE anchors on (D4) and what says WHICH
          season the finger was on — a rule counting calls alone would take a
          call to the wrong one. The act itself is a React handler and NOT a
          delegation target: the engine died by subtraction (D5), and a verb
          that needed a line in it was a verb that had not moved. */}
      {complete || askedOnce || !takeOffered ? null : (
        <button
          type="button"
          className={`${actionButton({ kind: "panelAction" })} ${seasonGrabSpacing()} ${seasonGrabTaken()}`}
          data-part="season/grab"
          data-grab-season={`${follow.title}|${num}`}
          aria-busy={askedInFlight.has(`${follow.title}|${num}`) || undefined}
          onClick={() => {
            void askForSeason(client, follow.title, num);
          }}
        >
          {t("panels.follow.grabSeason", { season: num })}
        </button>
      )}
    </Disclosure>
  );
}

// The season matrix and the legend that reads it — ONE block, so a panel
// asking for seasons cannot get the matrix without the key to it. The
// legend lists only the states actually PRESENT, above the matrix.
function SeasonsBlock({
  block,
}: {
  block: { type: "saisons" } & PanelBlockMap["saisons"];
}) {
  const { follow } = block;
  // THE MEDIUM'S IDENTITY, from the record or from the cache — re-asked when any
  // read lands, because the list that holds a medium nobody follows can land
  // after the panel opened.
  useServerStateVersion();
  const address = providerAddress(follow.ids ?? heldIdentity(follow.title)?.ids);
  // THE READS ARE MOUNTED ONLY WITH AN ADDRESS (B-503). Asked with an empty
  // provider and id, they were disabled but still built: two cache entries
  // keyed on nothing, each observed while the panel was open.
  return address
    ? <SeasonsAt block={block} provider={address.provider} id={address.id} />
    : <SeasonsDrawn block={block} served={{ owned: undefined, episodes: undefined, offCatalogue: {} }} owns={false} />;
}

/** The season block once the medium's address is known: its two served reads. */
function SeasonsAt({
  block,
  provider,
  id,
}: {
  block: { type: "saisons" } & PanelBlockMap["saisons"];
  provider: string;
  id: string;
}) {
  const seasonsRead = useMediaSeasons(provider, id);
  const sheetRead = useMediaSheet(provider, id);
  // WHETHER WE HOLD IT, read where the sheet reads it — the sheet's own
  // `owned` — so the panel and the sheet state one fact about one season.
  const owns = (sheetRead.data as { owned?: boolean } | null | undefined)?.owned === true;
  const served: Served = {
    owned: seasonsRead.data?.owned,
    episodes: (sheetRead.data as { episodes?: Record<string, EpisodeCatalog> } | null | undefined)?.episodes,
    offCatalogue: offCatalogueBySeason(seasonsRead.data),
  };
  return <SeasonsDrawn block={block} served={served} owns={owns} />;
}

/** The legend and the season rows, from what the served reads answered. */
function SeasonsDrawn({
  block,
  served,
  owns,
}: {
  block: { type: "saisons" } & PanelBlockMap["saisons"];
  served: Served;
  owns: boolean;
}) {
  const { follow, seasons } = block;
  const hasUpcoming = seasons.some((season) =>
    (catalogFor(served, season[0]) ?? []).some(
      (episode) => episode.airDate && episode.airDate > today(),
    ),
  );
  const statesPresent = new Set<string>([
    ...(hasUpcoming ? ["announced"] : []),
    ...seasons.flatMap((season) => [
      ...(season[2] > 0 ? ["in_library"] : []),
      ...((season[1] ?? 0) > season[2]
        ? [epState(served, follow, season[0], season[1] ?? 0, season[2])]
        : []),
    ]),
  ]);
  return (
    <>
      <EpisodeLegend present={statesPresent} />
      {seasons.map((season) => (
        <SeasonDetails
          key={season[0]}
          follow={follow}
          season={season}
          served={served}
          owns={owns}
        />
      ))}
    </>
  );
}

// Declared to the registry as this module evaluates. The shell imports this
// file at boot, before any panel can open.
registerBlock("saisons", (block) => <SeasonsBlock block={block} />);
