// « Classement des releases » — the ranking editor, under the settings page.
//
// IT LISTS WHAT `ranking.json5` HOLDS, read through the file's own operation —
// never a list of criteria written here: each criterion's field, its weight,
// and either its score per value or its thresholds, in the file's order. The
// write that edits them rides the same file's write, like every setting.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { useEngineDrawing } from "../../lib/engine-drawing";
import { bridge } from "../../lib/shell-doors";
import { read } from "../../lib/query-client";
import type { Schemas } from "../../lib/contract-schemas";
import {
  backAction, body, factDetail, factList, factName, factRow, factRowBody, factValue, screen, screenBar, scrollport,
} from "../../ui/variants";

type Criterion = Schemas["RankingCriterion"];

/** The key of the ranking file's content. */
export const rankingFileKey = ["/api/config/files/ranking.json5"];

/**
 * The ranking the file holds.
 *
 * @returns The query, its answer the file's criteria in order.
 */
function useRankingFile() {
  return useQuery({
    queryKey: rankingFileKey,
    queryFn: async () => read<Schemas["ConfigurationFileContent"]>(rankingFileKey[0]),
  });
}

/**
 * What a criterion scores, in words: its score per value, or its thresholds.
 *
 * @param criterion The criterion.
 * @param t The interface's words.
 * @returns The line, in the file's order.
 */
function scoring(criterion: Criterion, t: (key: string, values: Record<string, unknown>) => string): string {
  if (criterion.values) {
    return Object.entries(criterion.values).map(([value, score]) => `${value} ${score}`).join(" · ");
  }
  return (criterion.thresholds ?? [])
    .map((threshold) => t("screens.ranking.threshold", { at: threshold.at, score: threshold.score })).join(" · ");
}

/**
 * The ranking editor's screen.
 *
 * @returns The screen, its criteria as the file holds them.
 */
export function RankingScreen(): ReactElement {
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const { data: file, isPending, isError } = useRankingFile();
  const ranking = (file?.values as { ranking?: { criteria?: Criterion[] } } | undefined)?.ranking;
  const criteria = ranking?.criteria ?? [];
  return (
    <section className={screen({ open: true })} data-part="screen" data-open="" data-key="ranking"
      aria-label={t("screens.ranking.title")}>
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.ranking.back")}
        </button>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={body()} data-part="surface/body">
          <h1 className={factName()}>{t("screens.ranking.title")}</h1>
          {/* THE READ IN FLIGHT, OR FAILED, IS SAID — never an empty list standing for either. */}
          {isPending ? <Skeletons count={4} shape="card" /> : null}
          {isError ? <SurfaceError subject={t("screens.ranking.errorSubject")} /> : null}
          <ol className={factList()} data-part="ranking/criteria">
            {criteria.map((criterion) => (
              <li key={criterion.field} className={factRow()} data-part="ranking/criterion" data-field={criterion.field}>
                <span className={factRowBody()}>
                  <span className={factName()}>{criterion.field}</span>
                  <span className={factDetail()} data-part="ranking/scoring">{scoring(criterion, t)}</span>
                </span>
                <span className={factValue()} data-part="ranking/weight">
                  {t("screens.ranking.weight", { weight: criterion.weight })}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
