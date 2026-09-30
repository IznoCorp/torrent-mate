// The « Torrents » tab: every entry the download client runs, once per tracker.
//
// ONE CARD PER ENTRY, never folded: a torrent cross-seeded onto two trackers is
// two cards, each with ITS OWN ratio on ITS tracker — the ratio the answer
// carries, computed on the torrent's own size, never on the tracker's download
// volume (§ 18, NE-DOIT-PAS-1). The obligation an entry owes is a MARK on its
// own card, never a second list.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { Markup, emptyNoteMarkup } from "../../ui/markup";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { useUiState } from "../../lib/store-access";
import { emptyNote, section } from "../../ui/variants";
import { alertOf, useDownloads, useObligations, useTrackers } from "./queries";
import { owedBy, torrentItemMarkup } from "./torrent-card";
import { torrentFilter, torrentFilterClear } from "./variants";

/**
 * The line saying which tracker the list is filtered to, and lifting it.
 *
 * « TOUT VOIR » IS THE SAME VERB AS « Voir les torrents », given no tracker: an
 * adjustment of the page, which replaces its address and pushes nothing.
 *
 * @param props.tracker The tracker the list is filtered to.
 * @returns The line.
 */
function FilterLine({ tracker }: { tracker: string }): ReactElement {
  const { t } = useTranslation();
  return (
    <p className={torrentFilter()} data-part="torrents/filter">
      <span>{t("screens.torrents.filtered", { tracker })}</span>
      <button className={torrentFilterClear()} data-part="torrents/filter-clear" data-trackers-filter="">
        {t("screens.torrents.showAll")}
      </button>
    </p>
  );
}

/**
 * The « Torrents » tab.
 *
 * THE FILTER IS READ HERE, on the list both reads answered: filtered or not,
 * the page asks the server the same thing.
 *
 * @returns Every entry's row — the filtered tracker's alone when the dial names
 *     one — or the sentence saying there is none; while the reads are in flight,
 *     their skeletons, and when one failed, the failure.
 */
export function TorrentsTab(): ReactElement {
  const { t } = useTranslation();
  const state = useUiState();
  const downloadsRead = useDownloads();
  const obligationsRead = useObligations();
  const downloads = downloadsRead.data;
  const obligations = obligationsRead.data;
  const { data: trackers } = useTrackers();
  // THE READS IN FLIGHT, OR FAILED, ARE SAID — never an empty tab standing for either.
  if (downloadsRead.isError || obligationsRead.isError) {
    const retry = () => {
      void downloadsRead.refetch();
      void obligationsRead.refetch();
    };
    return <SurfaceError subject={t("screens.torrents.errorSubject")} onRetry={retry} />;
  }
  if (!downloads || !obligations) return <Skeletons count={3} shape="card" />;
  const alert = alertOf(trackers ?? [], downloads.downloads, obligations.items);
  const tracker = typeof state.trackersFilter === "string" ? state.trackersFilter : "";
  const entries = tracker === "" ? downloads.downloads : downloads.downloads.filter((entry) => entry.tracker === tracker);
  const filter = tracker === "" ? null : <FilterLine tracker={tracker} />;
  if (entries.length === 0) {
    // TWO SENTENCES, never one: nothing anywhere is not nothing on this tracker.
    const [title, body] = tracker === ""
      ? [t("screens.torrents.empty"), t("screens.torrents.emptyBody")]
      : [t("screens.torrents.emptyFiltered"), t("screens.torrents.emptyFilteredBody")];
    return (
      <>
        {filter}
        <Markup className={emptyNote()} data-part="empty-state" html={emptyNoteMarkup(title, body)} />
      </>
    );
  }
  return (
    <>
      {filter}
      {/* ONE CARD PER ENTRY, each in its swipe row: the media card's anatomy and taps. */}
      <Markup
        className={section()} data-part="torrents"
        html={entries.map((entry) => torrentItemMarkup(
          entry, owedBy(entry, obligations.items), alert.breached.has(`${entry.infoHash}:${entry.tracker}`),
        )).join("")}
      />
    </>
  );
}
