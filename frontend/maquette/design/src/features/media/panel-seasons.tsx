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
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";

// The slice of a "follow" record the season blocks read: `t` for lookups
// against the référentiel (`sheetFor`/`ownedFor`), `st` as the fallback state
// when a season has no per-episode ownership data. Only these two fields are
// ever read, whatever else the caller's object carries.
export type Follow = { t: string; st?: string };

export type Season = ReturnType<MediaReference["seasonsOf"]>[number];

// The kind this file adds to the panel's block map. Declared here, beside what
// draws it, so the two halves of the contract cannot drift apart.
declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    saisons: { isFollowed: Follow; seasons: Season[] };
  }
}

// Lifecycle order and swatch classes for the season legend — refonte.html
// keeps `EP_ORDER`/`EP_SWATCH` private (only `EP_LABEL` is published on the
// référentiel). Both are small, static, keyed on the same six states
// `EP_LABEL` already carries, so they are reproduced here verbatim rather
// than re-derived.
const EP_ORDER = [
  "unverified",
  "announced",
  "pending",
  "to_grab",
  "acquiring",
  "in_library",
] as const;

const EP_SWATCH: Record<string, string> = {
  unverified: "sw-muted",
  announced: "sw-upcoming",
  pending: "sw-waiting",
  to_grab: "sw-warning",
  acquiring: "sw-info",
  in_library: "sw-success",
};

type EpisodeCatalog = { n: number; air?: string | null }[];

// Presence is read from the LIST of owned numbers when the référentiel
// knows it, never from a `num <= owned` threshold that assumes the hole is
// at the end of the season — the same correction `epState` applies on the
// media sheet.
function epState(
  reference: MediaReference,
  follow: Follow,
  seasonNum: number,
  number: number,
  owned: number,
): string {
  const held = reference.ownedFor(follow.t, seasonNum);
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

function catalogFor(
  reference: MediaReference,
  follow: Follow,
  number: number,
): EpisodeCatalog | null {
  const sheet = reference.sheetFor(follow.t) as { eps?: unknown } | null;
  const eps = sheet?.eps as Record<string, EpisodeCatalog> | undefined;
  return eps?.[String(number)] ?? null;
}

function SeasonDetails({
  follow,
  season,
  reference,
}: {
  follow: Follow;
  season: Season;
  reference: MediaReference;
}) {
  const { t } = useTranslation();
  const [num, rawAired, owned] = season;
  const aired = rawAired ?? 0;
  const complete = owned >= aired;
  const missing = aired - owned;
  // An ANNOUNCED episode appears in the matrix but NEVER in the
  // denominator: it is not missing, it is not out yet. The provider
  // catalogue knows more than what has aired.
  const catalog = catalogFor(reference, follow, num);
  const total = Math.max(aired, catalog ? catalog.length : 0);
  const cells = Array.from({ length: total }, (_, index) => {
    const number = index + 1;
    const info = catalog?.find((entry) => entry.n === number) ?? null;
    const upcoming = Boolean(info?.air && info.air > reference.TODAY);
    const state = upcoming
      ? "announced"
      : epState(reference, follow, num, number, owned);
    return (
      <button
        key={number}
        className={`ep ${state}`}
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
    <details className="season" data-part="season" open={!complete}>
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
        <span className="sfr">
          {owned}/{aired}
        </span>{" "}
        {complete ? null : (
          <span className="miss" data-part="season/missing">
            {missing}{" "}
            {missing > 1 ? t("common.missingPlural") : t("common.missing")}
          </span>
        )}
      </summary>
      <div className="eps" data-part="episode/set">
        {cells}
      </div>
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
  const { isFollowed: follow, seasons: seasons } = block;
  const hasUpcoming = seasons.some((season) =>
    (catalogFor(reference, follow, season[0]) ?? []).some(
      (episode) => episode.air && episode.air > reference.TODAY,
    ),
  );
  const statesPresent = new Set<string>([
    ...(hasUpcoming ? ["announced"] : []),
    ...seasons.flatMap((season) => [
      ...(season[2] > 0 ? ["in_library"] : []),
      ...((season[1] ?? 0) > season[2]
        ? [epState(reference, follow, season[0], season[1] ?? 0, season[2])]
        : []),
    ]),
  ]);
  return (
    <>
      <div className="legend" data-part="legend">
        {EP_ORDER.filter((state) => statesPresent.has(state)).map((state) => (
          <span key={state}>
            <i className={EP_SWATCH[state]} />
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
        />
      ))}
    </>
  );
}

// Declared to the registry as this module evaluates. The shell imports this
// file at boot, before any panel can open.
registerBlock("saisons", (block) => <SeasonsBlock block={block} />);
