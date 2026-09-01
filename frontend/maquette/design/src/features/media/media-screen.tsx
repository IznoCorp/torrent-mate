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
  useMediaReference,
  type MediaReference,
  type MediaSheet,
} from "../../features/media/reference";
import { useStoreContent } from "../../lib/store-access";
import { seasonsHeld, useMediaSeasons, useMediaSheet } from "./queries";
import { backAction, body as bodyClass, screen, screenBar, scrollport, sectionHeading } from "../../ui/variants";
import { Icon } from "../../ui/icon";
import { SkeletonLine } from "../../ui/state-surfaces";
import { MediaCast } from "./media-cast";
import { MediaHero } from "./media-hero";
import { MediaDetails } from "./media-details";
import { MediaLibraryFacts } from "./media-library-facts";
import type { Follow, MediaSheetFields } from "./sheet-fields";

// The banner prefers the wide visual; the vertical poster is only a fallback,
// and nothing at all when there is neither — same resolution order as the
// legacy sheet, base title included.
function artworkFor(reference: MediaReference, title: string): string | null {
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
  // The address names a PROVIDER ID (DOIT-11); the catalogue is keyed by title.
  // The crossing happens in the engine, from the fixture itself, so the two
  // cannot drift. An id nobody carries resolves to `null` and the screen
  // renders its own honest empty case — the same answer it already gave an
  // unknown title, and the only honest one for a stale bookmark.
  const { provider, id } = useParams({ from: "/media/$provider/$id" });
  const lookup = useMediaReference();
  const title = (lookup.titleForProviderId(provider, id) ?? "").normalize("NFC");
  // `world.follows` is MUTATED IN PLACE by the still-legacy follow act
  // (`actionFollow`, refonte.html) — the reference never changes, so
  // `useWorld()` alone would not notice. Subscribing to `version` forces the
  // re-render on that bump, and the read below then sees the mutated list
  // fresh: this is what flips the « Suivre » button to « Suivi » without the
  // legacy sheet reopening itself.
  useStoreContent((c) => c.version);
  // FROM THE CACHE. This read was `useWorld()?.follows`, and the world stopped
  // holding them when the queue converted — so the sheet had been quietly
  // reporting « not followed » for everything, which the oracle cannot see
  // because no named state opens a sheet for a title the operator follows.
  const follows = (window.__followActions?.all() ?? []) as Follow[];
  const reference = useMediaReference();
  const { t } = useTranslation();
  const {
    icons,
    baseTitle,
    CAST,
    trailerIds,
    initials,
  } = reference;

  // FROM THE CACHE, BY ADDRESS (invariant 4, DOIT-11). The engine looked its
  // sheet up by TITLE out of a fixture keyed by title; the address is the
  // identity, and it is what the request carries.
  const sheetRead = useMediaSheet(provider, id);
  const sheet = (sheetRead.data ?? null) as (MediaSheet & MediaSheetFields) | null;
  // IN FLIGHT is two states, and reading one of them is reading half. With
  // placeholder data the query reports `success` and `isPlaceholderData` while
  // the read is still out; with none — an address no title answers — it
  // reports `pending`. Either way a part the screen does not have yet is a
  // part still to come, and the constitution refuses an answer about it
  // (§13): a skeleton stands where the answer will go. An errored read is not
  // in flight — it has answered, and the screen prints what it can.
  const inFlight =
    sheetRead.isPending || (sheetRead.isPlaceholderData && sheetRead.isFetching);
  const isFilm = sheet ? sheet.k === "movie" : false;
  /* Seasons are DERIVED from the provider catalogue crossed with the numbers
     actually owned. A hand-written table gave seasons to 10 series only, and
     none of them to the INCOMPLETE ones — the very media the question is
     about. */
  const seasonsRead = useMediaSeasons(provider, id);
  const catalogue = seasonsRead.data;
  // The seasons have no placeholder — nothing the tap knew says what is
  // aired — so their flight is the plain one.
  const seasonsInFlight = seasonsRead.isPending;
  const sorted = seasonsHeld(catalogue)
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
    <section
      className={`${screen()} open`}
      data-part="screen"
      data-open=""
      data-key={`mediaSheet:${title}`}
      aria-label={title}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => window.__bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.media.back")}
        </button>{" "}
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--color-muted-foreground)",
          }}
        >
          {url ?? (inFlight ? <SkeletonLine width="short" /> : t("screens.media.unidentified"))}
        </span>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={bodyClass()} data-part="surface/body" data-region="screen-media/body">
          <MediaHero title={title} sheet={sheet} isFilm={isFilm} artwork={artwork} trailer={trailer} inFlight={inFlight} />

          <div>
            <h2 className={sectionHeading()} data-part="heading" style={{ marginBottom: "6px" }}>
              {t("screens.media.synopsis")}
            </h2>
            <p
              style={{
                margin: 0,
                fontSize: "var(--text-3)",
                lineHeight: 1.55,
                color: "var(--color-muted-foreground)",
              }}
            >
              {sheet?.ov ? sheet.ov : inFlight ? <SkeletonLine width="full" /> : t("screens.media.synopsisUnknown")}
            </p>
          </div>

          <MediaCast sheet={sheet} isFilm={isFilm} inFlight={inFlight} />

          <MediaLibraryFacts
            sheet={sheet}
            isFilm={isFilm}
            owns={owns}
            followed={followed}
            seasons={sorted}
            own={own}
            aired={aired}
            pct={pct}
            catalog={catalog}
            catalogEp={catalogEp}
            title={title}
            seasonsInFlight={seasonsInFlight}
          />

          <MediaDetails title={title} isFilm={isFilm} owns={owns} followed={followed} follows={follows} prov={prov} inFlight={inFlight} />

          <div className="note" data-part="note">
            <b>{t("screens.media.noteTitle")}</b> {t("screens.media.noteBody")}
          </div>
        </div>
      </div>
    </section>
  );
}
