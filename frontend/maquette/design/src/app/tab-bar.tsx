// THE BOTTOM TAB BAR — the frame's chrome, and a PERSISTENT one.
//
// It was an empty `<nav>` in the document that `renderNav()` filled with
// `innerHTML` on EVERY `render()` — unconditionally, so every page switch and
// every store bump replaced the chrome's buttons with new nodes (B-231). A
// persistent chrome is the first property a mobile application owes
// (`MODEL.md` § 3, P1 and P2), and focus cannot survive a redraw that replaces
// the focused node (P28). React keeps the nodes; the rules hold that it does.
//
// IT RENDERS THE `<nav id="nav">` ITSELF, at the same id, the same classes and
// the same `data-part`, exactly as `ui/sheet.tsx` renders `#sheet`. The static
// container is gone from `index.html` in the same commit: a container removed
// a commit early is a null reference the engine captures at evaluation, and one
// removed a commit late is two elements answering one id.
//
// WHAT IT KNOWS: the navigation table (which pages sit in the bar, their label
// key, their icon, whether they carry a badge) and the store (which page is
// current, and whether the library is in selection mode). WHAT IT DOES NOT
// KNOW: what a badge counts. The row points at a function the feature exports.
import { useLayoutEffect } from "react";
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";

import { publishBarHeight } from "./bar-height";
import { NAVIGATION } from "./navigation";
import { Icon } from "../ui/icon";
import { useServerStateVersion } from "../lib/query-client";
import { useUiState } from "../lib/store-access";
import {
  tabBar,
  tabBarBadge,
  tabBarButton,
  tabBarIcon,
  tabBarIconDrawing,
  tabBarLabel,
} from "../ui/variants";

export function TabBar(): ReactElement {
  const { t } = useTranslation();
  const state = useUiState();
  const current = state.page as string | undefined;
  const selecting = state.selMode === true;
  // SUBSCRIBED TO SERVER STATE, because the badges are derived from it. A
  // synchronous read is not a subscription: without this the bar re-rendered on
  // store writes alone and a badge showed the previous scenario's count until
  // something unrelated redrew it. The value is not used — the subscription is.
  useServerStateVersion();

  // THE BAR'S HEIGHT IS PUBLISHED FROM HERE, and the move is not cosmetic.
  // `publishBarHeight()` used to run in the boot, after the engine had drawn
  // the bar — it queries `.bottombar`, and a bar drawn by React does not exist
  // at that point, so the query would answer nothing and the `ResizeObserver`
  // would never attach. R84's « exactly one publisher » is untouched:
  // `app/bar-height.ts` is still it, and only the moment it is called moved.
  // Before the paint, so nothing above the bar sits on `0px` for a frame.
  useLayoutEffect(() => {
    publishBarHeight();
  }, []);

  return (
    <nav
      id="nav"
      data-part="shell/tab-bar"
      aria-label={t("navigation.barLabel")}
      className={tabBar({ selecting })}
    >
      {NAVIGATION.filter((row) => row.inBar).map((row) => {
        // Read at render time, not stored: the count is server state in the
        // query cache, and the store bump that redraws this bar is what makes
        // the new number appear.
        const badge = row.badge ? row.badge() : 0;
        return (
          <button
            key={row.id}
            data-page={row.id}
            aria-current={current === row.id ? "page" : undefined}
            className={tabBarButton({ current: current === row.id })}
          >
            <span className={tabBarIcon()}>
              <Icon paths={row.icon} className={tabBarIconDrawing()} />
              {badge ? (
                <span className={tabBarBadge()} data-part="shell/tab-badge">
                  {badge}
                </span>
              ) : null}
            </span>
            <span className={tabBarLabel()}>{t(row.labelKey)}</span>
          </button>
        );
      })}
    </nav>
  );
}
