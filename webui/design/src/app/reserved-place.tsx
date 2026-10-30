// A PLACE THIS ACCOUNT DOES NOT HOLD, explained where it would have been drawn
// (§ 17 point 2; OPEN 3 = B, F29).
//
// Opened from the drawer or typed cold, a reserved page never renders: it says
// what it is, names the RIGHT this account lacks — never a role, never an
// account (ruling 17) — and who holds it by default. The sentences are one
// table in `fr.json` (`access.rights.*`, `access.holders.*`), read here, by
// Profil and by « Comptes ».
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import type { NavigationRow } from "./navigation";
import { emptyNote } from "../ui/variants";
import { Markup, emptyNoteMarkup } from "../ui/markup";
import { escapeHtml } from "../lib/markup-text";

/**
 * The explanation a reserved page draws in its place.
 *
 * Args:
 *     row: The page the account opened and does not hold.
 */
export function ReservedPlace({ row }: { row: NavigationRow }): ReactElement {
  const { t } = useTranslation();
  const right = row.opens?.[0] ?? "";
  return (
    <div data-part="access/reserved" data-right={right}>
      <Markup
        className={emptyNote()} data-part="empty-state"
        html={emptyNoteMarkup(
          t("access.reservedTitle", { page: t(row.labelKey) }),
          escapeHtml(t("access.reservedBody", { right: t(`access.rights.${right}`) }))
            + " " + escapeHtml(t(`access.holders.${right}`)),
        )}
      />
    </div>
  );
}
