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
import { Icon } from "../components/icon";
import { useLibraryReference, type IncompleteShow, type LibraryRow } from "../features/library/reference";
import { useStoreContent, useUiState, writeUiState } from "../lib/store-access";

// The three lenses, in the order the tab bar draws them. The count on
// « Incomplets » is the drawing's own, exactly as the legacy hard-coded it.
const INCOMPLETE_COUNT = 47;

function LibraryHead(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    icons,
    CATS,
    LIB_PAGE,
    render,
  } = useLibraryReference();
  const lenses = [
    { id: "cat", label: t("screens.library.lensMedia") },
    { id: "rec", label: t("screens.library.lensRecent") },
    { id: "inc", label: t("screens.library.lensIncomplete"), count: INCOMPLETE_COUNT },
  ];
  return (
    <>
      <div className="viewtabs" data-region="library/tabs">
        <div className="seg" data-part="segment" role="tablist">
          {lenses.map((lens) => (
            <button
              key={lens.id}
              role="tab"
              aria-selected={state.libLens === lens.id}
              data-lens={lens.id}
            >
              {lens.label}
              {lens.count ? <span className="n" data-part="segment/count">{lens.count}</span> : null}
            </button>
          ))}
        </div>
      </div>
      <div className="filters" data-region="library/filters">
        <div className="search">
          <Icon paths={icons.search} />
          <input
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
                writeUiState({
                  q: element.value,
                  libCount: LIB_PAGE,
                  libErr: false,
                });
                render();
              };
              element.addEventListener("input", commit);
              return () => element.removeEventListener("input", commit);
            }}
          />
          {state.q ? (
            <button
              className="searchclear"
              data-clearq="lib"
              aria-label={t("screens.library.clearLabel")}
            >
              <Icon paths={icons.x} />
            </button>
          ) : null}
        </div>
        <div className="pillbar">
          <div className="pillscroll" data-part="pill/list">
            {state.libLens === "cat"
              ? CATS.map((category) => (
                  <button
                    key={category.id}
                    className="pill"
                    data-part="pill"
                    aria-pressed={state.libCat === category.id}
                    data-cat={category.id}
                  >
                    {category.l}
                    <span className="c">{category.c}</span>
                  </button>
                ))
              : null}
          </div>
          <div className="vswwrap">
            <div className="vsw" data-part="view/switch">
              <button
                aria-pressed={state.libMode === "list"}
                data-lmode="list"
                aria-label={t("screens.library.listLabel")}
              >
                <Icon paths={icons.list} />
              </button>
              <button
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
  const { CATS, libFiltered } = useLibraryReference();
  const total = libFiltered().length;
  const shown = Math.min(state.libCount as number, total);
  const category = CATS.find((entry) => entry.id === state.libCat);
  const universe = category && category.of ? category.c : 1861;
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
  const { CATS } = useLibraryReference();
  const category = CATS.find((entry) => entry.id === state.libCat);
  const filter = category && category.of ? category.l.toLowerCase() : null;
  if ((state.q as string).trim() !== "") {
    return (
      <div className="empty" data-part="empty-state">
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
    <div className="empty" data-part="empty-state">
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
  const {
    libFiltered,
    libRowHTML,
    tileHTML,
    surfErrInner,
    paintSelBar,
    libraryLoaded,
    LIB_PAGE,
  } = useLibraryReference();
  const footRef = useRef<HTMLDivElement | null>(null);
  const grid = state.libMode === "grid";
  const rows = libFiltered();
  const count = state.libCount as number;
  const complete = count >= rows.length;

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

  // ONE PAGE MORE, asked for by the sentinel coming into view. The delay, the
  // single simulated failure and the page size are the legacy's own: this is
  // the same function, moved, not a new one.
  // IT READS THE LIVE STATE, never this render's snapshot, and that is a
  // correctness fix rather than a style: the legacy read the engine's alias,
  // which is always current. A closure over `state` freezes `libErr` at the
  // value the footer was drawn with — so « Réessayer », which clears the error
  // on the line above, is refused by the guard on the line below, every time.
  // The same closure froze `libCount`: a search or a sort that resets it to one
  // page while the 620 ms timer is in flight would then be overwritten with the
  // OLD count plus a page, jumping the list past what the count line promised.
  const loadMore = () => {
    const live = () => window.__store.read().state;
    if (live().libLoading || live().libErr) return;
    if ((live().libCount as number) >= libFiltered().length) return;
    // WHAT THE LOAD WAS ASKED FROM. Six hundred and twenty milliseconds is long
    // enough for the page to have moved on — a search, a sort, another lens,
    // all of which put the count back to one page — and a load that lands after
    // that would extend a list nobody asked to extend, from a number that no
    // longer exists. So the page it was asked from is remembered, and a landing
    // that does not recognise it does nothing. Measured: a state that draws a
    // skeleton starts a load, and 620 ms later it landed on the NEXT state,
    // which then drew two pages where it had asked for one.
    const asked = live().libCount as number;
    writeUiState({ libLoading: true });
    // THE STORE'S OWN VERSION is the identity, not the count: two different
    // states can both sit at one page, and « the count is what it was » would
    // then let a stale load through. Every write bumps the version, so anything
    // that happened while this load was in flight — a search, a sort, a lens,
    // another state driven by the harness — makes it stale by definition.
    const askedAt = window.__store.read().version;
    window.setTimeout(() => {
      if (window.__store.read().version !== askedAt) return;
      writeUiState({ libLoading: false });
      if (!live().libFailedOnce && asked >= LIB_PAGE * 3) {
        writeUiState({ libFailedOnce: true, libErr: true });
        return;
      }
      writeUiState({
        libCount: Math.min(libFiltered().length, asked + LIB_PAGE),
      });
    }, 620);
  };

  useEffect(() => {
    const foot = footRef.current;
    const port = document.querySelector("#port");
    if (!foot || !port || complete || state.libErr) return undefined;
    // NOT WHILE A PAGE IS IN FLIGHT: `loadMoreLib` disconnected the observer
    // for the duration of its own load and reconnected after. The live guard
    // already refuses a second load, but an observer that keeps firing during
    // those 620 ms is a difference in what the page DOES.
    if (state.libLoading) return undefined;
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
      <div id="libitems" className={grid ? "grid" : "sec"} data-part={grid ? "grid" : "section"}>
        {Array.from({ length: grid ? 9 : 5 }, (_, index) => (
          <div key={index} className={grid ? "sk tile" : "sk skcard"} data-skeleton="" data-part={grid ? "tile" : undefined} />
        ))}
      </div>
    );
  } else if (state.phase === "error") {
    items = (
      <div
        id="libitems"
        className={grid ? "grid" : "sec"} data-part={grid ? "grid" : "section"}
        dangerouslySetInnerHTML={{
          __html: `<div class="surferr" data-part="surface-error" role="alert">${surfErrInner(t("screens.library.errorSubject"))}</div>`,
        }}
      />
    );
  } else if (rows.length === 0) {
    items = (
      <div id="libitems" className={grid ? "grid" : "sec"} data-part={grid ? "grid" : "section"}>
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
        className={grid ? "grid" : "sec"} data-part={grid ? "grid" : "section"}
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
        <p className="endmark">
          {t("screens.library.endMark", { count: libraryLoaded() })}
        </p>
      );
    } else if (state.libErr) {
      foot = (
        <div className="loaderr" data-part="load-error">
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
            id="libretry"
            onClick={() => {
              writeUiState({ libErr: false });
              loadMore();
            }}
          >
            {t("screens.library.retry")}
          </button>
        </div>
      );
    } else {
      foot = grid ? (
        <div className="grid" data-part="grid">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="sk tile" data-part="tile" data-skeleton="" />
          ))}
        </div>
      ) : (
        <div className="sec" data-part="section">
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
      <div id="libload" className="loadfoot" ref={footRef}>
        {foot}
      </div>
    </>
  );
}

export function LibraryPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    INCOMPLETE,
    cardHTML,
    tileHTML,
  } = useLibraryReference();

  if (state.libLens === "inc") {
    return (
      <>
        <LibraryHead />
        <div className="countline" data-part="count-line" data-region="library/count-line">
          <span className="pip warning" data-part="status-dot"></span>
          <span>{t("screens.library.incompleteTitle")}</span>
          <b style={{ marginLeft: "auto" }}>{INCOMPLETE_COUNT}</b>
        </div>
        <div className="body" data-part="surface/body" data-region="library/body">
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
              className="grid" data-part="grid"
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
              className="sec" data-part="section"
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
        <div className="countline" data-part="count-line" data-region="library/count-line">
          <span>{t("screens.library.recentTitle")}</span>
        </div>
        <div className="body" data-part="surface/body" data-region="library/body">
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
      <div className="countline" data-part="count-line" data-region="library/count-line">
        <CountLine />
        <button className="linkbtn" data-selmode="1">
          {t("screens.library.select")}
        </button>
        <button style={{ marginLeft: 12 }} data-sort="1">
          <SortLabel />
        </button>
      </div>
      <div className="body" data-part="surface/body" data-region="library/body">
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
