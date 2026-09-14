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
import { useMediaReference, type MediaReference } from "./reference";
import { useQueryClient } from "@tanstack/react-query";
import { heldIdentity, providerAddress } from "../../lib/held-identity";
import { useServerStateVersion } from "../../lib/query-client";
import { ownedSeason, useMediaSeasons, useMediaSheet, type MediaSeasons } from "./queries";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";
import { queuedMark, seasonGrabSpacing, seasonGrabTaken, episodeCell, episodeSet, legend, legendSwatch, seasonDisclosure, seasonFraction, seasonShortfall, type EpisodeState } from "./variants";
import { actionButton } from "../../ui/variants";
import { askForSeason, useAskedInFlight } from "./season-grab";
import { useQueuedSeasons } from "./queued-seasons";

// The slice of a "follow" record the season blocks read: `ids` for the medium's
// two served reads — the owned numbers and the episode catalogue — `t` for the
// cache to be asked when the record carries no `ids`, and `st` as the fallback
// state when a season has no per-episode ownership data.
export type Follow = { t: string; st?: string; ids?: Record<string, number | string> | null };

/** A season of a series: its number, the episodes aired (null when unknown), the episodes owned. */
export type Season = [number, number | null, number];

// The kind this file adds to the panel's block map. Declared here, beside what
// draws it, so the two halves of the contract cannot drift apart.
declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    saisons: { follow: Follow; seasons: Season[] };
  }
}

// Lifecycle order for the season legend — refonte.html@60530dbd8 kept `EP_ORDER`
// private (only `EP_LABEL` is published on the référentiel). It is small,
// static and keyed on the same six states `EP_LABEL` carries, so it is
// reproduced here verbatim; each state's swatch is `legendSwatch`'s variant.
const EP_ORDER = [
  "unverified",
  "announced",
  "pending",
  "to_grab",
  "acquiring",
  "in_library",
] as const;

type EpisodeCatalog = { n: number; air?: string | null }[];

/** What the medium's two served reads answered, as the season blocks read them. */
type Served = {
  owned: MediaSeasons["owned"] | undefined;
  episodes: Record<string, EpisodeCatalog> | undefined;
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
      : follow.st === "pending"
        ? "pending"
        : follow.st === "acquiring"
          ? "acquiring"
          : "to_grab";
  if (number <= owned) return "in_library";
  if (follow.st === "pending") return "pending";
  if (follow.st === "acquiring") return "acquiring";
  return "to_grab";
}

function catalogFor(served: Served, number: number): EpisodeCatalog | null {
  return served.episodes?.[String(number)] ?? null;
}

function SeasonDetails({
  follow,
  season,
  reference,
  served,
  owns,
}: {
  follow: Follow;
  season: Season;
  reference: MediaReference;
  served: Served;
  /** Whether the library holds the medium. */
  owns: boolean;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  // WHICH SEASONS ARE WAITING on the pipeline, read from the cache so the row
  // redraws the moment one is answered « queued ».
  const waiting = useQueuedSeasons(follow.t);
  const askedInFlight = useAskedInFlight();
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
    const info = catalog?.find((entry) => entry.n === number) ?? null;
    const upcoming = Boolean(info?.air && info.air > reference.TODAY);
    const state = upcoming
      ? "announced"
      : epState(served, follow, num, number, owned);
    return (
      <button
        key={number}
        className={episodeCell({ state: state as EpisodeState })}
        data-part="episode"
        data-announced={state === "announced" || undefined}
        data-in-library={state === "in_library" || undefined}
        data-ep={`${follow.t}|${num}|${number}|${state}`}
        aria-label={`S${String(num).padStart(2, "0")}E${String(number).padStart(2, "0")} — ${reference.EP_LABEL[state]}`}
      >
        {String(number).padStart(2, "0")}
      </button>
    );
  });
  return (
    <details className={seasonDisclosure()} data-part="season" open={!complete}>
      <summary>
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
          <span className={queuedMark()} data-part="season/queued">
            {t("screens.media.seasonWaitingOnPipeline")}
          </span>
        ) : null}{" "}
        {/* A shortfall is an episode that AIRED and is not held — never one
            of a medium nobody holds, nor of a count nobody knows. */}
        {complete || !owns || rawAired === null ? null : (
          <span className={seasonShortfall()} data-part="season/missing">
            {missing}{" "}
            {missing > 1 ? t("common.missingPlural") : t("common.missing")}
          </span>
        )}
      </summary>
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
          delegation target: the engine dies by subtraction (D5), and a verb
          that needed a line in `legacy.js` would be a verb that has not moved. */}
      {complete ? null : (
        <button
          type="button"
          className={`${actionButton({ kind: "panelAction" })} ${seasonGrabSpacing()} ${seasonGrabTaken()}`}
          data-part="season/grab"
          data-grab-season={`${follow.t}|${num}`}
          aria-busy={askedInFlight.has(`${follow.t}|${num}`) || undefined}
          onClick={() => {
            void askForSeason(client, follow.t, num);
          }}
        >
          {t("panels.follow.grabSeason", { season: num })}
        </button>
      )}
    </details>
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
  const reference = useMediaReference();
  const { follow, seasons } = block;
  // THE MEDIUM'S IDENTITY, from the record or from the cache — re-asked when any
  // read lands, because the list that holds a medium nobody follows can land
  // after the panel opened.
  useServerStateVersion();
  const address = providerAddress(follow.ids ?? heldIdentity(follow.t)?.ids);
  const seasonsRead = useMediaSeasons(address?.provider ?? "", address?.id ?? "");
  const sheetRead = useMediaSheet(address?.provider ?? "", address?.id ?? "");
  // WHETHER WE HOLD IT, read where the sheet reads it — the sheet's own
  // `possede` — so the panel and the sheet state one fact about one season.
  const owns = (sheetRead.data as { possede?: boolean } | null | undefined)?.possede === true;
  const served: Served = {
    owned: seasonsRead.data?.owned,
    episodes: (sheetRead.data as { eps?: Record<string, EpisodeCatalog> } | null | undefined)?.eps,
  };
  const hasUpcoming = seasons.some((season) =>
    (catalogFor(served, season[0]) ?? []).some(
      (episode) => episode.air && episode.air > reference.TODAY,
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
      <div className={legend()} data-part="legend">
        {EP_ORDER.filter((state) => statesPresent.has(state)).map((state) => (
          <span key={state}>
            <i className={legendSwatch({ state })} />
            {reference.EP_LABEL[state]}
          </span>
        ))}
      </div>
      {seasons.map((season) => (
        <SeasonDetails
          key={season[0]}
          follow={follow}
          season={season}
          reference={reference}
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
