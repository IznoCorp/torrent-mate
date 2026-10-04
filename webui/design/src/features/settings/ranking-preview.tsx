// The ranking editor's live preview — the fixed sample set, scored as typed.
//
// IT ASKS THE PREVIEW OPERATION, never computes a score here: the ranking as
// the screen holds it — the file's criteria with the weights typed so far —
// goes to the operation, and its answer is drawn in its order. An excluded
// release stays a row, sunk last and flagged: a preview that silently dropped
// it would hide the very thing the ranking discards.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Chip } from "../../ui/chip";
import { SurfaceError } from "../../ui/state-surfaces";
import { readByPost } from "../../lib/query-client";
import type { Schemas } from "../../lib/contract-schemas";
import {
  factDetail, factList, factName, factRow, factRowBody, factValue, ruleNote, section, sectionTitle,
} from "../../ui/variants";

/** The preview operation's address. */
const PREVIEW_PATH = "/api/v1/acquisition/ranking/preview";
/** The file's key for the seeders under which a release is excluded — the engine's spelling. */
const FILE_MINIMUM_KEY = "min_seeders";
/** The engine's own minimum when the file sets none (`RankingConfig.min_seeders`). */
const ENGINE_MINIMUM = 1;

/** The ranking as `ranking.json5` holds it: its criteria and bonuses, and its other keys as written. */
export type RankingFileBlock = {
  criteria?: Schemas["RankingCriterion"][];
  bonuses?: Schemas["RankingBonuses"];
  [key: string]: unknown;
};

/**
 * The ranking the operation scores by, read from the file's block.
 *
 * @param block The file's ranking block, the typed weights already in place.
 * @returns The ranking in the contract's shape.
 */
function rankingOf(block: RankingFileBlock): Schemas["RankingConfig"] {
  return {
    criteria: block.criteria ?? [],
    minSeeders: typeof block[FILE_MINIMUM_KEY] === "number" ? block[FILE_MINIMUM_KEY] : ENGINE_MINIMUM,
    bonuses: block.bonuses ?? { freeleech: 0, silverleech: 0 },
  };
}

/**
 * The live preview.
 *
 * @param properties The ranking block as the screen holds it.
 * @returns The preview: every sample, in the order the operation answers.
 */
export function RankingPreview({ block }: { block: RankingFileBlock }): ReactElement {
  const { t } = useTranslation();
  const ranking = rankingOf(block);
  const { data, isError } = useQuery({
    queryKey: [PREVIEW_PATH, ranking],
    queryFn: async () => readByPost<Schemas["RankingPreview"]>(PREVIEW_PATH, ranking),
    // THE LAST ANSWER STAYS while the next is asked, so a typed digit re-orders
    // the rows rather than blanking them.
    placeholderData: keepPreviousData,
  });
  return (
    <section className={section()} data-part="ranking/preview">
      <h2 className={sectionTitle()}>{t("screens.ranking.previewTitle")}</h2>
      <p className={ruleNote()}>{t("screens.ranking.previewLead")}</p>
      {isError ? <SurfaceError subject={t("screens.ranking.previewErrorSubject")} /> : null}
      <ol className={factList()}>
        {(data?.ranked ?? []).map((release) => (
          <li key={release.title} className={factRow()} data-part="ranking/preview-row" data-title={release.title}
            data-excluded={String(release.excluded)}>
            <span className={factRowBody()}>
              <span className={factName()}>{release.title}</span>
              <span className={factValue()} data-part="ranking/preview-score">
                {t("screens.ranking.previewScore", { score: release.score })}
              </span>
              <span className={factDetail()}>
                {release.provider}
                {release.excluded ? (
                  <>
                    {" "}
                    <Chip tone="warning" label={t("screens.ranking.previewExcluded")} />{" "}
                    {t("screens.ranking.previewExcludedReason",
                      { seeders: release.seeders, minimum: ranking.minSeeders })}
                  </>
                ) : null}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
