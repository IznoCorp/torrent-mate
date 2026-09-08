// The season list of a media sheet: one collapsible row per season, folded
// from the owned numbers or from the catalogue, with the episode matrix
// underneath when the numbers are known.
import { useTranslation } from "react-i18next";
import { useMediaReference } from "./reference";
import { SkeletonLine } from "../../ui/state-surfaces";
import { factsPanel } from "../../ui/variants";
import { queuedMark, seasonGrabSpacing } from "./variants";
import { useQueuedSeasons } from "./queued-seasons";
import { askForSeason } from "./season-grab";
import { useQueryClient } from "@tanstack/react-query";
import type { CatalogSeason, MediaSheetFields, SeasonRow } from "./sheet-fields";

export function SeasonList({
  followed,
  sheet,
  sheetInFlight,
  failed,
  ownershipKnown,
  seasons,
  owns,
  catalog,
  title,
}: {
  /** Whether the medium is followed — the grab's own precondition. */
  followed: boolean;
  sheet: MediaSheetFields | null;
  seasons: [number, number | null, number][];
  owns: boolean;
  catalog: CatalogSeason[];
  title: string;
  /**
   * Whether the SHEET's read is still out. The rows come from the seasons read
   * and the episode lists from the sheet, which are two queries: with the
   * seasons landed and the sheet not, « Épisodes non détaillés pour cette
   * saison » is said about a list still on its way.
   */
  sheetInFlight: boolean;
  /**
   * Whether ownership has arrived. Every row's arithmetic is ownership: the
   * fraction, the « n manquants » and whether the row opens all read what the
   * reader HOLDS, and with `possede` still out they read a medium nobody owns
   * as one owned with nothing in it — « 0/13 · 13 manquants », in an open row,
   * about a suggestion.
   */
  /** Whether the sheet's read FAILED — an unknown is then unread, not unanswered. */
  failed: boolean;
  ownershipKnown: boolean;
}) {
  const {
    ownedFor,
    plages,
    dateFR,
    EP_LABEL,
    TODAY,
  } = useMediaReference();
  const { t } = useTranslation();
  // WHICH SEASONS ARE WAITING, read from the cache like every other fact on
  // this sheet, so the row redraws when one arrives.
  const waiting = useQueuedSeasons(title);
  // The cache the shared ask re-reads and redraws from. Taken here
  // rather than threaded through props: this component is rendered, so
  // it has a hook to read it from, which the panel's producer does not.
  const client = useQueryClient();
  const eps = sheet?.eps ?? {};
  // WHICH ROWS EXIST is the SEASONS read's answer; how full each one is, is the
  // sheet's. With ownership still out the rows are drawn from what has landed —
  // hiding them would wait for one answer by withholding another the reader
  // already has.
  const rows: SeasonRow[] = owns || !ownershipKnown
    ? seasons.map(([number, aired, own]) => ({ n: number, aired, own }))
    : catalog.map((season) => ({
        n: season.n,
        aired: season.ep,
        own: 0,
        air: season.air,
      }));
  if (!rows.length) return null;
  return (
    <div style={{ marginTop: "10px" }}>
      {rows.map((row) => {
        const list = eps[String(row.n)] ?? null;
        // THE OWNED NUMBERS ARE AN ANSWER ABOUT OWNERSHIP, so they wait for
        // ownership to be known — and reading them one line lower than the
        // three lines that already waited is what left « Manquants : 1–16 »
        // and sixteen `to_grab` cells one tap under « Saison 8 inconnu ».
        // Everything below derives from `held`: the count, the missing list and
        // the matrix all empty themselves through this one term, and the body
        // falls back to « Épisodes non détaillés pour cette saison », which
        // asserts nothing.
        const held = ownershipKnown && owns ? ownedFor(title, row.n) : null;
        /* The count is DERIVED from the owned numbers when they are known;
           a total that does not say where the holes are is no longer
           trusted. */
        const nbOwn = held
          ? [...held].filter((element) => !row.aired || element <= row.aired)
              .length
          : row.own;
        const complete = owns && row.aired != null && nbOwn >= row.aired;
        const missing = row.aired != null ? row.aired - nbOwn : null;
        /* With no known total, reason up to the highest owned episode: a
           hole BELOW that maximum is a genuine gap, above it nothing is
           known. */
        const bound =
          row.aired === 0
            ? 0
            : held && held.size
              ? (row.aired ?? Math.max(...held))
              : row.aired || 0;
        const missingNums =
          owns && held && row.aired
            ? Array.from(
                { length: row.aired },
                (ignored, index) => index + 1,
              ).filter((from) => !held.has(from))
            : [];
        const body = list ? (
          <div className={factsPanel()} data-part="panel" style={{ marginTop: "8px" }}>
            {list.map((episode) => {
              /* SUBTLE state colour: a 6px dot and the number in the
                 tone. The title stays neutral — it is what one reads
                 first, so it keeps maximum contrast. One colour signal
                 per row, not a Christmas tree. */
              const upcoming = episode.air && episode.air > TODAY;
              /* State comes from the LIST of owned numbers. A « number <=
                 owned count » threshold assumes the hole is always at the
                 end of the season: false for 35 series in this library. */
              const episodeState = upcoming
                ? "announced"
                : !owns || !held
                  ? "unverified"
                  : held.has(episode.n)
                    ? "in_library"
                    : "to_grab";
              return (
                // Same blanks as the season summary, same reason: the row is
                // a flex container (they draw nothing) and its `textContent`
                // is read as one sentence.
                <div
                  className={`eprow ${episodeState}`}
                  data-part="episode/row"
                  data-announced={episodeState === "announced" || undefined}
                  data-in-library={episodeState === "in_library" || undefined}
                  key={episode.n}
                >
                  <span className="epdot"></span>{" "}
                  <span className="en" data-part="episode/number">
                    E{String(episode.n).padStart(2, "0")}
                  </span>{" "}
                  <span className="et">{episode.t}</span>{" "}
                  <span className="ed">
                    {episode.air
                      ? dateFR(episode.air)
                      : t("screens.media.dateUnknown")}
                    {episodeState === "in_library"
                      ? ""
                      : ` · ${EP_LABEL[episodeState].toLowerCase()}`}
                  </span>
                </div>
              );
            })}
          </div>
        ) : bound && held ? (
          /* No episode titles, but the numbers are known: the matrix still
             answers « which ones are missing ». When the aired total is
             unknown, go no further than the highest owned episode — beyond
             it nothing is known, and it says so. */
          <>
            <div
              className="eps"
              data-part="episode/set"
              style={{ marginTop: "8px" }}
            >
              {Array.from({ length: bound }, (ignored, index) => {
                const number = index + 1;
                const episodeState = held.has(number)
                  ? "in_library"
                  : "to_grab";
                return (
                  <span
                    className={`ep ${episodeState}`}
                    data-part="episode"
                    data-in-library={episodeState === "in_library" || undefined}
                    key={number}
                    aria-label={t("screens.media.episodeAria", {
                      n: number,
                      // french-ok: the INTERPOLATION placeholder, named by
                      // `episodeAria` in fr.json — renaming this half alone
                      // leaves « Épisode 3 — {{etat}} » in the aria-label.
                      etat: EP_LABEL[episodeState],
                    })}
                  >
                    {String(number).padStart(2, "0")}
                  </span>
                );
              })}
            </div>
            {row.aired == null ? (
              <p className="noinfo" data-part="no-info" style={{ marginTop: "6px" }}>
                {t("screens.media.beyondEpisode", { n: bound })}
              </p>
            ) : (
              ""
            )}
          </>
        ) : row.aired === 0 || row.aired === null ? (
          // A SEASON WITH NOTHING AIRED IS THE SEASONS READ'S OWN ANSWER, and
          // that read has landed: a skeleton over it would be waiting for a
          // thing already known — the same defect with its sign turned round.
          // It precedes the sheet's flight deliberately.
          <p className="noinfo" data-part="no-info" style={{ marginTop: "8px" }}>
            {t("screens.media.seasonAnnounced")}
          </p>
        ) : sheetInFlight ? (
          <p className="noinfo" style={{ marginTop: "8px" }}>
            <SkeletonLine width="half" />
          </p>
        ) : (
          <p className="noinfo" data-part="no-info" style={{ marginTop: "8px" }}>
            {t("screens.media.episodesNotDetailed")}
          </p>
        );
        return (
          <details
            className="season"
            data-part="season"
            key={row.n}
            open={ownershipKnown && !(complete || !owns)}
          >
            <summary>
              {/* The blanks between these children are NOT decoration: the
                  legacy template carried a line break at each of them, and a
                  reader of `summary.textContent` — the rule that derives the
                  season number from it, an assistive technology reading the
                  row — would otherwise see « Saison 33/13 ». `summary` is a
                  flex container, so a whitespace-only node draws nothing. */}
              {t("common.season")} {row.n}{" "}
              <span className="sfr">
                {/* THE FRACTION IS OWNERSHIP, and a fraction is an assertion:
                    « 0/13 » about a medium whose `possede` has not arrived says
                    the reader holds none of it. The season's own total is the
                    seasons read's and is drawn either way. */}
                {row.aired === 0
                  ? t("screens.media.seasonUpcoming")
                  : !ownershipKnown
                    ? (sheetInFlight
                        ? <SkeletonLine width="short" />
                        : t(failed ? "screens.media.unread" : "screens.media.unknown"))
                    : owns
                      ? `${nbOwn}/${row.aired ?? "?"}`
                      : `${row.aired ?? "?"} ${t("screens.media.episodesShort")}`}
              </span>{" "}
              {/* DOIT-4's VISIBLE HALF, and it is the only thing this lot
                  draws. An ask that arrived while the pipeline was running is
                  queued — never refused — and the clause's word is VISIBLY.
                  The verb already says it in a message; a message is gone in
                  four seconds, and after it goes nothing distinguishes a season
                  whose ask is waiting from one nobody asked for. The pastille
                  is what the operator can come back to.

                  IT SITS BEFORE THE SHORTFALL, because it is the newer fact and
                  the one that explains why the shortfall has not moved. */}
              {waiting.includes(row.n) ? (
                <span className={queuedMark()} data-part="season/queued">
                  {t("screens.media.seasonWaitingOnPipeline")}
                </span>
              ) : (
                ""
              )}{" "}
              {ownershipKnown && owns && missing != null && missing > 0 ? (
                <span className="miss" data-part="season/missing">
                  {missing}{" "}
                  {missing > 1
                    ? t("common.missingPlural")
                    : t("common.missing")}
                </span>
              ) : (
                ""
              )}{" "}
              {!owns && row.air ? (
                <span
                  // ITS OWN NAME. It wore `season/missing` — the name of the
                  // chip that counts what a reader is short of — and a date is
                  // not a shortfall: a rule counting « missing chips » read
                  // seven of them on a sheet missing nothing.
                  className="miss" data-part="season/aired-on"
                  style={{
                    background: "transparent",
                    color: "var(--color-muted-foreground)",
                    fontWeight: 400,
                  }}
                >
                  {dateFR(row.air)}
                </span>
              ) : (
                ""
              )}
            </summary>
            {missingNums.length ? (
              <p className="missing" data-part="season/missing-list">
                {t("screens.media.missingList", {
                  // french-ok: the INTERPOLATION placeholder, named by
                  // `missingList` in fr.json — renaming this half alone
                  // leaves « Manquants : {{liste}} » on screen.
                  liste: plages(missingNums),
                })}
              </p>
            ) : (
              ""
            )}
            {body}
            {/* THE SAME ACTION THE FOLLOW PANEL OFFERS, on the surface that
                draws the same hole. The queued pastille was deliberately put on
                BOTH season surfaces; an offer drawn on only one of them makes
                the other a place where the operator can see what is missing and
                do nothing about it, which is DOIT-3 read backwards.

                GATED ON `followed`, and that is the honest half of the answer
                to « why do the two differ ». The operation is
                `/api/acquisition/follows/{title}/seasons/{n}/grab`: it asks
                about a FOLLOW. The panel is only ever drawn for one, so it
                needs no test; this list is drawn for any medium, and offering
                the act on a medium nobody follows would draw a button whose
                own address does not exist. The behaviour itself is shared —
                `askForSeason` — so the two surfaces cannot drift apart. */}
            {followed && !complete ? (
              <button
                type="button"
                className={`sact ${seasonGrabSpacing()}`}
                data-part="season/grab"
                data-grab-season={`${title}|${row.n}`}
                onClick={() => {
                  void askForSeason(client, title, row.n);
                }}
              >
                {t("panels.follow.grabSeason", { season: row.n })}
              </button>
            ) : null}
          </details>
        );
      })}
    </div>
  );
}
