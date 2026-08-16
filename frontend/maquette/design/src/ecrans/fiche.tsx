// design/src/ecrans/fiche.tsx
// The centre of the product: legacy `openFiche(title)` (`refonte.html`) — ONE
// media sheet for every medium — reborn as a real route (`/fiche/$titre`) and
// a final component. Markup is TRANSPLANTED, not translated: every tag, class
// and data-attribute below is the one `refonte.html`'s BLOCK 2 CSS already
// targets (`.screen`, `.fichebar`, `.herowrap`, `.trailer`, `.cast`,
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
  useContenu,
  useMonde,
  useReferentiel,
  type Fiche,
  type Referentiel,
} from "../donnees";

// The exact shape `svgIcon(paths, strokeWidth)` produced as an HTML string —
// rebuilt as a real element so it composes with JSX. Same helper as
// `profil.tsx`'s, `ajout.tsx`'s and `panneau.tsx`'s, still not shared: the
// extraction those files' comments call for is a follow-up of its own, not a
// silent scope add here.
function Icone({
  paths,
  strokeWidth,
}: {
  paths: string;
  strokeWidth?: number;
}) {
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

// The fields this screen reads off a `FICHES_RAW` entry. The source stays
// untyped JS and a movie and a show do not carry the same keys, so every
// field is optional — a narrowed view of `Fiche`, never a claim about what a
// sheet always has.
type EpisodeFiche = { n: number; t: string; air?: string | null };
type SaisonCatalogue = { n: number; ep: number | null; air?: string };
type FicheMedia = {
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
  statut?: string;
  saisons?: SaisonCatalogue[];
  eps?: Record<string, EpisodeFiche[]>;
  possede?: boolean;
};

// The slice of the simulated world this screen reads: the follow list, and
// only its titles.
type Suivi = { t: string };

// One row of the season list: an owned-seasons row (`[n, aired, own]` from
// `saisonsDe`) and a catalogue row (`{ n, ep, air }` from the sheet) are
// folded into the same shape before rendering, exactly as `saisonsFicheHTML`
// folds them.
type LigneSaison = {
  n: number;
  aired: number | null;
  own: number;
  air?: string;
};

function SaisonsFiche({
  fiche,
  saisons,
  possede,
  cat,
  titre,
}: {
  fiche: FicheMedia | null;
  saisons: [number, number | null, number][];
  possede: boolean;
  cat: SaisonCatalogue[];
  titre: string;
}) {
  const { possedesDe, plages, dateFR, EP_LABEL, AUJOURDHUI } = useReferentiel();
  const { t } = useTranslation();
  const eps = fiche?.eps ?? {};
  const lignes: LigneSaison[] = possede
    ? saisons.map(([number, aired, own]) => ({ n: number, aired, own }))
    : cat.map((cat2) => ({
        n: cat2.n,
        aired: cat2.ep,
        own: 0,
        air: cat2.air,
      }));
  if (!lignes.length) return null;
  return (
    <div style={{ marginTop: "10px" }}>
      {lignes.map((ligne) => {
        const liste = eps[String(ligne.n)] ?? null;
        const detenus = possede ? possedesDe(titre, ligne.n) : null;
        /* The count is DERIVED from the owned numbers when they are known;
           a total that does not say where the holes are is no longer
           trusted. */
        const nbOwn = detenus
          ? [...detenus].filter(
              (element) => !ligne.aired || element <= ligne.aired,
            ).length
          : ligne.own;
        const complete = possede && ligne.aired != null && nbOwn >= ligne.aired;
        const manque = ligne.aired != null ? ligne.aired - nbOwn : null;
        /* With no known total, reason up to the highest owned episode: a
           hole BELOW that maximum is a genuine gap, above it nothing is
           known. */
        const borne =
          ligne.aired === 0
            ? 0
            : detenus && detenus.size
              ? (ligne.aired ?? Math.max(...detenus))
              : ligne.aired || 0;
        const numsManquants =
          possede && detenus && ligne.aired
            ? Array.from(
                { length: ligne.aired },
                (ignored, index) => index + 1,
              ).filter((from) => !detenus.has(from))
            : [];
        const corps = liste ? (
          <div className="panel" style={{ marginTop: "8px" }}>
            {liste.map((liste2) => {
              /* SUBTLE state colour: a 6px dot and the number in the
                 tone. The title stays neutral — it is what one reads
                 first, so it keeps maximum contrast. One colour signal
                 per row, not a Christmas tree. */
              const futur = liste2.air && liste2.air > AUJOURDHUI;
              /* State comes from the LIST of owned numbers. A « number <=
                 owned count » threshold assumes the hole is always at the
                 end of the season: false for 35 series in this library. */
              const episodeState = futur
                ? "annonce"
                : !possede || !detenus
                  ? "non_verifie"
                  : detenus.has(liste2.n)
                    ? "en_mediatheque"
                    : "a_recuperer";
              return (
                // Same blanks as the season summary, same reason: the row is
                // a flex container (they draw nothing) and its `textContent`
                // is read as one sentence.
                <div className={`eprow ${episodeState}`} key={liste2.n}>
                  <span className="epdot"></span>{" "}
                  <span className="en">
                    E{String(liste2.n).padStart(2, "0")}
                  </span>{" "}
                  <span className="et">{liste2.t}</span>{" "}
                  <span className="ed">
                    {liste2.air
                      ? dateFR(liste2.air)
                      : t("screens.fiche.dateUnknown")}
                    {episodeState === "en_mediatheque"
                      ? ""
                      : ` · ${EP_LABEL[episodeState].toLowerCase()}`}
                  </span>
                </div>
              );
            })}
          </div>
        ) : borne && detenus ? (
          /* No episode titles, but the numbers are known: the matrix still
             answers « which ones are missing ». When the aired total is
             unknown, go no further than the highest owned episode — beyond
             it nothing is known, and it says so. */
          <>
            <div className="eps" style={{ marginTop: "8px" }}>
              {Array.from({ length: borne }, (ignored, index) => {
                const number = index + 1;
                const episodeState = detenus.has(number)
                  ? "en_mediatheque"
                  : "a_recuperer";
                return (
                  <span
                    className={`ep ${episodeState}`}
                    key={number}
                    aria-label={t("screens.fiche.episodeAria", {
                      n: number,
                      etat: EP_LABEL[episodeState],
                    })}
                  >
                    {String(number).padStart(2, "0")}
                  </span>
                );
              })}
            </div>
            {ligne.aired == null ? (
              <p className="nofiche" style={{ marginTop: "6px" }}>
                {t("screens.fiche.beyondEpisode", { n: borne })}
              </p>
            ) : (
              ""
            )}
          </>
        ) : ligne.aired === 0 || ligne.aired === null ? (
          <p className="nofiche" style={{ marginTop: "8px" }}>
            {t("screens.fiche.seasonAnnounced")}
          </p>
        ) : (
          <p className="nofiche" style={{ marginTop: "8px" }}>
            {t("screens.fiche.episodesNotDetailed")}
          </p>
        );
        return (
          <details
            className="season"
            key={ligne.n}
            open={!(complete || !possede)}
          >
            <summary>
              {/* The blanks between these children are NOT decoration: the
                  legacy template carried a line break at each of them, and a
                  reader of `summary.textContent` — the rule that derives the
                  season number from it, an assistive technology reading the
                  row — would otherwise see « Saison 33/13 ». `summary` is a
                  flex container, so a whitespace-only node draws nothing. */}
              {t("common.season")} {ligne.n}{" "}
              <span className="sfr">
                {ligne.aired === 0
                  ? t("screens.fiche.seasonUpcoming")
                  : possede
                    ? `${nbOwn}/${ligne.aired ?? "?"}`
                    : `${ligne.aired ?? "?"} ${t("screens.fiche.episodesShort")}`}
              </span>{" "}
              {possede && manque != null && manque > 0 ? (
                <span className="miss">
                  {manque}{" "}
                  {manque > 1 ? t("common.missingPlural") : t("common.missing")}
                </span>
              ) : (
                ""
              )}{" "}
              {!possede && ligne.air ? (
                <span
                  className="miss"
                  style={{
                    background: "transparent",
                    color: "var(--muted-foreground)",
                    fontWeight: 400,
                  }}
                >
                  {dateFR(ligne.air)}
                </span>
              ) : (
                ""
              )}
            </summary>
            {numsManquants.length ? (
              <p className="manquants">
                {t("screens.fiche.missingList", {
                  liste: plages(numsManquants),
                })}
              </p>
            ) : (
              ""
            )}
            {corps}
          </details>
        );
      })}
    </div>
  );
}

// The banner prefers the wide visual; the vertical poster is only a fallback,
// and nothing at all when there is neither — same resolution order as the
// legacy sheet, base title included.
function afficheDe(referentiel: Referentiel, titre: string): string | null {
  const { HEROS, POSTERS, baseTitle } = referentiel;
  return (
    HEROS[titre] ??
    HEROS[baseTitle(titre)] ??
    POSTERS[titre] ??
    POSTERS[baseTitle(titre)] ??
    null
  );
}

export function FicheEcran() {
  const { titre: brut } = useParams({ from: "/fiche/$titre" });
  // Defensive: `__ecrans.fiche` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const titre = brut.normalize("NFC");
  // `world.follows` is MUTATED IN PLACE by the still-legacy follow act
  // (`actionSuivre`, refonte.html) — the reference never changes, so
  // `useMonde()` alone would not notice. Subscribing to `version` forces the
  // re-render on that bump, and the read below then sees the mutated list
  // fresh: this is what flips the « Suivre » button to « Suivi » without the
  // legacy sheet reopening itself.
  useContenu((c) => c.version);
  const monde = useMonde() as { follows?: Suivi[] } | null;
  const suivis = monde?.follows ?? [];
  const referentiel = useReferentiel();
  const { t } = useTranslation();
  const {
    icons,
    baseTitle,
    sheetFor,
    saisonsDe,
    ACTEURS,
    trailerIds,
    initials,
  } = referentiel;

  const fiche = sheetFor(titre) as (Fiche & FicheMedia) | null;
  const isFilm = fiche ? fiche.k === "movie" : false;
  /* Seasons are DERIVED from the provider catalogue crossed with the numbers
     actually owned. A hand-written table gave seasons to 10 series only, and
     none of them to the INCOMPLETE ones — the very media the question is
     about. */
  const sort = saisonsDe(titre)
    .slice()
    .sort((slice, index) => index[0] - slice[0]);
  const own = sort.reduce(
    (accumulator, element) => accumulator + element[2],
    0,
  );
  const aired = sort.reduce(
    (accumulator, element) => accumulator + (element[1] ?? 0),
    0,
  );
  const pct = aired ? Math.round((own / aired) * 100) : null;
  // A suggestion is NOT in the library: the sheet must say so and offer to
  // add it, not to delete it. Same template, with the only variation reality
  // imposes.
  const possede = fiche?.possede !== false;
  // The FIRST of the two follow tests, and it is deliberately the LOOSE one:
  // it matches on the base title, so « Silo » follows « Silo (2023) ». The
  // « Informations » block below asks the SAME question with a STRICTER test
  // — the asymmetry is the legacy sheet's, transplanted rather than
  // reconciled here.
  const suivi = suivis.some(
    (follow) => baseTitle(follow.t) === baseTitle(titre),
  );
  const cat = (fiche?.saisons ?? [])
    .slice()
    .sort((slice, index) => index.n - slice.n);
  // `?? 0` where the legacy addition simply let `null` coerce to zero: same
  // total, spelled so the type says what the arithmetic already did.
  const catEp = cat.reduce(
    (accumulator, element) => accumulator + (element.ep ?? 0),
    0,
  );
  const prov = fiche?.ids ?? {};
  const url = prov.tvdb
    ? `/media/tvdb/${prov.tvdb}`
    : prov.tmdb
      ? `/media/tmdb/${prov.tmdb}`
      : null;
  const affiche = afficheDe(referentiel, titre);
  // The link exists or it does not; where one arrives from changes nothing.
  const bande = trailerIds[titre] ?? trailerIds[baseTitle(titre)] ?? null;

  return (
    <section className="screen open" data-cle={`fiche:${titre}`}>
      <div className="fichebar">
        <button className="fback" onClick={() => window.__pont.retour()}>
          <Icone paths={icons.left} />
          {t("screens.fiche.back")}
        </button>{" "}
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--muted-foreground)",
          }}
        >
          {url ?? t("screens.fiche.unidentified")}
        </span>
      </div>
      <div className="port">
        <div className="body">
          <div className={`herowrap${affiche ? "" : " noaffiche"}`}>
            <div
              className="herobg"
              aria-hidden="true"
              style={
                affiche ? { backgroundImage: `url('${affiche}')` } : undefined
              }
            ></div>
            <div className="hero">
              <h2 className="ht">{titre.split(" (")[0]}</h2>
              <p className="hm">
                {fiche
                  ? `${fiche.y || t("screens.fiche.yearUnknown")} · ${isFilm ? t("common.film") : t("common.series")}${fiche.duree ? ` · ${fiche.duree} ${t("screens.fiche.minutesShort")}` : ""}`
                  : t("screens.fiche.metadataUnknown")}{" "}
                {fiche?.g ? (
                  <>
                    <br />
                    {fiche.g}
                  </>
                ) : (
                  <>
                    <br />
                    {t("screens.fiche.genresUnknown")}
                  </>
                )}{" "}
                {fiche && !isFilm && fiche.statut ? (
                  <>
                    <br />
                    {t("screens.fiche.seriesStatus", {
                      statut: fiche.statut.toLowerCase(),
                    })}
                  </>
                ) : (
                  ""
                )}
              </p>
              {fiche?.note ? (
                <span className="hn">
                  <Icone paths={icons.star} />
                  {String(fiche.note).replace(".", ",")}
                  <span
                    style={{
                      color: "var(--muted-foreground)",
                      fontWeight: 400,
                    }}
                  >
                    {" "}
                    {t("screens.fiche.ratingSource")}
                  </span>
                </span>
              ) : (
                ""
              )}
            </div>
          </div>

          {bande ? (
            <a
              className="trailer"
              href={`https://www.youtube.com/watch?v=${bande.key}`}
              target="_blank"
              rel="noopener"
              data-yt={bande.key}
            >
              <span className="pl">
                <Icone paths={icons.play} />
              </span>{" "}
              <span>
                {t("screens.fiche.trailer")}
                <small>{bande.nom}</small>
              </span>{" "}
              <span className="tsrc">
                <Icone paths={icons.ext} />
                YouTube
              </span>
            </a>
          ) : (
            <p className="nofiche">{t("screens.fiche.noTrailer")}</p>
          )}

          <div>
            <h2 className="h2" style={{ marginBottom: "6px" }}>
              {t("screens.fiche.synopsis")}
            </h2>
            <p
              style={{
                margin: 0,
                fontSize: "12.5px",
                lineHeight: 1.55,
                color: "var(--muted-foreground)",
              }}
            >
              {fiche?.ov ? fiche.ov : t("screens.fiche.synopsisUnknown")}
            </p>
          </div>

          <div>
            <h2 className="h2" style={{ marginBottom: "8px" }}>
              {isFilm
                ? t("screens.fiche.castHeadingFilm")
                : t("screens.fiche.castHeadingSeries")}
            </h2>
            <div className="panel" style={{ marginBottom: "10px" }}>
              <div className="kv">
                <span>
                  {isFilm
                    ? t("screens.fiche.director")
                    : t("screens.fiche.creator")}
                </span>
                <span>
                  {(isFilm ? fiche?.real : fiche?.crea) ??
                    t("screens.fiche.unknown")}
                </span>
              </div>
            </div>
            {fiche?.cast?.length ? (
              <div className="cast" data-noswipe="">
                {fiche.cast.map((cast) => (
                  <figure key={cast.n}>
                    <span className="ca">
                      {ACTEURS[cast.n] ? (
                        <img src={ACTEURS[cast.n]} alt="" loading="lazy" />
                      ) : (
                        initials(cast.n)
                      )}
                    </span>
                    <figcaption>
                      <b>{cast.n}</b>
                      <span>{cast.r || t("screens.fiche.roleUnknown")}</span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            ) : (
              <p className="nofiche">{t("screens.fiche.castUnknown")}</p>
            )}
          </div>

          <div>
            <h2 className="h2" style={{ marginBottom: "6px" }}>
              {t("screens.fiche.library")}
            </h2>
            <div className="panel">
              {!possede ? (
                <>
                  <div className="kv">
                    <span>{t("screens.fiche.inLibrary")}</span>
                    <span>
                      <span className="pip neutral"></span>
                      {t("screens.fiche.no")}
                    </span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.fiche.follow")}</span>
                    <span>
                      {suivi
                        ? t("screens.fiche.followActive")
                        : t("screens.fiche.followInactive")}
                    </span>
                  </div>
                  {cat.length ? (
                    <div className="kv">
                      <span>{`${t("screens.fiche.catalogue")} ${isFilm ? "" : t("screens.fiche.catalogueKnown")}`}</span>
                      <span>
                        {`${cat.length} ${cat.length > 1 ? t("screens.fiche.seasonLowerPlural") : t("screens.fiche.seasonLower")} · ${catEp} ${t("screens.fiche.episodes")}`}
                      </span>
                    </div>
                  ) : (
                    ""
                  )}
                </>
              ) : isFilm ? (
                <>
                  <div className="kv">
                    <span>{t("screens.fiche.owned")}</span>
                    <span>
                      <span className="pip success"></span>
                      {t("screens.fiche.yes")}
                    </span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.fiche.file")}</span>
                    <span
                      style={{
                        fontFamily: "ui-monospace,Menlo,monospace",
                        fontSize: "11px",
                      }}
                    >
                      {`${baseTitle(titre)}.${fiche?.y ?? "2026"}.MULTi.1080p.mkv`}
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <div className="kv">
                    <span>{t("screens.fiche.seasons")}</span>
                    <span>{sort.length || t("screens.fiche.unknown")}</span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.fiche.airedEpisodes")}</span>
                    <span>{aired || t("screens.fiche.unknown")}</span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.fiche.ownedPlural")}</span>
                    <span>{own}</span>
                  </div>
                  <div className="kv">
                    <span>{t("screens.fiche.completeness")}</span>
                    <span>
                      <span
                        className={`pip ${pct === 100 ? "success" : pct === null ? "neutral" : "warning"}`}
                      ></span>
                      {pct === null
                        ? t("screens.fiche.unknownFeminine")
                        : pct + " %"}
                    </span>
                  </div>
                </>
              )}
            </div>
            <SaisonsFiche
              fiche={fiche}
              saisons={sort}
              possede={possede}
              cat={cat}
              titre={titre}
            />
          </div>

          <div>
            <h2 className="h2" style={{ marginBottom: "6px" }}>
              {t("screens.fiche.information")}
            </h2>
            <div className="panel">
              <div className="kv">
                <span>{t("screens.fiche.follow")}</span>
                {/* The SECOND follow test, and the strict one: an exact title
                    match, or an exact match on the title without its year
                    suffix. The hero block above answers the same question
                    through `baseTitle` on BOTH sides — a follow recorded
                    under a different year suffix reads « actif » there and
                    « non suivi » here. Transplanted as found. */}
                <span>
                  {suivis.some(
                    (follow) =>
                      follow.t === titre || follow.t === titre.split(" (")[0],
                  )
                    ? t("screens.fiche.followActive")
                    : t("screens.fiche.followInactive")}
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
                <span>{t("screens.fiche.metadataRefreshed")}</span>
                <span>{t("screens.fiche.metadataRefreshedValue")}</span>
              </div>
            </div>
          </div>

          <div className="sheetacts secondary">
            {possede ? (
              <>
                <button
                  className="sact"
                  data-toast={t("screens.fiche.rescrapeToast")}
                >
                  <Icone paths={icons.refresh} />
                  {t("screens.fiche.rescrape")}
                </button>{" "}
                <button className="sact danger" data-del={titre}>
                  <Icone paths={icons.trash} />
                  {t("screens.fiche.delete")}
                </button>
              </>
            ) : suivi ? (
              <button className="ficheadd done" disabled>
                <Icone paths={icons.check} />
                {isFilm
                  ? t("screens.fiche.added")
                  : t("screens.fiche.followed")}
              </button>
            ) : (
              // No `data-refiche`: the legacy button asked the sheet to
              // REOPEN itself so the label would flip under the finger. This
              // screen re-renders from the store instead — the follow act
              // bumps it, and the button becomes `ficheadd done` in place.
              <button
                className="ficheadd"
                data-follow={titre}
                data-fkind={isFilm ? "Film" : "Série"}
              >
                <Icone paths={icons.plus} />
                {isFilm
                  ? t("screens.fiche.add")
                  : t("screens.fiche.followVerb")}
              </button>
            )}
          </div>

          <div className="note">
            <b>{t("screens.fiche.noteTitle")}</b> {t("screens.fiche.noteBody")}
          </div>
        </div>
      </div>
    </section>
  );
}
