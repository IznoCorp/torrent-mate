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
import { registerLayer } from "./layer-registry";
import { NAVIGATION, type NavigationGroup, type NavigationRow } from "./navigation";
import { Drawer } from "../ui/drawer";
import { Icon } from "../ui/icon";
import { useServerStateVersion } from "../lib/query-client";
import { servedIdentityLines } from "../lib/served-identity";
import { useStoreContent, writeUiState } from "../lib/store-access";
import {
  drawerEntry,
  drawerEntryCount,
  drawerEntryDrawing,
  drawerGroup,
  drawerGroupTitle,
  drawerHead,
  drawerIdentity,
  drawerIdentityLabel,
  drawerIdentityPrimary,
  drawerIdentitySecondary,
  drawerNavigation,
} from "../ui/variants";

/** The groups, in the order the table first names them. */
function grouped(): { key: NavigationGroup; rows: NavigationRow[] }[] {
  const groups: { key: NavigationGroup; rows: NavigationRow[] }[] = [];
  for (const row of NAVIGATION) {
    if (!row.group) continue;
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
  const identity = servedIdentityLines();
  const appearance = currentAppearance();
  const closing = useRef(false);

  // THE GESTURE ATTACHES ONCE THE NODE EXISTS. It used to be installed from the
  // boot, which was before React drew anything: `#drawer` was static markup
  // then. E-002 is unchanged — it is still the frame's gesture, still closing
  // through `window.__closeLayers` so a swipe and a scrim tap share one path.
  useLayoutEffect(() => {
    installDrawerDismissGesture();
  }, []);

  // REGISTERED ON THE LADDER, for as long as this layer is mounted.
  useEffect(
    () =>
      registerLayer("drawer", {
        isOpen: () => window.__store.read().state.drawerOpen === true,
        close: (pop) => close(pop),
      }),
    [],
  );

  function close(pop?: boolean): void {
    if (window.__store.read().state.drawerOpen !== true) return;
    if (closing.current) return;
    closing.current = true;
    try {
      writeUiState({ drawerOpen: false });
      if (!pop) window.__derouler?.("drawer");
    } finally {
      closing.current = false;
    }
  }

  return (
    <Drawer open={open} label={t("navigation.drawerLabel")}>
      <div className={drawerHead()}>
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
      </div>
      <nav className={drawerNavigation()}>
        {grouped().map((group) => (
          <div key={group.key} className={drawerGroup()}>
            <p className={drawerGroupTitle()}>
              {t(`navigation.groups.${group.key}`)}
            </p>
            {group.rows.map((row) => {
              const badge = row.badge ? row.badge() : 0;
              return (
                <a
                  key={row.id}
                  href="#"
                  data-navgo={row.id}
                  aria-current={page === row.id ? "page" : undefined}
                  className={drawerEntry({ current: page === row.id })}
                >
                  <Icon paths={row.icon} className={drawerEntryDrawing()} />
                  <span>{t(row.labelKey)}</span>
                  {badge ? (
                    <span className={drawerEntryCount()}>{badge}</span>
                  ) : null}
                </a>
              );
            })}
          </div>
        ))}
      </nav>
      <div className={drawerGroup()}>
        <p className={drawerGroupTitle()}>{t("navigation.appearanceGroup")}</p>
        <div
          // `.segmini` IS THE ENGINE'S, and it stays a bare class for that
          // reason: the engine emits the same segment elsewhere, so its rules
          // are residue that outlives this drawer and `add-screen.tsx` already
          // wears it the same way.
          className="segmini"
          data-part="segment-small"
          role="group"
          aria-label={t("navigation.appearanceLabel")}
        >
          {APPEARANCES.map((mode) => (
            <button
              key={mode}
              data-appearance={mode}
              aria-pressed={appearance === mode}
              onClick={() => {
                chooseAppearance(mode);
                // Reflected in place: the drawer stays open — choosing an
                // appearance is not a navigation, and watching the theme change
                // IS the feedback. The bump is what redraws the pressed state.
                window.__store.touch();
              }}
            >
              {t(`navigation.appearance.${mode}`)}
            </button>
          ))}
        </div>
      </div>
      {/* WHAT THIS HOST IS SERVING, and it used to be a lie: three literals — a
          version, a build sha and « à jour » — none computed and none checked,
          while the repository stood twenty patch versions further on. The
          identity is the HOST's, published per request on the document it
          sends, and worded by `lib/served-identity.ts`, which also owns the
          case where nothing published one. `known` is forwarded as a `data-*`
          so a rule can tell the two apart without reading the words — by
          PRESENCE, like every other boolean state attribute here. */}
      <div
        className={drawerIdentity()}
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
