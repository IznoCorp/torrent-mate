import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useLibraryCategories } from "./queries";
import { useUiState } from "../../lib/store-access";
import { emptyNote } from "../../ui/variants";

// What the list says when it has nothing to show, and the two reasons are not
// the same sentence: a search that matched nothing is not a category this
// prototype does not carry.
export function EmptyLibrary(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { data: CATS = [] } = useLibraryCategories();
  const category = CATS.find((entry) => entry.id === state.libCat);
  const filter = category && category.of ? category.l.toLowerCase() : null;
  if ((state.q as string).trim() !== "") {
    return (
      <div className={emptyNote()} data-part="empty-state">
        <b>
          {t("screens.library.emptySearchLead", { query: state.q as string })}
          {filter
            ? t("screens.library.emptySearchInCategory", { category: filter })
            : ""}
          {t("screens.library.emptySearchDot")}
        </b>
        {t("screens.library.emptySearchBody")}
        {filter ? (
          t("screens.library.emptySearchNarrow")
        ) : (
          <>
            <br />
            <br />
            {t("screens.library.emptySearchElsewhereLead")}
            <b>{t("screens.library.emptySearchElsewhereAction")}</b>
            {t("screens.library.emptySearchElsewhereEnd")}
          </>
        )}
      </div>
    );
  }
  return (
    <div className={emptyNote()} data-part="empty-state">
      <b>
        {t("screens.library.emptyCategoryLead", {
          category: filter ?? t("screens.library.emptyCategoryFallback"),
        })}
      </b>
      {t("screens.library.emptyCategoryMiddle")}
      <b>{category?.c ?? 0}</b>
      {t("screens.library.emptyCategoryEnd")}
    </div>
  );
}
