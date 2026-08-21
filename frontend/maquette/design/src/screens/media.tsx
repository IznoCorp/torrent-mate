// design/src/screens/media.tsx
// The centre of the product: legacy `openFiche(title)` (`refonte.html`) — ONE
// media sheet for every medium — reborn as a real route (`/mediasheet/$title`) and
// a final component. Markup is TRANSPLANTED, not translated: every tag, class
// and data-attribute below is the one `refonte.html`'s BLOCK 2 CSS already
// targets (`.screen`, `.screenbar`, `.herowrap`, `.trailer`, `.cast`,
// `.eprow`, `.sheetacts`…), so the same stylesheet applies unchanged and the
// rule harness measures the same geometry it measured on the legacy screen.
//
// Fixed order, and the order is the promise: hero → trailer → synopsis →
// cast → library state (+ seasons) → identifiers → actions. The only
// variations are the ones nature imposes — a director and a runtime for a
// film, a creator, a status and a catalogue for a series. What is missing is
// written « inconnu », never hidden.
//
// React escapes text natively, so there is no `escapeHtml` here: every string
// below is a JSX child or an attribute value, which is already safe.
//
// The ACTION buttons carry `data-toast` / `data-del` / `data-follow` +
// `data-fkind` and NO `onClick`: the document-level click delegation the
// legacy engine still runs is the seam this screen leans on, exactly as the
// panel does. The trailer is a plain `<a>` WITHOUT `data-navgo` — that same
// delegation must not preventDefault an external link.
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import {
  useStoreContent,
  useWorld,
  useReference,
  type MediaSheet,
  type Reference,
} from "../data";

// The exact shape `svgIcon(paths, strokeWidth)` produced as an HTML string —
// rebuilt as a real element so it composes with JSX. Same helper as
// `profile.tsx`'s, `add.tsx`'s and `panel.tsx`'s, still not shared: the
// extraction those files' comments call for is a follow-up of its own, not a
// silent scope add here.
function Icon({ paths, strokeWidth }: { paths: string; strokeWidth?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth || 2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: paths }}
    />
  );
}

// The fields this screen reads off a `SHEETS_RAW` entry. The source stays
// untyped JS and a movie and a show do not carry the same keys, so every
// field is optional — a narrowed view of `MediaSheet`, never a claim about
// what a sheet always has.
type SheetEpisode = { n: number; t: string; air?: string | null };
type CatalogSeason = { n: number; ep: number | null; air?: string };
type MediaSheetFields = {
  k?: string;
  y?: string;
  note?: number;
  g?: string;
  duree?: number | null;
  ov?: string;
  real?: string | null;
  crea?: string | null;
  cast?: { n: string; r?: string }[];
  ids?: Record<string, string | number>;
  status?: string;
  seasons?: CatalogSeason[];
  eps?: Record<string, SheetEpisode[]>;
  possede?: boolean;
};

// The slice of the simulated world this screen reads: the follow list, and
// only its titles.
type Follow = { t: string };

// One row of the season list: an owned-seasons row (`[n, aired, own]` from
// `seasonsOf`) and a catalogue row (`{ n, ep, air }` from the sheet) are
// folded into the same shape before rendering, exactly as `sheetSeasonsHTML`
// folds them.
type SeasonRow = {
  n: number;
  aired: number | null;
  own: number;
  air?: string;
};

function SeasonList({
  sheet,
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
}) {
  const { ownedFor, plages, dateFR, EP_LABEL, TODAY } = useReference();
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
          <div className="panel" style={{ marginTop: "8px" }}>
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
                  key={episode.n}
                >
                  <span className="epdot"></span>{" "}
                  <span className="en">
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
              <p className="noinfo" style={{ marginTop: "6px" }}>
                {t("screens.media.beyondEpisode", { n: bound })}
              </p>
            ) : (
              ""
            )}
          </>
        ) : row.aired === 0 || row.aired === null ? (
          <p className="noinfo" style={{ marginTop: "8px" }}>
            {t("screens.media.seasonAnnounced")}
          </p>
        ) : (
          <p className="noinfo" style={{ marginTop: "8px" }}>
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
                <span className="miss">
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
                  className="miss"
                  style={{
                    background: "transparent",
                    color: "var(--muted-foreground)",
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

// The banner prefers the wide visual; the vertical poster is only a fallback,
// and nothing at all when there is neither — same resolution order as the
// legacy sheet, base title included.
function artworkFor(reference: Reference, title: string): string | null {
  const { HERO_IMAGES, POSTERS, baseTitle } = reference;
  return (
    HERO_IMAGES[title] ??
    HERO_IMAGES[baseTitle(title)] ??
    POSTERS[title] ??
    POSTERS[baseTitle(title)] ??
    null
  );
}

export function MediaScreen() {
  const { title: raw } = useParams({ from: "/mediasheet/$title" });
  // Defensive: `__screens.mediaSheet` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const title = raw.normalize("NFC");
  // `world.follows` is MUTATED IN PLACE by the still-legacy follow act
  // (`actionFollow`, refonte.html) — the reference never changes, so
  // `useWorld()` alone would not notice. Subscribing to `version` forces the
  // re-render on that bump, and the read below then sees the mutated list
  // fresh: this is what flips the « Suivre » button to « Suivi » without the
  // legacy sheet reopening itself.
  useStoreContent((c) => c.version);
  const world = useWorld() as { follows?: Follow[] } | null;
  const follows = world?.follows ?? [];
  const reference = useReference();
  const { t } = useTranslation();
  const {
    icons,
    baseTitle,
    sheetFor,
    seasonsOf,
    CAST,
    trailerIds,
    initials,
  } = reference;

  const sheet = sheetFor(title) as (MediaSheet & MediaSheetFields) | null;
  const isFilm = sheet ? sheet.k === "movie" : false;
  /* Seasons are DERIVED from the provider catalogue crossed with the numbers
     actually owned. A hand-written table gave seasons to 10 series only, and
     none of them to the INCOMPLETE ones — the very media the question is
     about. */
  const sorted = seasonsOf(title)
    .slice()
    .sort((slice, index) => index[0] - slice[0]);
  const own = sorted.reduce(
    (accumulator, element) => accumulator + element[2],
    0,
  );
  const aired = sorted.reduce(
    (accumulator, element) => accumulator + (element[1] ?? 0),
    0,
  );
  const pct = aired ? Math.round((own / aired) * 100) : null;
  // A suggestion is NOT in the library: the sheet must say so and offer to
  // add it, not to delete it. Same template, with the only variation reality
  // imposes.
  const owns = sheet?.possede !== false;
  // The FIRST of the two follow tests, and it is deliberately the LOOSE one:
  // it matches on the base title, so « Silo » follows « Silo (2023) ». The
  // « Informations » block below asks the SAME question with a STRICTER test
  // — the asymmetry is the legacy sheet's, transplanted rather than
  // reconciled here.
  const followed = follows.some(
    (follow) => baseTitle(follow.t) === baseTitle(title),
  );
  const catalog = (sheet?.seasons ?? [])
    .slice()
    .sort((slice, index) => index.n - slice.n);
  // `?? 0` where the legacy addition simply let `null` coerce to zero: same
  // total, spelled so the type says what the arithmetic already did.
  const catalogEp = catalog.reduce(
    (accumulator, element) => accumulator + (element.ep ?? 0),
    0,
  );
  const prov = sheet?.ids ?? {};
  const url = prov.tvdb
    ? `/media/tvdb/${prov.tvdb}`
    : prov.tmdb
      ? `/media/tmdb/${prov.tmdb}`
      : null;
  const artwork = artworkFor(reference, title);
  // The link exists or it does not; where one arrives from changes nothing.
  const trailer = trailerIds[title] ?? trailerIds[baseTitle(title)] ?? null;

  return (
    <section className="screen open" data-part="screen" data-open="" data-key={`mediaSheet:${title}`}>
      <div className="screenbar">
        <button className="fback" onClick={() => window.__bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.media.back")}
        </button>{" "}
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--muted-foreground)",
          }}
        >
          {url ?? t("screens.media.unidentified")}
        </span>
      </div>
      <div className="port">
        <div className="body" data-region="screen-media/body">
          <div
            className={`herowrap${artwork ? "" : " noposter"}`}
            data-no-poster={!artwork || undefined}
          >
            <div
              className="herobg"
              aria-hidden="true"
              style={
                artwork ? { backgroundImage: `url('${artwork}')` } : undefined
              }
            ></div>
            <div className="hero">
              <h2 className="ht">{title.split(" (")[0]}</h2>
              <p className="hm">
                {sheet
                  ? `${sheet.y || t("screens.media.yearUnknown")} · ${isFilm ? t("common.film") : t("common.series")}${sheet.duree ? ` · ${sheet.duree} ${t("screens.media.minutesShort")}` : ""}`
                  : t("screens.media.metadataUnknown")}{" "}
                {sheet?.g ? (
                  <>
                    <br />
                    {sheet.g}
                  </>
                ) : (
                  <>
                    <br />
                    {t("screens.media.genresUnknown")}
                  </>
                )}{" "}
                {sheet && !isFilm && sheet.status ? (
                  <>
                    <br />
                    {t("screens.media.seriesStatus", {
                      // french-ok: the INTERPOLATION placeholder, named by
                    // `seriesStatus` in fr.json — renaming this half alone
                    // leaves « Série {{statut}} » on screen.
                    statut: sheet.status.toLowerCase(),
                    })}
                  </>
                ) : (
                  ""
                )}
              </p>
              {sheet?.note ? (
                <span className="hn">
                  <Icon paths={icons.star} />
                  {String(sheet.note).replace(".", ",")}
                  <span
                    style={{
                      color: "var(--muted-foreground)",
                      fontWeight: 400,
                    }}
                  >
                    {" "}
                    {t("screens.media.ratingSource")}
                  </span>
                </span>
              ) : (
                ""
              )}
            </div>
          </div>

          {trailer ? (
            <a
              className="trailer"
              href={`https://www.youtube.com/watch?v=${trailer.key}`}
              target="_blank"
              rel="noopener"
              data-yt={trailer.key}
            >
              <span className="pl">
                <Icon paths={icons.play} />
              </span>{" "}
              <span>
                {t("screens.media.trailer")}
                <small>{trailer.name}</small>
              </span>{" "}
              <span className="tsrc">
                <Icon paths={icons.ext} />
                YouTube
              </span>
            </a>
          ) : (
            <p className="noinfo">{t("screens.media.noTrailer")}</p>
          )}

          <div>
            <h2 className="h2" style={{ marginBottom: "6px" }}>
              {t("screens.media.synopsis")}
            </h2>
            <p
              style={{
                margin: 0,
                fontSize: "12.5px",
                lineHeight: 1.55,
                color: "var(--muted-foreground)",
              }}
            >
              {sheet?.ov ? sheet.ov : t("screens.media.synopsisUnknown")}
            </p>
          </div>

          <div>
            <h2 className="h2" style={{ marginBottom: "8px" }}>
              {isFilm
                ? t("screens.media.castHeadingFilm")
                : t("screens.media.castHeadingSeries")}
            </h2>
            <div className="panel" style={{ marginBottom: "10px" }}>
              <div className="kv">
                <span>
                  {isFilm
                    ? t("screens.media.director")
                    : t("screens.media.creator")}
                </span>
                <span>
                  {(isFilm ? sheet?.real : sheet?.crea) ??
                    t("screens.media.unknown")}
                </span>
              </div>
            </div>
            {sheet?.cast?.length ? (
              <div className="cast" data-noswipe="">
                {sheet.cast.map((cast) => (
                  <figure key={cast.n}>
                    <span className="ca">
                      {CAST[cast.n] ? (
                        <img src={CAST[cast.n]} alt="" loading="lazy" />
                      ) : (
                        initials(cast.n)
                      )}
                    </span>
                    <figcaption>
                      <b>{cast.n}</b>
                      <span>{cast.r || t("screens.media.roleUnknown")}</span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            ) : (
              <p className="noinfo">{t("screens.media.castUnknown")}</p>
            )}
          </div>

          <div>
            <h2 className="h2" style={{ marginBottom: "6px" }}>
              {t("screens.media.library")}
            </h2>
            <div className="panel">
              {!owns ? (
                <>
                  <div className="kv">
                    <span>{t("screens.media.inLibrary")}</span>
                    <span>
                      <span className="pip neutral"></span>
                      {t("screens.media.no")}
                    </span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.media.follow")}</span>
                    <span>
                      {followed
                        ? t("screens.media.followActive")
                        : t("screens.media.followInactive")}
                    </span>
                  </div>
                  {catalog.length ? (
                    <div className="kv">
                      <span>{`${t("screens.media.catalogue")} ${isFilm ? "" : t("screens.media.catalogueKnown")}`}</span>
                      <span>
                        {`${catalog.length} ${catalog.length > 1 ? t("screens.media.seasonLowerPlural") : t("screens.media.seasonLower")} · ${catalogEp} ${t("screens.media.episodes")}`}
                      </span>
                    </div>
                  ) : (
                    ""
                  )}
                </>
              ) : isFilm ? (
                <>
                  <div className="kv">
                    <span>{t("screens.media.owned")}</span>
                    <span>
                      <span className="pip success"></span>
                      {t("screens.media.yes")}
                    </span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.media.file")}</span>
                    <span
                      style={{
                        fontFamily: "ui-monospace,Menlo,monospace",
                        fontSize: "11px",
                      }}
                    >
                      {`${baseTitle(title)}.${sheet?.y ?? "2026"}.MULTi.1080p.mkv`}
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <div className="kv">
                    <span>{t("screens.media.seasons")}</span>
                    <span>{sorted.length || t("screens.media.unknown")}</span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.media.airedEpisodes")}</span>
                    <span>{aired || t("screens.media.unknown")}</span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.media.ownedPlural")}</span>
                    <span>{own}</span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.media.completeness")}</span>
                    <span>
                      <span
                        className={`pip ${pct === 100 ? "success" : pct === null ? "neutral" : "warning"}`}
                      ></span>
                      {pct === null
                        ? t("screens.media.unknownFeminine")
                        : pct + " %"}
                    </span>
                  </div>
                </>
              )}
            </div>
            <SeasonList
              sheet={sheet}
              seasons={sorted}
              owns={owns}
              catalog={catalog}
              title={title}
            />
          </div>

          <div>
            <h2 className="h2" style={{ marginBottom: "6px" }}>
              {t("screens.media.information")}
            </h2>
            <div className="panel">
              <div className="kv">
                <span>{t("screens.media.follow")}</span>
                {/* The SECOND follow test, and the strict one: an exact title
                    match, or an exact match on the title without its year
                    suffix. The hero block above answers the same question
                    through `baseTitle` on BOTH sides — a follow recorded
                    under a different year suffix reads « actif » there and
                    « non suivi » here. Transplanted as found. */}
                <span>
                  {follows.some(
                    (follow) =>
                      follow.t === title || follow.t === title.split(" (")[0],
                  )
                    ? t("screens.media.followActive")
                    : t("screens.media.followInactive")}
                </span>
              </div>
              {Object.entries(prov).map(([key, value]) => (
                <div className="kv" key={key}>
                  <span>{key.toUpperCase()}</span>
                  <span
                    style={{
                      fontFamily: "ui-monospace,Menlo,monospace",
                      fontSize: "11px",
                    }}
                  >
                    {String(value)}
                  </span>
                </div>
              ))}
              <div className="kv">
                <span>{t("screens.media.metadataRefreshed")}</span>
                <span>{t("screens.media.metadataRefreshedValue")}</span>
              </div>
            </div>
          </div>

          <div className="sheetacts secondary">
            {owns ? (
              <>
                <button
                  className="sact"
                  data-toast={t("screens.media.rescrapeToast")}
                >
                  <Icon paths={icons.refresh} />
                  {t("screens.media.rescrape")}
                </button>{" "}
                <button className="sact danger" data-del={title}>
                  <Icon paths={icons.trash} />
                  {t("screens.media.delete")}
                </button>
              </>
            ) : followed ? (
              <button className="mediaadd done" disabled>
                <Icon paths={icons.check} />
                {isFilm
                  ? t("screens.media.added")
                  : t("screens.media.followed")}
              </button>
            ) : (
              // No sheet-refresh attribute: the legacy button asked the sheet to
              // REOPEN itself so the label would flip under the finger. This
              // screen re-renders from the store instead — the follow act
              // bumps it, and the button becomes `mediaadd done` in place.
              <button
                className="mediaadd"
                data-follow={title}
                // french-ok: a data-* VALUE, frozen with the DOM contract
                data-fkind={isFilm ? "Film" : "Série"}
              >
                <Icon paths={icons.plus} />
                {isFilm
                  ? t("screens.media.add")
                  : t("screens.media.followVerb")}
              </button>
            )}
          </div>

          <div className="note">
            <b>{t("screens.media.noteTitle")}</b> {t("screens.media.noteBody")}
          </div>
        </div>
      </div>
    </section>
  );
}
