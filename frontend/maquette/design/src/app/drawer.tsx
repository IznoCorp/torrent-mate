// WHAT IS IN THE DRAWER — the navigation table, the appearance, and what this
// host is serving.
//
// THREE THINGS THE FRAME OWNS ANYWAY (`MODEL.md` § 2 Part 7): the navigation
// table is Part 5's, the appearance is Part 9's, and the served identity is the
// document's own answer about itself. So the drawer knows no domain beyond the
// table the invariant blesses.
//
// IT REGISTERS WITH THE LADDER rather than being found by it. The engine's back
// handler tested `#drawer.classList.contains("open")`; it asks the registration
// now, exactly as it already asks `window.__panel` about the sheet. The HANDLER
// stays in the engine until L13 — this lot adds a rung, it does not move the
// walk.
//
// OPENING PUSHES ITS OWN HISTORY ENTRY and closing unwinds it, unless the close
// IS the pop. That is unchanged from the engine, and it is what makes a Back
// close the drawer without eating a page.
import { useEffect, useLayoutEffect, useRef } from "react";
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";

import {
  APPEARANCES,
  chooseAppearance,
  currentAppearance,
} from "./appearance";
import { installDrawerDismissGesture } from "./drawer-gesture";
import { drawerExtraGroups } from "./drawer-extras";
import { chooseRail, currentRail } from "./rail";
import { registerLayer, unwindLayer } from "./layers";
import { NAVIGATION, absentFor, opensFor, type NavigationGroup, type NavigationRow } from "./navigation";
import { icons } from "./icons";
import { useRights } from "../lib/account";
import type { Rights } from "../lib/rights";
import { Drawer } from "../ui/drawer";
import { Icon } from "../ui/icon";
import { useServerStateVersion } from "../lib/query-client";
import { servedIdentityLines } from "../lib/served-identity";
import { useStoreContent, useUiState, writeUiState, store } from "../lib/store-access";
import {
  drawerAppearance,
  drawerAppearanceSwitch,
  drawerBrand,
  drawerEntry,
  drawerEntryCount,
  drawerEntryCountCollapsed,
  drawerEntryLabel,
  drawerEntryDrawing,
  drawerEntryReserved,
  drawerGroup,
  drawerGroupTitle,
  drawerHead,
  drawerIdentity,
  drawerIdentityLabel,
  drawerIdentityPrimary,
  drawerIdentitySecondary,
  drawerNavigation,
  drawerRailToggle,
  drawerUnfoldedOnly,
  viewSwitch,
  viewSwitchButton,
} from "../ui/variants";

/** The groups, in the order the table first names them — minus what is absent for this account. */
function grouped(rights: Rights): { key: NavigationGroup; rows: NavigationRow[] }[] {
  const groups: { key: NavigationGroup; rows: NavigationRow[] }[] = [];
  for (const row of NAVIGATION) {
    if (!row.group || absentFor(row, rights)) continue;
    const seen = groups.find((candidate) => candidate.key === row.group);
    if (seen) seen.rows.push(row);
    else groups.push({ key: row.group, rows: [row] });
  }
  return groups;
}

export function NavigationDrawer(): ReactElement {
  const { t } = useTranslation();
  const open = useStoreContent((content) => content.state.drawerOpen === true);
  const page = useStoreContent((content) => content.state.page as string);
  // The badges are derived from server state, so this layer re-derives them
  // when any of it moves — the same subscription the tab bar takes.
  useServerStateVersion();
  // AND TO THE STORE, because a badge function may read it too: a derivation
  // the menu button redraws on a store write and this entry did not would be
  // two readings of one count.
  useUiState();
  // AND TO THE STORE'S VERSION, which is what the appearance's tap moves
  // (`store.touch()`): the choice lives in `localStorage`, not in the state, so
  // a subscription to the state alone never redrew the pressed control (B-580).
  useStoreContent((content) => content.version);
  const rights = useRights();
  const identity = servedIdentityLines();
  const appearance = currentAppearance();
  // FOLDED OR NOT, on a desktop (DECIDED 2). Read on every draw: the choice lives in
  // `localStorage`, and the toggle's `store.touch()` is what redraws it, as the appearance's does.
  const collapsed = currentRail() === "collapsed";
  const closing = useRef(false);

  // THE GESTURE ATTACHES ONCE THE NODE EXISTS. It used to be installed from the
  // boot, which was before React drew anything: `#drawer` was static markup
  // then. E-002 is unchanged — it is still the frame's gesture, still closing
  // through `closeLayers` so a swipe and a scrim tap share one path.
  // THE CLEANUP IS THE POINT, not tidiness: an effect that installs listeners
  // and returns nothing leaks a set on every remount, and `React.StrictMode` —
  // on, in `shell.tsx` — double-invokes it besides.
  //
  // It does NOT explain B-278: the double acknowledgement that led here survived
  // this cleanup, measured, so that entry stays open on its own.
  useLayoutEffect(() => installDrawerDismissGesture(), []);

  // REGISTERED ON THE LADDER, for as long as this layer is mounted.
  useEffect(
    () =>
      registerLayer("drawer", {
        isOpen: () => store.read().state.drawerOpen === true,
        close: (pop) => close(pop),
      }),
    [],
  );

  function close(pop?: boolean): void {
    if (store.read().state.drawerOpen !== true) return;
    if (closing.current) return;
    closing.current = true;
    try {
      writeUiState({ drawerOpen: false });
      if (!pop) unwindLayer("drawer");
    } finally {
      closing.current = false;
    }
  }

  return (
    <Drawer open={open} label={t("navigation.drawerLabel")}>
      <div className={drawerHead({ collapsed })}>
        <span className={drawerBrand({ collapsed })}>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="w-[22px] h-[22px] text-primary"
          aria-hidden="true"
        >
          <path d="M3 4h18l-7 8v7l-4 2v-9z" />
        </svg>
        <span>
          Torrent
          <em className="[font-style:normal] text-primary">Mate</em>
        </span>
        </span>
        <button
          type="button"
          className={drawerRailToggle({ collapsed })}
          data-part="shell/rail-toggle"
          aria-label={t(collapsed ? "navigation.railExpand" : "navigation.railCollapse")}
          aria-expanded={!collapsed}
          title={t(collapsed ? "navigation.railExpand" : "navigation.railCollapse")}
          onClick={() => {
            chooseRail(collapsed ? "open" : "collapsed");
            store.touch();
          }}
        >
          <Icon paths={collapsed ? icons.right : icons.left} className={drawerEntryDrawing()} />
        </button>
      </div>
      <nav className={drawerNavigation()}>
        {grouped(rights).map((group) => (
          <div key={group.key} className={drawerGroup()}>
            <p className={drawerGroupTitle({ collapsed })}>
              {t(`navigation.groups.${group.key}`)}
            </p>
            {group.rows.map((row) => {
              // A MARKED ROW CARRIES NO COUNT (F29): it would be a live number
              // the account cannot open the page to explain.
              const reserved = !opensFor(row, rights);
              const badge = !reserved && row.badge ? row.badge() : 0;
              return (
                <a
                  key={row.id}
                  href="#"
                  data-navgo={row.id}
                  data-reserved={reserved || undefined}
                  aria-current={page === row.id ? "page" : undefined}
                  title={collapsed ? t(row.labelKey) : undefined}
                  className={drawerEntry({ current: page === row.id, reserved, collapsed })}
                >
                  <Icon paths={row.icon} className={drawerEntryDrawing()} />
                  <span className={drawerEntryLabel({ collapsed })}>{t(row.labelKey)}</span>
                  {reserved ? (
                    <span className={drawerEntryReserved({ collapsed })} data-part="shell/drawer-reserved">
                      <Icon paths={icons.lock} className={drawerEntryDrawing()} />
                      {t("access.reservedTag")}
                    </span>
                  ) : null}
                  {badge ? (
                    <span
                      className={`${drawerEntryCount()} ${collapsed ? drawerEntryCountCollapsed() : ""}`}
                      data-part="shell/drawer-count"
                    >
                      {badge}
                    </span>
                  ) : null}
                </a>
              );
            })}
          </div>
        ))}
      </nav>
      <div className={`${drawerGroup()} ${drawerAppearance()} ${drawerUnfoldedOnly({ collapsed })}`}>
        <p className={drawerGroupTitle()}>{t("navigation.appearanceGroup")}</p>
        <div
          className={`${viewSwitch()} ${drawerAppearanceSwitch()}`}
          data-part="view/switch"
          role="group"
          aria-label={t("navigation.appearanceLabel")}
        >
          {APPEARANCES.map((mode) => (
            <button
              key={mode}
              className={viewSwitchButton({ size: "text" })}
              data-appearance={mode}
              aria-pressed={appearance === mode}
              onClick={() => {
                chooseAppearance(mode);
                // Reflected in place: the drawer stays open — choosing an
                // appearance is not a navigation, and watching the theme change
                // IS the feedback. The bump is what redraws the pressed state.
                store.touch();
              }}
            >
              {t(`navigation.appearance.${mode}`)}
            </button>
          ))}
        </div>
      </div>
      {/* WHAT A BUILD CONTRIBUTES, AFTER EVERYTHING THE PRODUCT OWNS (`drawer-extras.ts`).
          Empty in the product's own build: the maquette's controls arrive from the
          harness module, which this file never imports. The label and the pressed
          state are read on every draw — the entry's tap moves the store's version,
          which this component already subscribes to. */}
      {drawerExtraGroups().map((group) => (
        <div
          key={group.part}
          className={`${drawerGroup()} ${drawerAppearance()}`}
          data-part={group.part}
        >
          <p className={drawerGroupTitle({ collapsed })}>{group.title()}</p>
          {group.entries.map((entry) => (
            <button
              key={entry.id}
              id={entry.id}
              type="button"
              aria-pressed={entry.pressed ? entry.pressed() : undefined}
              title={collapsed ? entry.label() : undefined}
              className={`${drawerEntry({ collapsed })} w-full text-left`}
              onClick={() => {
                entry.onPress();
                store.touch();
              }}
            >
              <Icon paths={entry.icon} className={drawerEntryDrawing()} />
              <span className={drawerEntryLabel({ collapsed })}>{entry.label()}</span>
            </button>
          ))}
        </div>
      ))}
      {/* WHAT THIS HOST IS SERVING, and it used to be a lie: three literals — a
          version, a build sha and « à jour » — none computed and none checked,
          while the repository stood twenty patch versions further on. The
          identity is the HOST's, published per request on the document it
          sends, and worded by `lib/served-identity.ts`, which also owns the
          case where nothing published one. `known` is forwarded as a `data-*`
          so a rule can tell the two apart without reading the words — by
          PRESENCE, like every other boolean state attribute here. */}
      <div
        className={`${drawerIdentity()} ${drawerUnfoldedOnly({ collapsed })}`}
        data-part="shell/served-identity"
        data-known={identity.known || undefined}
      >
        <p className={drawerIdentityLabel()}>{identity.label}</p>
        <p className={drawerIdentityPrimary()}>{identity.primary}</p>
        <p className={drawerIdentitySecondary()}>{identity.secondary}</p>
      </div>
    </Drawer>
  );
}
