// « hors catalogue (n) » under a season's row — ONE drawing, for the media
// sheet's season list and the follow panel's seasons (maquette-blocked § 1.10:
// « by the one season-row markup »), so the two surfaces cannot drift apart.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { offCatalogueMark } from "./variants";

/**
 * The line saying how many held episode numbers the catalogue does not list,
 * in the muted tone, without judgement (B-475 = B). The season's fraction is
 * not touched: it counts what aired (B-380).
 *
 * @param props.count How many held numbers the catalogue does not list — none,
 *     or undefined, draws nothing.
 * @returns The line, or null.
 */
export function SeasonOffCatalogue({ count }: { count: number | undefined }): ReactElement | null {
  const { t } = useTranslation();
  if (!count) return null;
  return (
    <span className={offCatalogueMark()} data-part="season/off-catalogue">
      {t("surfaces.season.offCatalogue", { count })}
    </span>
  );
}
