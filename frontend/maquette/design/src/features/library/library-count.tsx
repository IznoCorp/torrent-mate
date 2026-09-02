// The count line's own sentence, and the sort control's own label.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { useLibraryReference } from "./reference";
import { useLibraryCategories, useLibraryListing } from "./queries";
import { useUiState } from "../../lib/store-access";

// The count line's own sentence: how many of how many, or how many results for
// what was typed. The category qualifies both, and « Tout » qualifies neither
// — it is the whole library, not a filter on it.
export function CountLine(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { data: CATS = [] } = useLibraryCategories();
  // FROM THE SAME QUERY THE LIST READS, so the two cannot disagree about how
  // many rows are on screen — §13's « une seule dérivation par question »,
  // which two independent counts is the standing way to break.
  const listing = useLibraryListing(
    String(state.q ?? ""),
    String(state.libCat ?? ""),
    String(state.sortKey ?? ""),
    Boolean(state.sortReversed),
  );
  const total = listing.data?.pages[0]?.total ?? 0;
  const shown = (listing.data?.pages ?? []).reduce(
    (count, page) => count + page.items.length, 0);
  const category = CATS.find((entry) => entry.id === state.libCat);
  // THE LIBRARY'S OWN TOTAL, SERVED. It was written here as the literal 1861,
  // three lines under a comment saying the count comes « from the same query
  // the list reads, so the two cannot disagree » — while the query answered
  // that very number and the screen printed a constant instead. Change the
  // seed and the screen went on saying 1861.
  const universe = category && category.of ? category.c : total;
  const suffix =
    category && category.of
      ? t("screens.library.countCategory", { category: category.l.toLowerCase() })
      : "";
  const query = (state.q as string).trim();
  return (
    <span id="libcount">
      {query === "" ? (
        <>
          <b>{shown}</b>
          {t("screens.library.countShownMiddle")}
          <b>{universe}</b>
          {suffix}
        </>
      ) : (
        <>
          <b>{total}</b>
          {t(
            total > 1
              ? "screens.library.countResultMany"
              : "screens.library.countResultOne",
            { query: state.q as string },
          )}
          {suffix}
        </>
      )}
    </span>
  );
}

// The sort control's own label: the icon, then the NAME of the direction in
// force — E-001's own promise, read from the table the prototype declares
// rather than restated here.
export function SortLabel(): ReactElement {
  const state = useUiState();
  const { icons, TRIS } = useLibraryReference();
  const ways = TRIS[state.sortKey as string];
  return (
    <>
      <Icon paths={icons.sort} />
      {ways[state.sortReversed ? "inverse" : "normal"]}
    </>
  );
}
