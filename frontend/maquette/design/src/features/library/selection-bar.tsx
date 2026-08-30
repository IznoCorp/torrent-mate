// THE LIBRARY'S SELECTION BAR — the feature's content, in the frame's slot.
//
// WHOSE IT IS. The BAR is the library's: what it says and what it offers are
// this feature's business. The PLACE it sits in is the frame's — above the tab
// bar, clearing the safe area, at a rank the frame decides
// (`app/bottom-slot.tsx`). That is the split `MODEL.md` § 2 Part 6 names:
// « frame slot, feature content ».
//
// IT IS A NEW FILE ON PURPOSE. `features/library/page.tsx` is 613 non-blank
// lines and one of L14's four surfaces over invariant 6's ceiling: a
// grandfathered file is never extended, not by one line. The engine created
// this node and appended it to `#device` on every selection change; it is a
// component now, mounted once, and its own condition decides whether it draws.
//
// THE VERBS STAY WHERE THEY ARE. `data-selmode` and `data-delsel` are read by
// the engine's document-level delegation, and this markup emits them
// unchanged — a conversion moves the DRAWING and nothing else. They come to
// this feature with the producers, at L19.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";

import { useStoreContent } from "../../lib/store-access";
import {
  selectionAction,
  selectionBar,
  selectionCaption,
} from "../../ui/variants";

export function SelectionBar(): ReactElement | null {
  const { t } = useTranslation();
  // SELECTED IS A `Set` THE ENGINE MUTATES IN PLACE, and `store.touch()` is
  // what announces the change. `useUiState()` would not do: it selects the
  // state OBJECT, whose identity a touch does not change, so a component
  // reading `state.selected.size` through it would never re-render. The SIZE
  // is selected instead — a number, which changes, which is what
  // `useSyncExternalStore` compares.
  const size = useStoreContent(
    (content) => (content.state.selected as Set<number> | undefined)?.size ?? 0,
  );
  const selecting = useStoreContent(
    (content) => content.state.selMode === true,
  );
  if (!selecting) return null;

  return (
    <div
      className={selectionBar()}
      data-part="selection/bar"
      // A NAMED REGION, so the caption and the two actions stop being page
      // content adrift outside every landmark. The bar exists only while a
      // selection does, which is exactly what the name says.
      role="region"
      aria-label={t("screens.library.selection.barLabel")}
    >
      <span className={selectionCaption()} data-part="selection/caption">
        {size === 0
          ? t("screens.library.selection.hint")
          : t(
              size > 1
                ? "screens.library.selection.countPlural"
                : "screens.library.selection.count",
              { count: size },
            )}
      </span>
      <button data-selmode="0" className={selectionAction()}>
        {t("screens.library.selection.cancel")}
      </button>
      <button
        data-tone="danger"
        data-delsel="1"
        disabled={size === 0}
        className={selectionAction({ tone: "danger" })}
      >
        {t("screens.library.selection.delete")}
      </button>
    </div>
  );
}
