// THE BOTTOM SLOT — the place above the tab bar, and who may fill it.
//
// It is a PLACE rather than a box, and that is deliberate: its occupants
// position themselves against the phone frame, so a wrapper element would be
// markup this lot has no licence to add — the rendering of every part is
// validated (mission of 2026-08-19) and a conversion moves no pixel. What this
// module owns is the LIST: which things may sit above the bar, in what order,
// at what rank. `MODEL.md` § 2 Part 6 names that as the chrome's own property,
// and says why it is one place — today it is an accumulation of nine numbers
// across five files.
//
// IT HOLDS TWO OCCUPANTS: the library's selection bar, and the settings' save
// bar (C1) — drawn over every page that holds pending edits (`holdsEdits` in
// `app/navigation.ts`: Réglages and Trackers), never over another, because the
// operator refused a bar on every page. The frame names each feature ONCE, here, which is the same species as `app/router-tree.tsx`'s
// one import per page — the exception invariant 10 blesses by name.
//
// NO REGISTRY, and it is a decision rather than an omission. A registry with
// one member is machinery for a kind of thing rather than for a thing, which
// the tree rule forbids and which D5 calls what nobody dares delete. The day a
// second feature wants the slot, the two are named here and a registry is one
// reviewed line away.
import { useLayoutEffect, type ReactElement } from "react";

import { SelectionBar } from "../features/library/selection-bar";
import { SaveBar } from "../features/settings/banners";
import { pendingEdits } from "../lib/pending-edits-door";
import { useStoreContent } from "../lib/store-access";
import { publishSaveBarHeight } from "./bar-height";
import { rowFor } from "./navigation";

/**
 * What sits above the tab bar.
 *
 * @returns The occupants the page drawn admits.
 */
export function BottomSlot(): ReactElement {
  const page = useStoreContent((content) => String(content.state.page ?? ""));
  const holdsEdits = rowFor(page)?.holdsEdits === true;
  // A PENDING EDIT IS A STORE BUMP: the count is re-read at each one.
  const waiting = useStoreContent(() => pendingEdits()?.waiting() ?? 0);
  const saveBarShown = holdsEdits && waiting > 0;
  // The port reserves the bar's height while it shows, so nothing sits under it.
  useLayoutEffect(() => publishSaveBarHeight(), [saveBarShown]);
  return (
    <>
      <SelectionBar />
      {holdsEdits ? <SaveBar /> : null}
    </>
  );
}
