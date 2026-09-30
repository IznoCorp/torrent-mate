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
import { codesOf, legendOf, owedBy, torrentItemMarkup } from "./torrent-card";
import { Legend } from "../../ui/legend";

/**
 * The « Torrents » tab.
 *
 * THE FILTER IS READ HERE, on the list both reads answered: filtered or not,
 * the page asks the server the same thing. The selector above the page's body
 * SAYS it; the list only obeys it.
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
  if (entries.length === 0) {
    // TWO SENTENCES, never one: nothing anywhere is not nothing on this tracker.
    const [title, body] = tracker === ""
      ? [t("screens.torrents.empty"), t("screens.torrents.emptyBody")]
      : [t("screens.torrents.emptyFiltered"), t("screens.torrents.emptyFilteredBody")];
    return (
      <Markup className={emptyNote()} data-part="empty-state" html={emptyNoteMarkup(title, body)} />
    );
  }
  const breachedOf = (entry: (typeof entries)[number]) => alert.breached.has(`${entry.infoHash}:${entry.tracker}`);
  // THE PAIR'S OWN TRACKER SWITCH (§ 17 point 1): the summary this tab already reads.
  const trackerEnabled = (name: string) => (trackers ?? []).find((one) => one.name === name)?.crossSeed.enabled ?? true;
  // THE LEGEND READS THE CODES THE CARDS DRAW, only those present on the list shown.
  const codes = entries.flatMap((entry) => codesOf(entry, owedBy(entry, obligations.items), breachedOf(entry)));
  return (
    <>
      <Legend entries={legendOf(codes)} />
      {/* ONE CARD PER ENTRY, each in its swipe row: the media card's anatomy and taps. */}
      <Markup
        className={section()} data-part="torrents"
        html={entries.map((entry) => torrentItemMarkup(
          entry, owedBy(entry, obligations.items), breachedOf(entry), trackerEnabled,
        )).join("")}
      />
    </>
  );
}
