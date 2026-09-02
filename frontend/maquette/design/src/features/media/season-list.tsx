// The season list of a media sheet: one collapsible row per season, folded
// from the owned numbers or from the catalogue, with the episode matrix
// underneath when the numbers are known.
import { useTranslation } from "react-i18next";
import { useMediaReference } from "./reference";
import { SkeletonLine } from "../../ui/state-surfaces";
import { factsPanel } from "../../ui/variants";
import type { CatalogSeason, MediaSheetFields, SeasonRow } from "./sheet-fields";

export function SeasonList({
  sheet,
  sheetInFlight,
  seasons,
  owns,
  catalog,
  title,
}: {
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
}) {
  const {
    ownedFor,
    plages,
    dateFR,
    EP_LABEL,
    TODAY,
  } = useMediaReference();
  const { t } = useTranslation();
  const eps = sheet?.eps ?? {};
  const rows: SeasonRow[] = owns
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
        const held = owns ? ownedFor(title, row.n) : null;
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
        ) : sheetInFlight ? (
          <p className="noinfo" style={{ marginTop: "8px" }}>
            <SkeletonLine width="half" />
          </p>
        ) : row.aired === 0 || row.aired === null ? (
          <p className="noinfo" data-part="no-info" style={{ marginTop: "8px" }}>
            {t("screens.media.seasonAnnounced")}
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
            open={!(complete || !owns)}
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
                {row.aired === 0
                  ? t("screens.media.seasonUpcoming")
                  : owns
                    ? `${nbOwn}/${row.aired ?? "?"}`
                    : `${row.aired ?? "?"} ${t("screens.media.episodesShort")}`}
              </span>{" "}
              {owns && missing != null && missing > 0 ? (
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
                  className="miss" data-part="season/missing"
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
              <p className="missing">
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
          </details>
        );
      })}
    </div>
  );
}
