import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { SurfaceError } from "../../ui/state-surfaces";
import { useAcquisitionReference, type Follow } from "./reference";
import { useFollows } from "./queries";
import { useUiState } from "../../lib/store-access";
import { FollowsFilters } from "./follows-filters";
import { body, emptyNote, section as sectionClass, sectionCount, sectionTitle } from "../../ui/variants";

// The swipe action a follow that can be searched again reveals. It is a
// data-ATTRIBUTE VALUE the document-level delegation dispatches on — a contract
// with the engine, not copy; the label beside it is the copy, from `fr.json`.
const SEARCH_AGAIN = "chercher"; // french-ok: a data-attribute value, a contract

// « Suivis » — what one has asked the machine to watch. Three display modes
// (list, grouped, grid), a filter that ignores case and accents, and four
// pills. The page says out loud, in its own note, that the cadence is printed
// as the scheduler returns it — a raw cron expression on a phone card, which
// it names as the defect it is rather than hiding.
export function FollowsTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    icons,
    cardHTML,
    tileHTML,
    swipeHTML,
    skelCardsInner,
    emptyInner,
    svgIcon,
    stFraction,
    stLabel,
    gridBadge,
    cadenceFR,
    nextSearchFR,
    escapeHtml,
    ST_TONE,
    URGENCY,
    GROUPS,
    CADENCE_CRON,
  } = useAcquisitionReference();

  // FROM THE CACHE (invariant 4). Following, unfollowing and grabbing are
  // mutations the engine's delegation still calls; their conversion is the
  // follows panel's own, and this is the read.
  const { data: follows = [] } = useFollows();
  const pills = [
    { id: "tout", label: t("screens.acquisition.pillAll"), count: follows.length },
    {
      id: "series",
      label: t("screens.acquisition.pillSeries"),
      count: follows.filter((follow) => follow.k !== "movie").length,
    },
    {
      id: "movies",
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
    (state.pill === "movies" && follow.k === "movie") ||
    (state.pill === "pause" && follow.st === "disabled");
  const term = (state.filter as string).trim().toLocaleLowerCase();
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
  const next = nextSearchFR(CADENCE_CRON, new Date());

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
      follow.st === "pending"
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
        follow.since
          ? t("screens.acquisition.followedSince") + follow.since
          : null,
        // Zero is a fact worth printing: a follow added and never searched is
        // exactly what one wants to spot.
        follow.searches != null
          ? t(
              follow.searches > 1
                ? "screens.acquisition.searchesMany"
                : "screens.acquisition.searchesOne",
              { count: follow.searches },
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
        ? `<button class="act pause" data-part="swipe/action" data-action="pause" data-swipeact="pause">${svgIcon(icons.x)}${t("screens.acquisition.swipeStopSearching")}</button><button class="act remove" data-part="swipe/action" data-action="remove" data-swipeact="remove">${svgIcon(icons.trash)}${t("screens.acquisition.swipeRemove")}</button>`
        : `<button class="act pause" data-part="swipe/action" data-action="pause" data-swipeact="pause">${svgIcon(icons.x)}${t("screens.acquisition.swipePause")}</button><button class="act remove" data-part="swipe/action" data-action="remove" data-swipeact="remove">${svgIcon(icons.trash)}${t("screens.acquisition.swipeRemove")}</button>`,
      follow.st === "pending" || follow.st === "to_grab"
        ? `<button class="act resume" data-part="swipe/action" data-action="resume" data-swipeact="${SEARCH_AGAIN}">${svgIcon(icons.refresh)}${t("screens.acquisition.swipeSearch")}</button>`
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
  // complete element here — a `.sec`, a `.gallery`, an `.empty`, a skeleton or an
  // error surface — and React cannot inject markup without a host, so the host
  // IS that element rather than a wrapper around it.
  let content: ReactElement;
  if (state.phase === "loading") {
    content = (
      <div
        className={sectionClass()} data-part="section"
        dangerouslySetInnerHTML={{ __html: skelCardsInner(5) }}
      />
    );
  } else if (state.phase === "error") {
    content = (
      <SurfaceError subject={t("screens.acquisition.errorFollows")} />
    );
  } else if (visible.length === 0) {
    content = (
      <div
        className={emptyNote()} data-part="empty-state"
        dangerouslySetInnerHTML={{ __html: emptyInner(
      term !== ""
        ? t("screens.acquisition.emptyFilter", {
            // ESCAPED, because this string is injected as HTML: i18next
            // interpolates without escaping — right for a React text node,
            // wrong here — and the legacy escaped it at exactly this spot.
            term: escapeHtml(state.filter as string),
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
        className="gallery" data-part="grid"
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
              className={sectionClass()} data-part="section"
              dangerouslySetInnerHTML={{
                __html: `
            <div class="sechead" data-part="section/head"><span class="pip ${group.pip}" data-part="status-dot"></span><span class="${sectionTitle()}" data-part="section/title">${group.l}</span><span class="${sectionCount()}" data-part="section/count">${items.length}</span></div>
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
        className={sectionClass()} data-part="section"
        dangerouslySetInnerHTML={{
          __html: visible.map((follow) => rowOf(follow, true)).join(""),
        }}
      />
    );
  }

  return (
    <>
      <FollowsFilters pills={pills} />
      <p className="cadence" data-part="cadence">{cadenceFR(CADENCE_CRON)}</p>
      <div className={body()} data-part="surface/body" data-region="acquisition/body">
        <div className="note" data-part="note">
          <b>{t("screens.acquisition.followsNoteLead")}</b>
          {t("screens.acquisition.followsNoteRest")}
        </div>
        <div className="note" data-part="note">
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
