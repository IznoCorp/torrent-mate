// design/src/pages/acquisition.tsx
// The largest migrated PAGE: legacy `viewAcquisition()`
// (290 lines, three tabs) reborn as a final component. Markup is TRANSPLANTED,
// not translated.
//
// Acquisition is where one asks for media and watches the asking: what is
// waiting, what one follows, and what one might want. The three tabs are three
// different surfaces sharing one bar, which is why they are three functions
// here rather than one with branches.
//
// WHAT THIS COMPONENT DRAWS AND NEVER FILLS: `#sugitems`, `#sugload` and the
// deck's `.deckbody`. The suggestion machinery stays the fragment's, and that
// is a measured decision rather than an unfinished one — `avancerDeck` mutates
// the deck's own DOM in place (it inserts a card at the back, decrements every
// `data-depth`, writes an inline transform on the outgoing one and removes it
// 440 ms later), and its own comment says why: a replaced node cannot animate.
// React owning that markup would restore the string it last rendered on the
// next repaint and undo the gesture four rules measure. So the containers are
// React's and their CONTENT is the fragment's: React manages zero children
// there, so neither world removes the other's nodes — the arrangement
// `paintSelBar` already has, one level down.
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../components/icon";
import type { Follow, QueueCard } from "../data";
import {
  useReference,
  useStoreContent,
  useUiState,
  writeUiState,
} from "../data";

// The swipe action a follow that can be searched again reveals. It is a
// data-ATTRIBUTE VALUE the document-level delegation dispatches on — a contract
// with the engine, not copy; the label beside it is the copy, from `fr.json`.
const SEARCH_AGAIN = "chercher"; // french-ok: a data-attribute value, a contract

// The tab bar, and the « more » control that opens the watch-and-obligations
// sheet. Shared by the three surfaces below.
function AcquisitionTabs(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons, derivedTakeable, derivedBlocked } = useReference();
  const tabs = [
    {
      id: "maintenant",
      label: t("screens.acquisition.tabNow"),
      count: derivedTakeable().length + derivedBlocked().length,
    },
    { id: "suivis", label: t("screens.acquisition.tabFollows") },
    { id: "decouvrir", label: t("screens.acquisition.tabDiscover") },
  ];
  return (
    <div className="viewtabs">
      <div className="seg" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={state.acqTab === tab.id}
            data-acqtab={tab.id}
          >
            {tab.label}
            {tab.count ? <span className="n">{tab.count}</span> : null}
          </button>
        ))}
      </div>
      <button
        className="more"
        aria-label={t("screens.acquisition.moreLabel")}
        data-sheet="plus"
      >
        <Icon paths={icons.more} />
      </button>
    </div>
  );
}

// « En cours » — five sections of urgency, one coloured pip each, and a counter
// that IS its own link. The page's own note calls this the language reference
// for the three other pages.
function NowTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    cardHTML,
    secInner,
    emptyInner,
    skelCardsInner,
    surfErrInner,
    derivedTakeable,
    derivedBlocked,
    derivedInflight,
    derivedNotfound,
    derivedDoneToday,
    derivedStuck,
  } = useReference();

  if (state.phase !== "prete") {
    return (
      <div className="body">
        {state.phase === "erreur" ? (
          <div
            className="surferr"
            dangerouslySetInnerHTML={{
              __html: surfErrInner(t("screens.acquisition.errorNow")),
            }}
          />
        ) : (
          <div
            className="sec"
            dangerouslySetInnerHTML={{ __html: skelCardsInner(4) }}
          />
        )}
      </div>
    );
  }

  const takeable = derivedTakeable();
  const blocked = derivedBlocked();
  const inflight = derivedInflight();
  const notfound = derivedNotfound();
  const doneToday = derivedDoneToday();
  const stuck = derivedStuck();
  const nothing =
    takeable.length +
      blocked.length +
      inflight.length +
      notfound.length +
      doneToday.length ===
    0;

  const section = (
    pip: string,
    title: string,
    cards: QueueCard[],
    inner: string,
    note?: string,
  ) =>
    cards.length === 0 || inner === "" ? null : (
      <section
        className="sec"
        dangerouslySetInnerHTML={{
          __html: secInner(pip, title, String(cards.length), inner, note),
        }}
      />
    );

  return (
    <div className="body">
      <div className="note">
        <b>{t("screens.acquisition.nowNoteLead")}</b>
        {t("screens.acquisition.nowNoteRest")}
      </div>
      {nothing ? (
        <div
          className="empty"
          dangerouslySetInnerHTML={{
            __html: emptyInner(
              t("screens.acquisition.nowEmptyTitle"),
              `${t("screens.acquisition.nowEmptyBodyBefore")}<b>${t("screens.acquisition.nowEmptyBodyCount")}</b>${t("screens.acquisition.nowEmptyBodyAfter")}`,
            ),
          }}
        />
      ) : null}
      {section(
        "warning",
        t("screens.acquisition.takeable"),
        takeable,
        takeable
          .map((card) =>
            cardHTML(card, {
              foot: t("screens.acquisition.takeableFoot"),
              footSolid: true,
            }),
          )
          .join(""),
      )}
      {section(
        "danger",
        t("screens.acquisition.blocked"),
        blocked,
        blocked
          .map((card) =>
            cardHTML(card, { foot: t("screens.acquisition.blockedFoot") }),
          )
          .join(""),
      )}
      {stuck.length > 0 ? (
        <button className="crossref" data-go="arr">
          {blocked.length > 0
            ? t("screens.acquisition.crossrefFromAcquisition")
            : ""}
          <b>{stuck.length}</b>
          {t("screens.acquisition.crossrefMedium")}
          {stuck.length > 1 ? t("screens.acquisition.crossrefPlural") : ""}
          {t("screens.acquisition.crossrefToTreat")}
          {stuck.length > 1
            ? t("screens.acquisition.crossrefEnteredMany")
            : t("screens.acquisition.crossrefEnteredOne")}
          {t("screens.acquisition.crossrefWithoutFollow")}
          <span>{t("screens.acquisition.crossrefLink")}</span>
        </button>
      ) : null}
      {section(
        "info",
        t("screens.acquisition.inflight"),
        inflight,
        inflight.map((card) => cardHTML(card)).join(""),
      )}
      {section(
        "waiting",
        t("screens.acquisition.notfound"),
        notfound,
        notfound.map((card) => cardHTML(card)).join(""),
        `<b>${t("screens.acquisition.notfoundNoteLead")}</b>${t("screens.acquisition.notfoundNoteRest")}`,
      )}
      {section(
        "success",
        t("screens.acquisition.doneToday"),
        doneToday,
        doneToday.map((card) => cardHTML(card)).join(""),
      )}
    </div>
  );
}

// « Suivis » — what one has asked the machine to watch. Three display modes
// (list, grouped, grid), a filter that ignores case and accents, and four
// pills. The page says out loud, in its own note, that the cadence is printed
// as the scheduler returns it — a raw cron expression on a phone card, which
// it names as the defect it is rather than hiding.
function FollowsTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    icons,
    cardHTML,
    tileHTML,
    swipeHTML,
    skelCardsInner,
    surfErrInner,
    emptyInner,
    svgIcon,
    stFraction,
    stLabel,
    gridBadge,
    cadenceFR,
    prochaineRechercheFR,
    escapeHtml,
    render,
    ST_TONE,
    URGENCY,
    GROUPS,
    CADENCE_CRON,
    derivedFollows,
  } = useReference();

  const follows = derivedFollows();
  const pills = [
    { id: "tout", label: t("screens.acquisition.pillAll"), count: follows.length },
    {
      id: "series",
      label: t("screens.acquisition.pillSeries"),
      count: follows.filter((follow) => follow.k !== "movie").length,
    },
    {
      id: "films",
      label: t("screens.acquisition.pillMovies"),
      count: follows.filter((follow) => follow.k === "movie").length,
    },
    {
      id: "pause",
      label: t("screens.acquisition.pillPaused"),
      count: follows.filter((follow) => follow.st === "disabled").length,
    },
  ];

  const matches = (follow: Follow) =>
    state.pill === "tout" ||
    (state.pill === "series" && follow.k !== "movie") ||
    (state.pill === "films" && follow.k === "movie") ||
    (state.pill === "pause" && follow.st === "disabled");
  const term = (state.filtre as string).trim().toLocaleLowerCase();
  const normalise = (text: string) =>
    text
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase();
  const matchesName = (follow: Follow) =>
    term === "" || normalise(follow.t).includes(normalise(term));
  const visible = follows
    .filter((follow) => matches(follow) && matchesName(follow))
    .sort(
      (left, right) =>
        (left.fresh ? 0 : 1) - (right.fresh ? 0 : 1) ||
        URGENCY[left.st] - URGENCY[right.st] ||
        left.t.localeCompare(right.t, "fr"),
    );

  // Read ONCE for the whole list: every card names the same next slot.
  const next = prochaineRechercheFR(CADENCE_CRON, new Date());

  const seriesState = (follow: Follow) =>
    follow.k === "movie"
      ? null
      : follow.serie === "Continuing"
        ? t("screens.acquisition.seriesOngoing")
        : follow.serie === "Ended"
          ? t("screens.acquisition.seriesEnded")
          : null;

  const descriptorOf = (follow: Follow, showStatus: boolean) => ({
    t: follow.t,
    k: follow.k,
    s: [
      String(follow.y),
      follow.k === "movie"
        ? t("screens.acquisition.movie")
        : t("screens.acquisition.series"),
      seriesState(follow),
    ]
      .filter(Boolean)
      .join(" · "),
    r:
      follow.st === "en_attente"
        ? [
            t("screens.acquisition.noConformRelease"),
            next ? t("screens.acquisition.nextSearch", { at: next }) : null,
          ]
            .filter(Boolean)
            .join(" ")
        : undefined,
    f: stFraction(follow) ?? undefined,
    chip: showStatus
      ? ([ST_TONE[follow.st], stLabel(follow)] as [string, string])
      : undefined,
    caption:
      [
        follow.depuis
          ? t("screens.acquisition.followedSince") + follow.depuis
          : null,
        // Zero is a fact worth printing: a follow added and never searched is
        // exactly what one wants to spot.
        follow.recherches != null
          ? t(
              follow.recherches > 1
                ? "screens.acquisition.searchesMany"
                : "screens.acquisition.searchesOne",
              { count: follow.recherches },
            )
          : null,
      ]
        .filter(Boolean)
        .join(" · ") || undefined,
  });

  const rowOf = (follow: Follow, showStatus: boolean) =>
    swipeHTML(
      cardHTML(descriptorOf(follow, showStatus)),
      follow.k === "movie"
        ? `<button class="act pause" data-swipeact="pause">${svgIcon(icons.x)}${t("screens.acquisition.swipeStopSearching")}</button><button class="act remove" data-swipeact="remove">${svgIcon(icons.trash)}${t("screens.acquisition.swipeRemove")}</button>`
        : `<button class="act pause" data-swipeact="pause">${svgIcon(icons.x)}${t("screens.acquisition.swipePause")}</button><button class="act remove" data-swipeact="remove">${svgIcon(icons.trash)}${t("screens.acquisition.swipeRemove")}</button>`,
      follow.st === "en_attente" || follow.st === "a_recuperer"
        ? `<button class="act resume" data-swipeact="${SEARCH_AGAIN}">${svgIcon(icons.refresh)}${t("screens.acquisition.swipeSearch")}</button>`
        : "",
    );

  const tileOf = (follow: Follow) =>
    tileHTML(
      follow,
      stFraction(follow) ??
        (follow.st === "disabled"
          ? t("screens.acquisition.paused")
          : String(follow.y)),
      { muted: follow.st === "disabled", badge: gridBadge(follow) },
    );

  // EACH BRANCH DRAWS ITS OWN CONTAINER and fills it. The legacy interpolated a
  // complete element here — a `.sec`, a `.grid`, an `.empty`, a skeleton or an
  // error surface — and React cannot inject markup without a host, so the host
  // IS that element rather than a wrapper around it.
  let content: ReactElement;
  if (state.phase === "chargement") {
    content = (
      <div
        className="sec"
        dangerouslySetInnerHTML={{ __html: skelCardsInner(5) }}
      />
    );
  } else if (state.phase === "erreur") {
    content = (
      <div
        className="surferr"
        dangerouslySetInnerHTML={{
          __html: surfErrInner(t("screens.acquisition.errorFollows")),
        }}
      />
    );
  } else if (visible.length === 0) {
    content = (
      <div
        className="empty"
        dangerouslySetInnerHTML={{ __html: emptyInner(
      term !== ""
        ? t("screens.acquisition.emptyFilter", {
            // ESCAPED, because this string is injected as HTML: i18next
            // interpolates without escaping — right for a React text node,
            // wrong here — and the legacy escaped it at exactly this spot.
            term: escapeHtml(state.filtre as string),
          })
        : state.pill === "pause"
          ? t("screens.acquisition.emptyPaused")
          : t("screens.acquisition.emptyNoFollows"),
      term !== ""
        ? `${t("screens.acquisition.emptyFilterBodyBefore")}<b>${follows.length}</b>${t("screens.acquisition.emptyFilterBodyAfter")}`
        : state.pill === "pause"
          ? t("screens.acquisition.emptyPausedBody")
          : `${t("screens.acquisition.emptyNoFollowsBodyBefore")}<b>${t("screens.acquisition.emptyNoFollowsBodyPlus")}</b>${t("screens.acquisition.emptyNoFollowsBodyAfter")}`,
        ) }}
      />
    );
  } else if (state.followMode === "grid") {
    content = (
      <div
        className="grid"
        dangerouslySetInnerHTML={{ __html: visible.map(tileOf).join("") }}
      />
    );
  } else if (state.followMode === "group") {
    content = (
      <>
        {GROUPS.map((group) => {
          const items = visible.filter((follow) =>
            group.of.includes(follow.st),
          );
          if (items.length === 0) return null;
          // A heterogeneous group KEEPS the chip on its cards: its header
          // cannot say which of its three values each card carries.
          const showStatus = group.of.length > 1;
          return (
            <section
              key={group.l}
              className="sec"
              dangerouslySetInnerHTML={{
                __html: `
            <div class="sechead"><span class="pip ${group.pip}"></span><span class="t">${group.l}</span><span class="k">${items.length}</span></div>
            ${items.map((item) => rowOf(item, showStatus)).join("")}
          `,
              }}
            />
          );
        })}
      </>
    );
  } else {
    content = (
      <div
        className="sec"
        dangerouslySetInnerHTML={{
          __html: visible.map((follow) => rowOf(follow, true)).join(""),
        }}
      />
    );
  }

  return (
    <>
      <div className="filters">
        <div className="search">
          <Icon paths={icons.search} />
          <input
            // UNCONTROLLED, with its own native handler — the arrangement
            // `#libq` has, for the same reason: `mountSearch` bound this field
            // from outside, and it runs inside `render()`, BEFORE React has put
            // the field in the document. Typing did nothing until some other
            // control forced a second render.
            type="search"
            id="follq"
            defaultValue={state.filtre as string}
            placeholder={t("screens.acquisition.filterPlaceholder")}
            aria-label={t("screens.acquisition.filterLabel")}
            ref={(element) => {
              if (!element) return;
              // What changes the filter from OUTSIDE — the clear cross — has to
              // reach the field, and only when the two differ, so nothing
              // touches the node mid-word. The ATTRIBUTE follows too: the
              // legacy re-emitted it on every draw.
              const filter = state.filtre as string;
              if (element.value !== filter) element.value = filter;
              if (element.getAttribute("value") !== filter)
                element.setAttribute("value", filter);
              const commit = () => {
                writeUiState({ filtre: element.value });
                render();
              };
              element.addEventListener("input", commit);
              return () => element.removeEventListener("input", commit);
            }}
          />
          {state.filtre ? (
            <button
              className="searchclear"
              data-clearq="foll"
              aria-label={t("screens.acquisition.clearLabel")}
            >
              <Icon paths={icons.x} />
            </button>
          ) : null}
        </div>
        <div className="pillbar">
          <div className="pillscroll">
            {pills.map((pill) => (
              <button
                key={pill.id}
                className="pill"
                aria-pressed={state.pill === pill.id}
                data-pill={pill.id}
              >
                {pill.label}
                <span className="c">{pill.count}</span>
              </button>
            ))}
          </div>
          <div className="vswwrap">
            <div className="vsw">
              <button
                aria-pressed={state.followMode === "list"}
                data-fmode="list"
                aria-label={t("screens.acquisition.modeList")}
              >
                <Icon paths={icons.list} />
              </button>
              <button
                aria-pressed={state.followMode === "group"}
                data-fmode="group"
                aria-label={t("screens.acquisition.modeGroup")}
              >
                <Icon paths={icons.group} />
              </button>
              <button
                aria-pressed={state.followMode === "grid"}
                data-fmode="grid"
                aria-label={t("screens.acquisition.modeGrid")}
              >
                <Icon paths={icons.grid} />
              </button>
            </div>
          </div>
        </div>
      </div>
      <p className="cadence">{cadenceFR(CADENCE_CRON)}</p>
      <div className="body">
        <div className="note">
          <b>{t("screens.acquisition.followsNoteLead")}</b>
          {t("screens.acquisition.followsNoteRest")}
        </div>
        <div className="note">
          <b>{t("screens.acquisition.cadenceNoteLead")}</b>
          {t("screens.acquisition.cadenceNoteBefore")}
          <code>{t("screens.acquisition.cadenceNoteInner")}</code>
          {t("screens.acquisition.cadenceNoteAfter")}
        </div>
        {content}
      </div>
    </>
  );
}

// « Découvrir » — what one might want, which is the only surface here that
// asks nothing of the operator: the bar's badge never counts it.
//
// THE CONTAINERS ARE DRAWN HERE AND FILLED BY THE FRAGMENT. `#sugitems`,
// `#sugload` and the deck's `.deckbody` keep their content from `fillSug` /
// `sugFoot` / `refreshDeck`, because the deck's gesture mutates its own DOM in
// place and a replaced node cannot animate. React renders zero children into
// them, so neither world removes the other's nodes.
function DiscoverTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    icons,
    skelCardsInner,
    surfErrInner,
    fillSug,
    sugFoot,
    mountDeck,
    deckHTML,
  } = useReference();

  // THE FRAGMENT FILLS WHAT THIS DRAWS, and it has to be asked AFTER the
  // drawing: `render()` calls the same verbs, but it calls them before React
  // has put the containers in the document, so they find nothing. The deck at
  // rest is filled the same way — its markup was part of the page's own HTML
  // in the legacy, and it is written into the body here.
  useEffect(() => {
    const deckBody = document.querySelector(".deckbody");
    if (state.sugMode === "deck" && state.phase === "prete" && deckBody) {
      // ONLY IF THE PILE IS NOT ALREADY THERE. Rewriting it on every commit
      // destroys the gesture in flight: « Passer » writes the order to the
      // store, which re-renders this component, whose effect would then replace
      // the very nodes `avancerDeck` is animating — and a replaced node cannot
      // animate, which is the whole reason this machinery stayed imperative.
      // Rebuilding a spent pile is `refreshDeck`'s business, and it does it.
      if (!deckBody.querySelector(".deck")) {
        deckBody.innerHTML = deckHTML();
        mountDeck();
      }
      return;
    }
    // AND WHAT THE LEGACY CLEARED BY REWRITING. The deck at rest is written
    // into the body by the line above, and React does not know that node: it
    // was not rendered, so a re-render leaves it in place — the pile stayed at
    // the top of the page under every other state, measured. The legacy got
    // this for free by rewriting `#view` wholesale; here it is said out loud.
    for (const stale of document.querySelectorAll(".body > .deck")) {
      stale.remove();
    }
    if (document.querySelector("#sugitems")) {
      fillSug();
      sugFoot();
    }
  });
  const modes = [
    ["list", icons.list, t("screens.acquisition.modeList")],
    ["poster", icons.grid, t("screens.acquisition.modePosters")],
    ["deck", icons.cards, t("screens.acquisition.modeDeck")],
  ] as const;

  const selector = (
    <div className="filters">
      <div className="pillbar">
        <div className="pillscroll"></div>
        <div className="vswwrap">
          <div className="vsw">
            {modes.map(([id, paths, label]) => (
              <button
                key={id}
                aria-pressed={state.sugMode === id}
                data-sugmode={id}
                aria-label={label}
              >
                <Icon paths={paths} />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // The deck at rest is the whole body: no notes, no containers, just the pile
  // the fragment fills.
  if (state.sugMode === "deck" && state.phase === "prete") {
    return (
      <>
        {selector}
        <div className="body deckbody"></div>
      </>
    );
  }

  return (
    <>
      {selector}
      <div
        className={`body${state.sugMode === "deck" ? " deckbody" : ""}`}
      >
        <div className="note">
          <b>{t("screens.acquisition.discoverNoteLead")}</b>
          {t("screens.acquisition.discoverNoteRest")}
        </div>
        {state.tmdb ? (
          <div className="live">
            <span className="d"></span>
            <span>
              {t("screens.acquisition.liveBefore")}
              <b>{t("screens.acquisition.liveSuggestions")}</b>
              {t("screens.acquisition.liveMiddle")}
              <b>{t("screens.acquisition.liveOwned")}</b>
              {t("screens.acquisition.liveAfter")}
            </span>
          </div>
        ) : (
          <div
            className="surferr"
            style={{
              borderColor:
                "color-mix(in oklab,var(--warning) 45%,transparent)",
              background: "color-mix(in oklab,var(--warning) 8%,transparent)",
            }}
          >
            <b style={{ color: "var(--warning)" }}>
              {t("screens.acquisition.tmdbDisconnected")}
            </b>
            {t("screens.acquisition.tmdbBefore")}
            <b>{t("screens.acquisition.tmdbNotes")}</b>
            {t("screens.acquisition.tmdbMiddle")}
            <br />
            <br />
            {t("screens.acquisition.tmdbAfterBreaks")}
            <b>{t("screens.acquisition.tmdbSimilar")}</b>
            {t("screens.acquisition.tmdbEnd")}
            <button data-tmdb="1">
              {t("screens.acquisition.connectTmdb")}
            </button>
          </div>
        )}
        <div className="note">
          <b>{t("screens.acquisition.callsNoteLead")}</b>
          {t("screens.acquisition.callsNoteBefore")}
          <b>{t("screens.acquisition.callsNoteInner")}</b>
          {t("screens.acquisition.callsNoteAfter")}
        </div>
        <div className="note">
          <b>{t("screens.acquisition.gesturesNoteLead")}</b>
          {t("screens.acquisition.gesturesNoteBefore")}
          <em>{t("screens.acquisition.gesturesNoteInner")}</em>
          {t("screens.acquisition.gesturesNoteAfter")}
        </div>
        {state.phase === "chargement" ? (
          <div
            className="sec"
            dangerouslySetInnerHTML={{ __html: skelCardsInner(4) }}
          />
        ) : state.phase === "erreur" ? (
          <div
            className="surferr"
            dangerouslySetInnerHTML={{
              __html: surfErrInner(t("screens.acquisition.errorSuggestions")),
            }}
          />
        ) : null}
        {/* FILLED BY THE FRAGMENT, never by React — see this file's header. */}
        <div id="sugitems" hidden={state.phase !== "prete"}></div>
        <div
          id="sugload"
          className="loadfoot"
          hidden={state.phase !== "prete" || state.sugMode === "deck"}
        ></div>
        <div className="note">
          <b>{t("screens.acquisition.tmdbMissingNoteLead")}</b>
          {t("screens.acquisition.tmdbMissingNoteRest")}
        </div>
      </div>
    </>
  );
}

export function AcquisitionPage(): ReactElement | null {
  const state = useUiState();
  // THE WORLD IS MUTATED IN PLACE by every action this page offers — grabbing a
  // medium splices it out of one list and unshifts it into another, pausing a
  // follow writes its status — and those actions signal with `toucher()`, which
  // bumps the store's VERSION and leaves `etat` identical. Subscribing to the
  // state alone leaves React bailing out: measured, « Récupérer maintenant »
  // moved the medium and left every counter on screen unchanged. The two other
  // pages that read mutable data subscribe the same way, for the same reason.
  useStoreContent((content) => content.version);
  if (state.acqTab === "maintenant") {
    return (
      <>
        <AcquisitionTabs />
        <NowTab />
      </>
    );
  }
  if (state.acqTab === "suivis") {
    return (
      <>
        <AcquisitionTabs />
        <FollowsTab />
      </>
    );
  }
  return (
    <>
      <AcquisitionTabs />
      <DiscoverTab />
    </>
  );
}
