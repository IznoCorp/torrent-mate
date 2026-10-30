// design/src/features/acquisition/page.tsx
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
import { FollowsTab } from "./follows-tab";
import { NowTab } from "./now-tab";
import { TodoTab } from "./todo-tab";
import { useRights } from "../../lib/account";
import { drawnTab } from "./tab-memory";

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
  // A TAB THE ACCOUNT DOES NOT OPEN IS NEVER DRAWN (§ 17), whatever the dial
  // holds: its first open tab is. Before the account is read, the dial stands.
  const tab = drawnTab(String(state.acqTab), useRights());
  if (tab === "now") {
    return (
      <>
        <AcquisitionTabs />
        <NowTab />
      </>
    );
  }
  if (tab === "todo") {
    return (
      <>
        <AcquisitionTabs />
        <TodoTab />
      </>
    );
  }
  // « Suivis », and whatever else the dial holds: a tab that is no longer one
  // (« discover ») opens the first tab rather than an empty page.
  return (
    <>
      <AcquisitionTabs />
      <FollowsTab />
    </>
  );
}
