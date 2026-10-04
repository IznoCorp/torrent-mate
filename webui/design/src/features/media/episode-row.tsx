// One episode's row in a media sheet's season: its state dot, its number, its
// title and its date — the season list's row, in a file of its own so the list
// stays under the 400-line ceiling (invariant 6).
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { statusDot } from "../../ui/variants";
import { episodeDate, episodeNumber, episodeRow, episodeTitle, type EpisodeState } from "./variants";
import { EPISODE_DOT } from "./episode-legend";
import { dateLabel, episodeStateLabel } from "./format";
import type { SheetEpisode } from "./sheet-fields";

/**
 * An episode's row. SUBTLE state colour: a 6px dot and the number in the
 * tone. The title stays neutral — it is what one reads first, so it keeps
 * maximum contrast. One colour signal per row, not a Christmas tree.
 *
 * @param props.episode The episode, as the sheet lists it.
 * @param props.state Its state, derived by the list from the owned numbers.
 * @returns The row.
 */
export function EpisodeRow({ episode, state }: { episode: SheetEpisode; state: EpisodeState }): ReactElement {
  const { t } = useTranslation();
  return (
    // Same blanks as the season summary, same reason: the row is
    // a flex container (they draw nothing) and its `textContent`
    // is read as one sentence.
    <div
      className={episodeRow({ state })}
      data-part="episode/row"
      data-state={state}
      data-announced={state === "announced" || undefined}
      data-in-library={state === "in_library" || undefined}
    >
      <span className={statusDot({ tone: EPISODE_DOT[state] })} data-part="status-dot"></span>{" "}
      <span className={episodeNumber({ state })} data-part="episode/number">
        E{String(episode.number).padStart(2, "0")}
      </span>{" "}
      <span className={episodeTitle()}>{episode.title}</span>{" "}
      <span className={episodeDate()}>
        {episode.airDate ? dateLabel(episode.airDate) : t("screens.media.dateUnknown")}
        {state === "in_library" ? "" : ` · ${episodeStateLabel(state).toLowerCase()}`}
      </span>
    </div>
  );
}
