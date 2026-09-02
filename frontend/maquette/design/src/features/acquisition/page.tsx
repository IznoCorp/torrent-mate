// design/src/pages/acquisition.tsx
// The largest migrated PAGE: legacy `viewAcquisition()`
// (290 lines, three tabs) reborn as a final component. Markup is TRANSPLANTED,
// not translated.
//
// Acquisition is where one asks for media and watches the asking: what is
// waiting, what one follows, and what one might want. The three tabs are three
// different surfaces sharing one bar, which is why they are three functions
// here rather than one with branches.
import type { ReactElement } from "react";
import { useStoreContent, useUiState } from "../../lib/store-access";
import { AcquisitionTabs } from "./acquisition-tabs";
import { DiscoverTab } from "./discover-tab";
import { FollowsTab } from "./follows-tab";
import { NowTab } from "./now-tab";

export function AcquisitionPage(): ReactElement | null {
  const state = useUiState();
  // THE WORLD IS MUTATED IN PLACE by every action this page offers — grabbing a
  // medium splices it out of one list and unshifts it into another, pausing a
  // follow writes its status — and those actions signal with `touch()`, which
  // bumps the store's VERSION and leaves `state` identical. Subscribing to the
  // state alone leaves React bailing out: measured, « Récupérer maintenant »
  // moved the medium and left every counter on screen unchanged. The two other
  // pages that read mutable data subscribe the same way, for the same reason.
  useStoreContent((content) => content.version);
  if (state.acqTab === "now") {
    return (
      <>
        <AcquisitionTabs />
        <NowTab />
      </>
    );
  }
  if (state.acqTab === "follows") {
    return (
      <>
        <AcquisitionTabs />
        <FollowsTab />
      </>
    );
  }
  return (
    <>
      <AcquisitionTabs />
      <DiscoverTab />
    </>
  );
}
