// The library's list: the listing page by page, the windowed rows, the
// sentinel that asks for the next page, and the footer that says whether
// there is more. The rows go through `libRowHTML` and `tileHTML`, reused
// VERBATIM: they carry the `data-*` the document-level delegation reads, and
// re-deriving that markup here would drift the one thing that seam depends
// on being byte-exact.
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { VirtualRows } from "../../ui/virtual-rows";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { LIBRARY_WINDOW, useLibraryReference, type LibraryRow } from "./reference";
import { registerListingPaging, useLibraryListing } from "./queries";
import { useStoreContent, useUiState } from "../../lib/store-access";
import { EmptyLibrary } from "./library-empty";
import { endMark, loadError, loadErrorAction, loadFooter, section } from "../../ui/variants";

// The list, its footer, and the sentinel that loads the next page. The FOOTER
// is the sentinel — the legacy's own arrangement, kept: an observer watching a
// separate marker would fire at a different moment and change when the next
// page arrives.
export function LibraryList(): ReactElement {
  const state = useUiState();
  // The store's own draw counter, which every write bumps — including the
  // in-place world mutations a delegated action makes.
  const version = useStoreContent((content) => content.version);
  const { t } = useTranslation();
  const { libRowHTML, tileHTML, paintSelBar } = useLibraryReference();
  const footRef = useRef<HTMLDivElement | null>(null);
  const grid = state.libMode === "grid";
  // FROM THE CACHE, PAGE BY PAGE (invariant 4). Four keys leave the interface's
  // own store with this: `libCount` was a page cursor, `libLoading` and
  // `libErr` were query state, and `libFailedOnce` remembered whether the
  // simulated failure had fired. Every one of them is the query's, and the
  // query is where they live now.
  //
  // THE ORDER IS PART OF THE QUESTION. The filtering and the sort used to be
  // done here over the whole set; a page index only means something once the
  // server orders what it pages.
  const listing = useLibraryListing(
    String(state.q ?? ""),
    String(state.libCat ?? ""),
    String(state.sortKey ?? ""),
    Boolean(state.sortReversed),
  );
  const rows = (listing.data?.pages ?? []).flatMap((page) => page.items);
  // WHAT THE END MARK SAYS is what the source HOLDS, never what the library
  // claims and never the size of a filtered answer.
  const loaded = listing.data?.pages[0]?.loaded ?? 0;
  const count = rows.length;
  const complete = !listing.hasNextPage && !listing.isFetchingNextPage;

  // The selection bar is the FRAGMENT's node, repainted after this component
  // draws — exactly where `fillLib` repainted it.
  // `fillLib` reached this line only after populating the ROWS: it returned
  // before it on the skeleton, on the error surface and on an empty list. So
  // repainting on every draw would destroy and rebuild a node the legacy left
  // alone — and that node lives in `#device`, beside the settings save bar.
  const drawsRows = state.phase === "ready" && rows.length > 0;
  useEffect(() => {
    if (drawsRows) paintSelBar();
  });

  // ONE PAGE MORE, asked for by the sentinel coming into view. The cache owns
  // the whole of it now: whether one is in flight, whether the last one failed,
  // and how many have landed. What is left here is the ASKING.
  //
  // WHAT WENT WITH IT, and it is the point of the phase. The 620 ms delay and
  // the « fail once past three pages » were the interface simulating a server
  // it did not have; the delay is the scenario's `setDefaultLatency` and the
  // failure is its `afterCalls`. An interface that decides when its own reads
  // fail is an interface that cannot be shown a real failure.
  const loadMore = () => {
    if (listing.isFetchingNextPage || listing.isError || !listing.hasNextPage) return;
    void listing.fetchNextPage();
  };

  // THE LIST'S OWN « one more page », handed to the door a named state asks
  // through. Registered rather than reconstructed: the query's definition lives
  // in one place, and this is the function that already holds it. Registering
  // is not asking — invariant 5 is about a READ issued from an effect, and
  // nothing is read here.
  useEffect(() => {
    registerListingPaging(() => void listing.fetchNextPage());
    return () => registerListingPaging(null);
  });

  useEffect(() => {
    const foot = footRef.current;
    // THE PORT THIS FOOTER IS ACTUALLY IN, never the first one in the document.
    // `document.querySelector("#port")` answers with whichever port comes first,
    // and with a media sheet open OVER the library that is the SHEET's — so the
    // footer counted as « in view » in a container it does not live in, and the
    // sentinel asked for page after page nobody had scrolled to. The engine
    // never showed it: its loader waited 620 ms per page and the measurement
    // happened before the first one landed. Wiring the list to a cache that
    // answers at once turned a masked defect into 46 402 px of list.
    const port = foot?.closest(".port") ?? null;
    // AND NOT WHILE THE LIST IS NOT ON SCREEN. A surface showing a skeleton or
    // an error is not showing its rows, so nothing has been scrolled past and
    // nothing should be asked for — and the footer sits high in a short
    // container, which is precisely where an observer fires. The engine never
    // showed this either: its loader waited 620 ms per page and re-checked the
    // store's version on landing, so a state measured before the first timer
    // landed looked still. Answering at once made the difference visible.
    if (!foot || !port || complete || listing.isError || !drawsRows) return undefined;
    // NOT WHILE A PAGE IS IN FLIGHT: `loadMoreLib` disconnected the observer
    // for the duration of its own load and reconnected after. The guard in
    // `loadMore` already refuses a second one, but an observer that keeps
    // firing while a page is in flight is a difference in what the page DOES.
    if (listing.isFetchingNextPage) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore();
      },
      { root: port, rootMargin: "220px" },
    );
    observer.observe(foot);
    return () => observer.disconnect();
  });

  let items: ReactElement;
  if (state.phase === "loading") {
    items = (
      <div id="libitems" className={grid ? "gallery" : "sec"} data-part={grid ? "grid" : "section"}>
        <Skeletons count={grid ? 9 : 5} shape={grid ? "tile" : "card"} />
      </div>
    );
  } else if (state.phase === "error") {
    // THE ENGINE'S LAST COMPONENT READER, and it is gone. This branch used to
    // ask `legacy.js` for a string and hand it to `dangerouslySetInnerHTML`, so
    // the markup, the French and the retry all lived in the dying half. The
    // engine keeps `surfErr` for the surfaces IT still draws (D5 — its share
    // dies with the surface that stops needing it), and the retry is real:
    // B-031's inert `<button data-phase="ready">` set a store field and re-asked
    // nothing.
    items = (
      <div
        id="libitems"
        className={grid ? "gallery" : "sec"} data-part={grid ? "grid" : "section"}
      >
        <SurfaceError subject={t("screens.library.errorSubject")} />
      </div>
    );
  } else if (rows.length === 0) {
    items = (
      <div id="libitems" className={grid ? "gallery" : "sec"} data-part={grid ? "grid" : "section"}>
        <EmptyLibrary />
      </div>
    );
  } else {
    // KEYED BY THE DRAW, deliberately. `fillLib` rewrote this container on every
    // `render()`, and things are written into it IMPERATIVELY afterwards — a
    // swipe leaves an inline transform on the row it opened. React keeps nodes
    // whose generated string is unchanged, so an open swipe would survive a
    // repaint that used to snap it shut. A key that moves with the store's own
    // version makes each draw a new node, which is what the legacy did.
    // WINDOWED (P24) — `ui/virtual-rows.tsx` carries the whole reasoning.
    items = (
      <VirtualRows
        drawKey={version}
        count={count}
        {...(grid ? LIBRARY_WINDOW.gallery : LIBRARY_WINDOW.list)}
        scrollElement={() => document.querySelector("#port")}
        className={grid ? "gallery" : "sec"}
        part={grid ? "grid" : "section"}
        renderRow={(index) =>
          grid
            ? tileHTML(rows[index], (rows[index] as LibraryRow).f, { index })
            : libRowHTML(rows[index], index)
        }
      />
    );
  }

  // THE FOOTER FOLLOWS THE COUNT, NEVER THE PHASE. `libFoot()` ran on every
  // draw — over the skeleton, over the error surface, over an empty search —
  // and answered on one question only: is there more to load? A first version
  // here gated it on `phase === "prete"` and on having rows, which silently
  // dropped the end mark under a search that matched nothing and the sentinel
  // under the error surface. Measured against the legacy's own drawing.
  let foot: ReactElement | null = null;
  {
    if (complete) {
      foot = (
        <p className={endMark()}>
          {t("screens.library.endMark", { count: loaded })}
        </p>
      );
    } else if (listing.isError) {
      foot = (
        <div className={loadError()} data-part="load-error">
          <b>{t("screens.library.loadErrorLead")}</b>
          {t("screens.library.loadErrorRest", { count })}
          {/* THE ONLY CONTROL ON A MIGRATED PAGE THAT IS NOT DELEGATED. Every
              other one emits a `data-*` the legacy's document-level handler
              reads; this one is React's own — and it works from inside the
              portal because React attaches its listeners to each portal
              CONTAINER as well as to the root. It was inert all the same until
              R79 measured it alone, for a different reason: the load it starts
              read this render's snapshot, where the error it had just cleared
              was still set. */}
          <button
            className={loadErrorAction()}
            id="libretry"
            onClick={() => void listing.fetchNextPage()}
          >
            {t("screens.library.retry")}
          </button>
        </div>
      );
    } else {
      foot = grid ? (
        <div className="gallery" data-part="grid">
          <Skeletons count={3} shape="tile" />
        </div>
      ) : (
        <div className={section()} data-part="section">
          {Array.from({ length: 2 }, (_, index) => (
            <div key={index} className="sk row" data-skeleton="" />
          ))}
        </div>
      );
    }
  }

  return (
    <>
      {items}
      <div id="libload" className={loadFooter()} ref={footRef}>
        {foot}
      </div>
    </>
  );
}
