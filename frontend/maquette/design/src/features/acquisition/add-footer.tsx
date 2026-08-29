// THE ADD SCREEN'S ANNOUNCEMENT BAR, on its own.
//
// Extracted at L10-bis because `add-screen.tsx` crossed the 400-line ceiling
// (invariant 6) the moment this bar gained a dismissal, and the split is taken
// on a SUBJECT rather than on the line count that prompted it: what the bar
// announces, how it is dismissed and when it comes back are one behaviour, and
// they were the only part of that file with a rule of its own (R96).
//
// THE BAR IS A NOTIFICATION AND NOT A STATE OF THE SCREEN, arbitrated by the
// operator on 2026-08-29: it passes over the list, reserves no space, and is
// dismissible. Its only exit was unreadable until L10-bis, which is why it read
// as stuck (B-139).
import type { ReactElement } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Icon } from "../../ui/icon";
import {
  addFooter,
  addFooterAction,
  addFooterDismiss,
} from "./variants";

export function AddFooter({
  added,
  icons,
  toFollows,
}: {
  added: Set<number>;
  icons: Record<string, string>;
  toFollows: () => void;
}): ReactElement | null {
  const { t } = useTranslation();

  // WHAT IS REMEMBERED IS THE COUNT, never a boolean. Adding a further medium
  // is a new announcement and must be seen; a boolean would swallow every one
  // after the first, which is a different defect wearing this fix — held by
  // R96's last check and proved by mutating exactly that.
  //
  // This is genuinely ephemeral interface state: nothing server-side is copied
  // here, which is what invariant 4 refuses.
  const [dismissedAtCount, setDismissedAtCount] = useState<number | null>(null);

  if (added.size === 0 || added.size === dismissedAtCount) return null;

  return (
    <div className={addFooter()} data-part="add/foot">
      <span>
        <b>{added.size}</b>{" "}
        {added.size > 1
          ? t("screens.add.mediaPlural")
          : t("screens.add.media")}{" "}
        {added.size > 1
          ? t("screens.add.addedPlural")
          : t("screens.add.added")}
      </span>
      <button className={addFooterAction()} onClick={toFollows}>
        {t("screens.add.seeFollows")}
      </button>
      <button
        className={addFooterDismiss()}
        data-part="add/foot-dismiss"
        aria-label={t("screens.add.dismissAdded")}
        onClick={() => setDismissedAtCount(added.size)}
      >
        <Icon paths={icons.x} />
      </button>
    </div>
  );
}
