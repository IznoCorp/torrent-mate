// A tab bar: the lenses a page is read through, one of them selected.
//
// ONE COMPONENT FOR EVERY TAB BAR. Acquisition, Médiathèque and Trackers each
// drew their own, at three heights; this is Acquisition's bar as it stood, and
// the others come to it. The finger's floor lives in `segmentTab`, so no page
// re-declares it.
//
// IT KNOWS NO DOMAIN. Which tabs, which one is selected and what a tap writes
// are the caller's: the tap is the `data-*` attribute the caller names, read by
// the page's own verb, exactly as before. What a tab bar IS — a tab list, tabs,
// the selected one, the size — is this file's.
import type { ReactElement, ReactNode } from "react";
import { segment, segmentCount, segmentTab, viewTabs } from "./variants";

/** One tab: what it says, and the number it carries when there is one. */
export type Tab = {
  id: string;
  label: string;
  count?: number;
};

/**
 * A tab bar, sticky at the top of its scrollport.
 *
 * @param props.tabs The tabs, in the order the page reads them.
 * @param props.selected The id of the tab drawn selected.
 * @param props.attribute The `data-*` attribute a tap writes, carrying the tab's id.
 * @param props.data-region The region the row is measured as, when a rule reads it —
 *   written at the call site under the attribute's own name, so the markup guard
 *   reads the value where it is chosen.
 * @param props.trailing A control after the tabs — a « more » button.
 * @returns The tab bar.
 */
export function Tabs({ tabs, selected, attribute, "data-region": region, trailing }: {
  /** The tabs, in the order the page reads them. */
  tabs: readonly Tab[];
  /** The id of the tab drawn selected. */
  selected: string;
  /** The `data-*` attribute a tap writes. */
  attribute: `data-${string}`;
  /** The region the row is measured as. */
  "data-region"?: string;
  /** A control after the tabs. */
  trailing?: ReactNode;
}): ReactElement {
  return (
    <div className={viewTabs()} data-region={region}>
      <div className={segment()} data-part="segment" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={segmentTab()}
            role="tab"
            aria-selected={selected === tab.id}
            {...{ [attribute]: tab.id }}
          >
            {tab.label}
            {tab.count ? <span className={segmentCount()} data-part="segment/count">{tab.count}</span> : null}
          </button>
        ))}
      </div>
      {trailing}
    </div>
  );
}
