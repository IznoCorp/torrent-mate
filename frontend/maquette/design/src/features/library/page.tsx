// design/src/pages/library.tsx
// The fifth migrated PAGE, and the first whose CONTENT the fragment used to
// write after the page was drawn: legacy `viewLibrary()` returned a skeleton —
// an empty `#libitems`, an empty `#libcount` — and `fillLib()` / `libFoot()` /
// `paintLibCount()` filled it as the operator scrolled, `fillLib` replacing the
// element outright (`box.outerHTML = …`). Two worlds writing one container is
// what tore the React root down once already, so the list and its loading move
// here WITH the page rather than leaving a seam behind.
//
// Markup is TRANSPLANTED, not translated. The rows go through `libRowHTML` and
// `tileHTML`, reused VERBATIM: they carry the `data-*` the document-level
// delegation reads (`data-tile`, `data-del`, `data-swipeact`, `data-panel`,
// `data-mediasheet`), and re-deriving that markup here would drift the one thing
// that seam depends on being byte-exact.
//
// WHAT DOES NOT MOVE: the selection bar. `paintSelBar()` creates and removes a
// `.selbar` inside `#device`, a node React never draws — so the legacy owns it
// from creation to removal, and this component only asks for a repaint after it
// renders, exactly as `fillLib` did. Moving it would put a second portal where
// the current arrangement already has one owner.
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { useLibraryReference, type IncompleteShow, type LibraryRow } from "../../features/library/reference";
import {
  registerListingPaging,
  useLibraryCategories,
  useLibraryIncomplete,
  useLibraryListing,
} from "./queries";
import { useStoreContent, useUiState, writeUiState } from "../../lib/store-access";
import { body, countLine, countLineAction, emptyNote, endMark, filterPill, filterPillCount, filterZone, loadError, loadErrorAction, loadFooter, pillBar, pillScroll, searchClear, searchField, searchInput, section, segment, segmentCount, segmentTab, statusDot, viewSwitch, viewSwitchButton, viewSwitchWrap, viewTabs } from "../../ui/variants";

// The three lenses, in the order the tab bar draws them. The count on
// « Incomplets » is the drawing's own, exactly as the legacy hard-coded it.
const INCOMPLETE_COUNT = 47;

function LibraryHead(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons, render } = useLibraryReference();
  const { data: CATS = [] } = useLibraryCategories();
  const lenses = [
    { id: "cat", label: t("screens.library.lensMedia") },
    { id: "rec", label: t("screens.library.lensRecent") },
    { id: "inc", label: t("screens.library.lensIncomplete"), count: INCOMPLETE_COUNT },
  ];
  return (
    <>
      <div className={viewTabs()} data-region="library/tabs">
        <div className={segment()} data-part="segment" role="tablist">
          {lenses.map((lens) => (
            <button
              key={lens.id}
              className={segmentTab()}
            role="tab"
              aria-selected={state.libLens === lens.id}
              data-lens={lens.id}
            >
              {lens.label}
              {lens.count ? <span className={segmentCount()} data-part="segment/count">{lens.count}</span> : null}
            </button>
          ))}
        </div>
      </div>
      <div className={filterZone()} data-region="library/filters">
        <div className={searchField()}>
          <Icon paths={icons.search} />
          <input
            className={searchInput()}
            // UNCONTROLLED, and NOT keyed by the query. The legacy rebuilt this
            // node on every draw and then put the caret back by hand; React
            // keeps the node, so the dance is unnecessary — and keying it by
            // what one types would recreate the node on every keystroke, which
            // is the same defect wearing the other hat. The field is the one
            // place the operator's own text lives between two renders.
            type="search"
            id="libq"
            defaultValue={state.q as string}
            placeholder={t("screens.library.searchPlaceholder")}
            aria-label={t("screens.library.searchLabel")}
            // THE HANDLER MOVES WITH THE FIELD: `mountSearch` used to bind this
            // from outside, and binding a node React owns from outside is two
            // writers on one field — the same reason the panel took its own
            // `.fieldinput` handler. Native `input`, not React's synthetic
            // `onChange`, because that is the event the legacy bound and the
            // one a probe dispatches.
            ref={(element) => {
              if (!element) return;
              // AND WHAT CHANGES THE QUERY FROM OUTSIDE has to reach the field:
              // the clear cross, or a driven state. The legacy got this for
              // free by rebuilding the node; an uncontrolled input keeps what
              // was typed, so a cross that emptied the list would have left the
              // word sitting in the field. Assigning only when the two DIFFER
              // is what keeps this from touching the node mid-word — while one
              // types, they are equal.
              const query = state.q as string;
              if (element.value !== query) element.value = query;
              // The ATTRIBUTE too. `defaultValue` writes it at mount only, and
              // the legacy re-emitted it on every draw — so anything reading
              // the serialised markup (the fidelity oracle included) would see
              // an empty field over one that shows a word.
              if (element.getAttribute("value") !== query)
                element.setAttribute("value", query);
              const commit = () => {
                // ONLY THE QUERY. Resetting a page cursor and clearing an error
                // beside it is what the interface had to do while it owned
                // both; the query KEY carries the search now, so typing asks a
                // different question, which has its own pages and its own
                // error by construction.
                writeUiState({ q: element.value });
                render();
              };
              element.addEventListener("input", commit);
              return () => element.removeEventListener("input", commit);
            }}
          />
          {state.q ? (
            <button
              className={searchClear()}
              data-clearq="lib"
              aria-label={t("screens.library.clearLabel")}
            >
              <Icon paths={icons.x} />
            </button>
          ) : null}
        </div>
        <div className={pillBar()}>
          <div className={pillScroll()} data-part="pill/list">
            {state.libLens === "cat"
              ? CATS.map((category) => (
                  <button
                    key={category.id}
                    className={filterPill()}
                    data-part="pill"
                    aria-pressed={state.libCat === category.id}
                    data-cat={category.id}
                  >
                    {category.l}
                    <span className={filterPillCount()}>{category.c}</span>
                  </button>
                ))
              : null}
          </div>
          <div className={viewSwitchWrap()}>
            <div className={viewSwitch()} data-part="view/switch">
              <button
                className={viewSwitchButton()}
                aria-pressed={state.libMode === "list"}
                data-lmode="list"
                aria-label={t("screens.library.listLabel")}
              >
                <Icon paths={icons.list} />
              </button>
              <button
                className={viewSwitchButton()}
                aria-pressed={state.libMode === "grid"}
                data-lmode="grid"
                aria-label={t("screens.library.gridLabel")}
              >
                <Icon paths={icons.grid} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// The count line's own sentence: how many of how many, or how many results for
// what was typed. The category qualifies both, and « Tout » qualifies neither
// — it is the whole library, not a filter on it.
function CountLine(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { data: CATS = [] } = useLibraryCategories();
  // FROM THE SAME QUERY THE LIST READS, so the two cannot disagree about how
  // many rows are on screen — §13's « une seule dérivation par question »,
  // which two independent counts is the standing way to break.
  const listing = useLibraryListing(
    String(state.q ?? ""),
    String(state.libCat ?? ""),
    String(state.sortKey ?? ""),
    Boolean(state.sortReversed),
  );
  const total = listing.data?.pages[0]?.total ?? 0;
  const shown = (listing.data?.pages ?? []).reduce(
    (count, page) => count + page.items.length, 0);
  const category = CATS.find((entry) => entry.id === state.libCat);
  // THE LIBRARY'S OWN TOTAL, SERVED. It was written here as the literal 1861,
  // three lines under a comment saying the count comes « from the same query
  // the list reads, so the two cannot disagree » — while the query answered
  // that very number and the screen printed a constant instead. Change the
  // seed and the screen went on saying 1861.
  const universe = category && category.of ? category.c : total;
  const suffix =
    category && category.of
      ? t("screens.library.countCategory", { category: category.l.toLowerCase() })
      : "";
  const query = (state.q as string).trim();
  return (
    <span id="libcount">
      {query === "" ? (
        <>
          <b>{shown}</b>
          {t("screens.library.countShownMiddle")}
          <b>{universe}</b>
          {suffix}
        </>
      ) : (
        <>
          <b>{total}</b>
          {t(
            total > 1
              ? "screens.library.countResultMany"
              : "screens.library.countResultOne",
            { query: state.q as string },
          )}
          {suffix}
        </>
      )}
    </span>
  );
}

// What the list says when it has nothing to show, and the two reasons are not
// the same sentence: a search that matched nothing is not a category this
// prototype does not carry.
function EmptyLibrary(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { data: CATS = [] } = useLibraryCategories();
  const category = CATS.find((entry) => entry.id === state.libCat);
  const filter = category && category.of ? category.l.toLowerCase() : null;
  if ((state.q as string).trim() !== "") {
    return (
      <div className={emptyNote()} data-part="empty-state">
        <b>
          {t("screens.library.emptySearchLead", { query: state.q as string })}
          {filter
            ? t("screens.library.emptySearchInCategory", { category: filter })
            : ""}
          {t("screens.library.emptySearchDot")}
        </b>
        {t("screens.library.emptySearchBody")}
        {filter ? (
          t("screens.library.emptySearchNarrow")
        ) : (
          <>
            <br />
            <br />
            {t("screens.library.emptySearchElsewhereLead")}
            <b>{t("screens.library.emptySearchElsewhereAction")}</b>
            {t("screens.library.emptySearchElsewhereEnd")}
          </>
        )}
      </div>
    );
  }
  return (
    <div className={emptyNote()} data-part="empty-state">
      <b>
        {t("screens.library.emptyCategoryLead", {
          category: filter ?? t("screens.library.emptyCategoryFallback"),
        })}
      </b>
      {t("screens.library.emptyCategoryMiddle")}
      <b>{category?.c ?? 0}</b>
      {t("screens.library.emptyCategoryEnd")}
    </div>
  );
}

// The list, its footer, and the sentinel that loads the next page. The FOOTER
// is the sentinel — the legacy's own arrangement, kept: an observer watching a
// separate marker would fire at a different moment and change when the next
// page arrives.
function LibraryList(): ReactElement {
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
    items = (
      <div
        key={version}
        id="libitems"
        className={grid ? "gallery" : "sec"} data-part={grid ? "grid" : "section"}
        dangerouslySetInnerHTML={{
          __html: rows
            .slice(0, count)
            .map((row, index) =>
              grid
                ? tileHTML(row, (row as LibraryRow).f, { index })
                : libRowHTML(row, index),
            )
            .join(""),
        }}
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

export function LibraryPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  const { cardHTML, tileHTML } = useLibraryReference();
  // The « incomplets » lens reads its own resource. The « récent » lens does
  // NOT: it draws the same `LibraryList`, which is the listing in the source's
  // own order — a second read of the same rows would be a second answer to one
  // question (§13), and `RECENT` is the fixture that arrangement made
  // redundant.
  const { data: INCOMPLETE = [] } = useLibraryIncomplete();

  if (state.libLens === "inc") {
    return (
      <>
        <LibraryHead />
        <div className={countLine()} data-part="count-line" data-region="library/count-line">
          <span className={statusDot({ tone: "warning" })} data-part="status-dot"></span>
          <span>{t("screens.library.incompleteTitle")}</span>
          <b style={{ marginLeft: "auto" }}>{INCOMPLETE_COUNT}</b>
        </div>
        <div className={body()} data-part="surface/body" data-region="library/body">
          <div className="note" data-part="note">
            <b>{t("screens.library.incompleteNoteLead")}</b>
            {t("screens.library.incompleteNoteMiddle")}
            <code>{t("screens.library.incompleteUnknown")}</code>
            {t("screens.library.incompleteNoteAfterUnknown")}
            <code>{t("screens.library.incompleteInvented")}</code>
            {t("screens.library.incompleteNoteEnd")}
          </div>
          {state.libMode === "grid" ? (
            <div
              className="gallery" data-part="grid"
              dangerouslySetInnerHTML={{
                __html: INCOMPLETE.map((show: IncompleteShow) =>
                  tileHTML(
                    show,
                    t("screens.library.incompleteEpisodes", {
                      owned: show.o,
                      all: show.a,
                    }),
                  ),
                ).join(""),
              }}
            />
          ) : (
            <div
              className={section()} data-part="section"
              dangerouslySetInnerHTML={{
                __html: INCOMPLETE.map((show: IncompleteShow) =>
                  cardHTML({
                    t: show.t,
                    s: t(
                      show.a - show.o > 1
                        ? "screens.library.incompleteSubMany"
                        : "screens.library.incompleteSubOne",
                      { year: show.y, count: show.a - show.o },
                    ),
                    f: `${show.o}/${show.a}`,
                    chip: ["warning", t("screens.library.incompleteChip")],
                  }),
                ).join(""),
              }}
            />
          )}
        </div>
      </>
    );
  }

  if (state.libLens === "rec") {
    return (
      <>
        <LibraryHead />
        <div className={countLine()} data-part="count-line" data-region="library/count-line">
          <span>{t("screens.library.recentTitle")}</span>
        </div>
        <div className={body()} data-part="surface/body" data-region="library/body">
          <div className="note" data-part="note">
            <b>{t("screens.library.recentNoteLead")}</b>
            {t("screens.library.recentNoteMiddle")}
            <em>{t("screens.library.recentNoteEmphasis")}</em>
            {t("screens.library.recentNoteEnd")}
          </div>
          <LibraryList />
        </div>
      </>
    );
  }

  return (
    <>
      <LibraryHead />
      <div className={countLine()} data-part="count-line" data-region="library/count-line">
        <CountLine />
        <button className={`${countLineAction()} linkbtn`} data-selmode="1">
          {t("screens.library.select")}
        </button>
        <button className={countLineAction()} style={{ marginLeft: 12 }} data-sort="1">
          <SortLabel />
        </button>
      </div>
      <div className={body()} data-part="surface/body" data-region="library/body">
        <div className="note" data-part="note">
          <b>{t("screens.library.mediaNoteLead")}</b>
          {t("screens.library.mediaNoteMiddle")}
          <code>{t("screens.library.mediaNoteRoute")}</code>
          {t("screens.library.mediaNoteEnd")}
        </div>
        <LibraryList />
        <div className="note" data-part="note">
          <b>{t("screens.library.loadingNoteLead")}</b>
          {t("screens.library.loadingNoteMiddle")}
          <code>{t("screens.library.loadingNoteDatabase")}</code>
          {t("screens.library.loadingNoteEnd")}
        </div>
      </div>
    </>
  );
}

// The sort control's own label: the icon, then the NAME of the direction in
// force — E-001's own promise, read from the table the prototype declares
// rather than restated here.
function SortLabel(): ReactElement {
  const state = useUiState();
  const { icons, TRIS } = useLibraryReference();
  const ways = TRIS[state.sortKey as string];
  return (
    <>
      <Icon paths={icons.sort} />
      {ways[state.sortReversed ? "inverse" : "normal"]}
    </>
  );
}
