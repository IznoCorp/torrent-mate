// « Demandée » on a season's row — ONE drawing, for the media sheet's season
// list and the follow panel's seasons, so the two surfaces cannot drift apart.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { chip } from "../../ui/variants";

/**
 * The mark of a season whose whole recovery is live: the info chip, the same
 * the release picker's refusal wears. An automatic recovery says « auto »
 * INSIDE the one chip (Q19; DECIDED 4: never a second chip on the row).
 *
 * @param props.title The medium.
 * @param props.season The season, 1-based.
 * @param props.automatic Whether the engine launched it.
 * @returns The chip.
 */
export function SeasonRequested({ title, season, automatic }: {
  title: string; season: number; automatic: boolean;
}): ReactElement {
  const { t } = useTranslation();
  return (
    <span className={chip({ tone: "info" })} data-tone="info" data-part="season/asked" data-asked-season={`${title}|${season}`}>
      {t(automatic ? "screens.media.seasonRequestedAutomatic" : "screens.media.seasonRequested")}
    </span>
  );
}
