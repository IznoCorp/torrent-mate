// « Classement des releases » — the ranking editor, under the settings page.
//
// IT LISTS WHAT `ranking.json5` HOLDS, read through the file's own operation —
// never a list of criteria written here: each criterion's field, its weight,
// and either its score per value or its thresholds, in the file's order.
//
// A WEIGHT IS TYPED AND SAVED through the file's own write, the one every
// setting rides, carrying the digest the read answered: a file that moved
// under the editor takes nothing, and says so in the settings' own words.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useState, type ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { useEngineDrawing } from "../../lib/engine-drawing";
import { bridge, toast } from "../../lib/shell-doors";
import { HELD, read } from "../../lib/query-client";
import type { Schemas } from "../../lib/contract-schemas";
import {
  actionButton, backAction, body, factDetail, factList, factName, factRow, factRowBody, loadError, loadErrorAction,
  screen, screenBar, scrollport,
} from "../../ui/variants";
import { configurationStatusQuery, writeConfigurationFile } from "./queries";
import { rankingCriterion, readAgainAction, weightInput } from "./variants";
import { RankingPreview, type RankingFileBlock } from "./ranking-preview";

type Criterion = Schemas["RankingCriterion"];

/** The key of the ranking file's content. */
export const rankingFileKey = ["/api/v1/config/files/ranking.json5"];

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

/** The weights the operator typed, by criterion, as typed. */
type TypedByCriterion = Record<string, string>;

/**
 * Whether a typed weight is one the file can hold: a number, nothing else.
 *
 * @param typed What was typed.
 * @returns True when it reads as a finite number.
 */
function isWeight(typed: string): boolean {
  return typed.trim() !== "" && Number.isFinite(Number(typed));
}

/**
 * The file's values with the typed weights in place, every other key as read.
 *
 * @param values The file's values, as the read answered them.
 * @param typed The typed weights.
 * @returns What the save writes.
 */
function withTyped(values: Record<string, unknown>, typed: TypedByCriterion): Record<string, unknown> {
  const ranking = values.ranking as { criteria?: Criterion[] } | undefined;
  const criteria = (ranking?.criteria ?? []).map((criterion) =>
    criterion.field in typed ? { ...criterion, weight: Number(typed[criterion.field]) } : criterion);
  return { ...values, ranking: { ...ranking, criteria } };
}

/**
 * The ranking editor's screen.
 *
 * @returns The screen, its criteria as the file holds them.
 */
export function RankingScreen(): ReactElement {
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const { data: file, isPending, isError, error } = useRankingFile();
  const client = useQueryClient();
  const [typed, setTyped] = useState<TypedByCriterion>({});
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const ranking = (file?.values as { ranking?: { criteria?: Criterion[] } } | undefined)?.ranking;
  const criteria = ranking?.criteria ?? [];
  const saveOpen = Object.keys(typed).length > 0 && Object.values(typed).every(isWeight) && !saving;
  // THE PREVIEW SCORES WHAT IS TYPED, as far as it reads as a weight: a field
  // half-typed keeps the file's own until it does.
  const previewBlock = file === undefined ? undefined : withTyped(file.values,
    Object.fromEntries(Object.entries(typed).filter(([, value]) => isWeight(value)))).ranking as RankingFileBlock;

  // THE SAVE ASKS THE LAYER and draws what it answers. A write the outbox held
  // has not landed, so it keeps the edits and says nothing; a conflict keeps
  // them too — the operator's work is not thrown away on top of the surprise.
  // A REFUSAL lets the button go and SAYS it, the edits kept: « Enregistrement… »
  // never outlives the write it names.
  const save = async () => {
    if (file === undefined) return;
    setSaving(true);
    let answered: Awaited<ReturnType<typeof writeConfigurationFile>>;
    try {
      answered = await writeConfigurationFile(
        file.name, { values: withTyped(file.values, typed), digest: file.digest });
    } catch {
      toast?.show({ message: t("screens.ranking.saveRefused") });
      return;
    } finally {
      setSaving(false);
    }
    if (answered === HELD || answered === undefined) return;
    if (answered.conflict) {
      setConflict(true);
      return;
    }
    setTyped({});
    await client.invalidateQueries({ queryKey: rankingFileKey });
    await client.invalidateQueries({ queryKey: configurationStatusQuery.queryKey });
    toast?.show({ message: t("panels.setting.savedToast", { files: file.name }) });
  };
  // RE-READING after a conflict is the operator's decision, as in the settings.
  const readAgain = () => {
    setConflict(false);
    setTyped({});
    void client.invalidateQueries({ queryKey: rankingFileKey });
  };
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
        <div className={body()} data-part="surface/body" data-region="screen-ranking/body">
          <h1 className={factName()}>{t("screens.ranking.title")}</h1>
          {/* THE READ IN FLIGHT, OR FAILED, IS SAID — never an empty list standing for either. */}
          {isPending ? <Skeletons count={4} shape="card" /> : null}
          {isError ? <SurfaceError subject={t("screens.ranking.errorSubject")} failure={error ?? undefined} /> : null}
          {conflict ? (
            <div className={loadError()} data-part="load-error">
              <b>{t("screens.settings.conflictLead")}</b>
              {t("screens.settings.conflictRest")}{" "}
              <button className={`${loadErrorAction()} ${readAgainAction()}`} data-part="ranking/read-again" onClick={readAgain}>
                {t("screens.ranking.conflictReload")}
              </button>
            </div>
          ) : null}
          <ol className={factList()} data-part="ranking/criteria">
            {criteria.map((criterion) => (
              <li key={criterion.field} className={`${factRow()} ${rankingCriterion()}`} data-part="ranking/criterion" data-field={criterion.field}>
                <span className={factRowBody()}>
                  <span className={factName()}>{criterion.field}</span>
                  <span className={factDetail()} data-part="ranking/scoring">{scoring(criterion, t)}</span>
                </span>
                <input className={weightInput()} data-part="ranking/weight" type="number" inputMode="decimal"
                  value={typed[criterion.field] ?? String(criterion.weight)}
                  aria-label={t("screens.ranking.weightLabel", { field: criterion.field })}
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    setTyped((before) => ({ ...before, [criterion.field]: value }));
                  }} />
              </li>
            ))}
          </ol>
          {criteria.length > 0 ? (
            <button className={actionButton({ kind: "panelAction", tone: "primary" })} data-part="ranking/save"
              disabled={!saveOpen} onClick={() => void save()}>
              {saving ? t("screens.ranking.saving") : t("screens.ranking.save")}
            </button>
          ) : null}
          {previewBlock !== undefined && criteria.length > 0 ? <RankingPreview block={previewBlock} /> : null}
        </div>
      </div>
    </section>
  );
}
