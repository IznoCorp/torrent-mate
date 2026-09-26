// « À traiter » — what only the operator's hand unblocks (ruling 7).
//
// A TAB OF ITS OWN (ruling 10), and never an empty screen (DOIT-7): with nothing
// waiting, it says so and says where the rest is.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { body, emptyNote } from "../../ui/variants";
import { Markup, emptyNoteMarkup } from "../../ui/markup";

/**
 * The « À traiter » tab's body.
 *
 * @returns The body.
 */
export function TodoTab(): ReactElement {
  const { t } = useTranslation();
  return (
    <div className={body()} data-part="surface/body" data-region="acquisition/body">
      <Markup
        className={emptyNote()} data-part="empty-state"
        html={emptyNoteMarkup(t("screens.acquisition.todoEmptyTitle"), t("screens.acquisition.todoEmptyBody"))}
      />
    </div>
  );
}
