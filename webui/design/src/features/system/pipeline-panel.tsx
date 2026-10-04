// « Le pipeline » — the section where what runs for ALL media at once is read
// and set.
//
// ITS PLACE IS THE DECISION THIS FILE STANDS FOR: between what SCHEDULES a run
// and what a run LEFT. A reader going down this page meets, in order, when runs
// happen, what governs them now, and what the last ones did — which is the
// order the questions arrive in.
//
// WHY A HOST RATHER THAN THE BLOCKS DIRECTLY. The section's blocks are drawn by
// their own files and land one at a time; the heading, its guidance line and
// their order live here, so where the section SITS is decided once and never
// re-argued by whichever block lands next.
import { useTranslation } from "react-i18next";
import { guidance } from "../../ui/variants/layout";
import { sectionHeading } from "../../ui/variants";
import { Levers } from "./levers";
import { LocksBlock } from "./locks";
import type { ReactElement } from "react";

/**
 * The pipeline section of the machine's page.
 *
 * @returns Its heading, its guidance line and its blocks.
 */
export function PipelinePanel(): ReactElement {
  const { t } = useTranslation();
  return (
    <div data-part="pipeline-panel">
      <h2 className={sectionHeading()} data-part="heading">{t("screens.system.pipeline")}</h2>
      <div className={guidance()} data-part="guidance">
        {t("screens.system.pipelineGuidance")}
      </div>
      <Levers />
      <LocksBlock />
    </div>
  );
}
