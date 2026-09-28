// The « Torrents » tab: every entry the download client runs, once per tracker.
//
// ONE ROW PER ENTRY, never folded: a torrent cross-seeded onto two trackers is
// two rows, each with ITS OWN ratio on ITS tracker — the ratio the answer
// carries, computed on the torrent's own size, never on the tracker's download
// volume (§ 18, NE-DOIT-PAS-1). The obligation an entry owes is a MARK on its
// own row, never a second list.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { chip, factDetail, factList, factRow, factRowBody, factValue, statusDot } from "../../ui/variants";
import { dayOf, written } from "./format";
import { useDownloads, useObligations, type Download, type Obligation } from "./queries";
import { torrentTitle } from "./variants";

/**
 * The obligation one entry owes on its own tracker.
 *
 * @param entry The download client's entry.
 * @param obligations Every obligation.
 * @returns The obligation, or undefined when the entry owes none.
 */
function owedBy(entry: Download, obligations: Obligation[]): Obligation | undefined {
  return obligations.find(
    (obligation) => obligation.infoHash === entry.infoHash && obligation.sourceTracker === entry.tracker,
  );
}

/**
 * What an entry carries, said after its title: the season and the episode.
 *
 * @param entry The download client's entry.
 * @returns The episode's code, or an empty string for a movie.
 */
function episodeCode(entry: Download): string {
  const twoDigits = (value: number) => String(value).padStart(2, "0");
  if (entry.season === null) return "";
  return entry.episode === null ? `S${twoDigits(entry.season)}` : `S${twoDigits(entry.season)}E${twoDigits(entry.episode)}`;
}

/**
 * One entry's row.
 *
 * @param props.entry The download client's entry.
 * @param props.obligation The obligation it owes, when it owes one.
 * @returns The row.
 */
function TorrentRow({ entry, obligation }: { entry: Download; obligation: Obligation | undefined }): ReactElement {
  const { t } = useTranslation();
  const code = episodeCode(entry);
  // RUNNING: nothing has closed it — neither met, nor broken, nor released.
  const running = obligation !== undefined
    && obligation.satisfiedAt === null && obligation.breachedAt === null && obligation.releasedAt === null;
  // MET AND STILL SEEDING: the entry kept going past its own requirement.
  const done = obligation !== undefined && obligation.satisfiedAt !== null && obligation.releasedAt === null;
  return (
    <li data-part="torrents/row" data-entry={entry.infoHash} data-tracker={entry.tracker}>
      <span className={factRow()}>
        <span
          className={statusDot({ tone: entry.origin ? "info" : "waiting" })}
          data-part="torrents/origin"
          data-origin={entry.origin ? "origin" : "cross"}
          role="img"
          aria-label={t(entry.origin ? "screens.torrents.origin" : "screens.torrents.crossSeed")}
        />
        <span className={factRowBody()}>
          {/* THE TITLE IS A PATH: its sheet, or its resolution when nobody identified it. */}
          <button className={torrentTitle()} data-part="torrents/title" data-mediasheet={entry.title}>
            {code === "" ? entry.title : `${entry.title} · ${code}`}
          </button>
          <span className={factDetail()} data-part="torrents/tracker">{entry.tracker}</span>
          <span className={factDetail()} data-part="torrents/deadline">
            {entry.deadline === null
              ? t("screens.torrents.noDeadline")
              : t("screens.torrents.deadline", { date: dayOf(entry.deadline) })}
          </span>
          {running ? (
            <span className={chip({ tone: "info" })} data-part="torrents/obligation-open">
              {t("screens.torrents.obligationOpen")}
            </span>
          ) : null}
          {done ? (
            <span className={chip({ tone: "success" })} data-part="torrents/obligation-done">
              {t("screens.torrents.obligationDone")}
            </span>
          ) : null}
        </span>
        <span className={factValue()} data-part="torrents/ratio">
          {t("screens.trackers.ratio", { ratio: written(entry.ratio, 2) })}
        </span>
      </span>
    </li>
  );
}

/**
 * The « Torrents » tab.
 *
 * @returns Every entry's row, once both reads have answered.
 */
export function TorrentsTab(): ReactElement | null {
  const { data: downloads } = useDownloads();
  const { data: obligations } = useObligations();
  if (!downloads || !obligations) return null;
  return (
    <ol className={factList()} data-part="torrents">
      {downloads.downloads.map((entry) => (
        <TorrentRow
          key={`${entry.infoHash}:${entry.tracker}`}
          entry={entry}
          obligation={owedBy(entry, obligations.items)}
        />
      ))}
    </ol>
  );
}
