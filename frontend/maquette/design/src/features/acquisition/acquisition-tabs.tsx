import { useEngineDrawing } from "../../lib/engine-drawing";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { useAcquisitionQueue } from "../../lib/queue";
import { useUiState } from "../../lib/store-access";
import { Tabs } from "../../ui/tabs";
import { moreButton } from "../../ui/variants";
import { inFlightCards, todoCards } from "../../lib/arrival-slots";
import { useRights } from "../../lib/account";
import { isOwn } from "../../lib/rights";
import { drawnTab, tabsOpenTo } from "./tab-memory";

// The tab bar, and the « more » control that opens the watch-and-obligations
// sheet. Shared by the four surfaces below.
export function AcquisitionTabs(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  // THE BADGE COUNTS WHAT IS WAITING, from the same read the deck draws — two
  // counts of one queue is the standing way to make the operator see two
  // truths (§13).
  const scenario = state.scen === "loaded" ? "loaded" : "";
  const { data: queue } = useAcquisitionQueue(scenario);
  // THE ORDER IS THE OPERATOR'S: « Suivis · En cours · À traiter ». « Découvrir »
  // is a page of the bottom bar, not a tab of this one.
  // The tab opened by default is derived, wherever it stands in the row.
  // EVERY COUNT IS THE ACCOUNT'S OWN (R-L18-g): a card another account asked
  // for is drawn read-only to a role that sees everyone's, and counted by none.
  const rights = useRights();
  const own = (cards: Parameters<typeof isOwn>[0][]) => cards.filter((card) => isOwn(card, rights)).length;
  const open = tabsOpenTo(rights);
  const tabs = [
    { id: "follows", label: t("screens.acquisition.tabFollows") },
    // « EN COURS » COUNTS WHAT MOVES — « En vol », the one list it draws.
    { id: "now", label: t("screens.acquisition.tabNow"), count: queue ? own(inFlightCards(queue)) : 0 },
    // « À TRAITER » COUNTS ITS CARDS, the number the bar's badge says too.
    { id: "todo", label: t("screens.acquisition.tabTodo"), count: queue ? own(todoCards(queue)) : 0 },
  ].filter((tab) => open.includes(tab.id));
  return (
    <Tabs
      tabs={tabs}
      selected={drawnTab(String(state.acqTab), rights)}
      attribute="data-acqtab"
      data-region="acquisition/tabs"
      trailing={
        <button className={moreButton()} aria-label={t("screens.acquisition.moreLabel")} data-more>
          <Icon paths={icons.more} />
        </button>
      }
    />
  );
}
