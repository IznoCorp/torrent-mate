// The sidebar body (wordmark + board switcher + Board/Daemon nav groups). Shared by the desktop
// aside and the mobile drawer (responsive mobile, DESIGN §4.1). Pure presentational; behaviour
// identical to the pre-extraction AppShell.
//
// Each nav entry carries a lucide-react icon (operator-validated mapping, ticket #47). The desktop
// aside can collapse to a narrow icon-only rail (`collapsed` prop): labels/keys/switcher hide, the
// icon is centred, and the entry label surfaces as a hover tooltip (`title`).
import React from "react";
import {
  SquareKanban,
  Columns3Cog,
  ArrowRightLeft,
  SlidersHorizontal,
  BadgeCheck,
  FileCode,
  MonitorCheck,
  ServerCog,
  ShieldCogCorner,
} from "lucide-react";
import { useT } from "../i18n/index.jsx";

const { Badge, Select } = window.KanbanMateDesignSystem_2463ad;

// lucide icon per nav entry — operator-validated set (#47, "Decided — sidebar icons" 2026-06-20).
const NAV_ICON = {
  board: SquareKanban,
  columns: Columns3Cog,
  transitions: ArrowRightLeft,
  defaults: SlidersHorizontal,
  validation: BadgeCheck,
  yaml: FileCode,
  monitoring: MonitorCheck,
  daemon: ServerCog,
  profiles: ShieldCogCorner,
};

// Three semantic nav groups rendered in order: Views (non-config), Config, Daemon.
export const VIEWS_NAV = [
  { id: "board", tkey: "shell.nav.board", key: "native" },
  { id: "monitoring", tkey: "shell.nav.monitoring", key: "live" },
];
export const CONFIG_NAV = [
  { id: "columns", tkey: "shell.nav.columns", key: "columns.yml" },
  { id: "transitions", tkey: "shell.nav.transitions", key: "transitions.yml" },
  { id: "defaults", tkey: "shell.nav.defaults", key: "defaults" },
  { id: "validation", tkey: "shell.nav.validation", key: "V1–V11" },
  { id: "yaml", tkey: "shell.nav.yaml", key: "read-only" },
];
export const DAEMON_NAV = [
  { id: "daemon", tkey: "shell.nav.projects", key: "projects.json" },
  { id: "profiles", tkey: "shell.nav.profiles", key: "read-only" },
];
export const ALL_NAV = [...VIEWS_NAV, ...CONFIG_NAV, ...DAEMON_NAV];

export function Wordmark({ size = 16, markOnly = false }) {
  const mark = (
    <span
      style={{
        display: "inline-grid",
        placeItems: "center",
        width: size * 1.6,
        height: size * 1.6,
        borderRadius: "var(--radius-md)",
        background: "var(--primary)",
        color: "var(--primary-foreground)",
        fontFamily: "var(--font-mono)",
        fontWeight: 600,
        fontSize: size * 0.95,
        flex: "none",
      }}
    >
      [▸]
    </span>
  );
  if (markOnly) return mark;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        fontFamily: "var(--font-display)",
        fontWeight: 700,
        letterSpacing: "var(--tracking-tight)",
        color: "var(--sidebar-foreground)",
        lineHeight: 1,
        fontSize: size,
      }}
    >
      {mark}
      KanbanMate
    </span>
  );
}

function NavItem({ item, label, active, onClick, badge, collapsed = false }) {
  const [hover, setHover] = React.useState(false);
  const Icon = NAV_ICON[item.id];
  const hasBadge = badge != null && badge > 0;
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title={collapsed ? label : undefined}
      aria-label={collapsed ? label : undefined}
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: collapsed ? "center" : "space-between",
        gap: 8,
        width: "100%",
        padding: collapsed ? "9px 0" : "7px 10px",
        border: "none",
        cursor: "pointer",
        textAlign: "left",
        borderRadius: "var(--radius-md)",
        fontFamily: "var(--font-sans)",
        fontSize: "var(--text-sm)",
        fontWeight: active ? 600 : 500,
        color: active
          ? "var(--sidebar-accent-foreground)"
          : "var(--muted-foreground)",
        background: active || hover ? "var(--sidebar-accent)" : "transparent",
      }}
    >
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: collapsed ? 0 : 9,
          minWidth: 0,
        }}
      >
        {Icon ? (
          <Icon
            size={16}
            strokeWidth={1.75}
            style={{
              flex: "none",
              color: active ? "var(--primary)" : "currentColor",
            }}
          />
        ) : (
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 2,
              flex: "none",
              background: active ? "var(--primary)" : "var(--border)",
            }}
          />
        )}
        {!collapsed && label}
      </span>
      {collapsed ? (
        hasBadge ? (
          <span
            style={{
              position: "absolute",
              top: 5,
              right: 8,
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--destructive, #dc2626)",
            }}
          />
        ) : null
      ) : hasBadge ? (
        <Badge tone="red" size="sm">
          {badge}
        </Badge>
      ) : (
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--muted-foreground)",
            opacity: 0.7,
          }}
        >
          {item.key}
        </span>
      )}
    </button>
  );
}

function GroupLabel({ children, tone }) {
  return (
    <div
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        letterSpacing: ".09em",
        textTransform: "uppercase",
        color:
          tone === "daemon"
            ? "var(--health-waiting-fg, #b45309)"
            : "var(--muted-foreground)",
        padding: "6px 10px 8px",
        display: "flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      {children}
    </div>
  );
}

export default function SidebarNav({
  active,
  onNav,
  projects = [],
  selected, // eslint-disable-line no-unused-vars -- kept for call-site symmetry
  onSelect,
  repo = "—",
  errorCount = 0,
  collapsed = false,
}) {
  const { t } = useT();
  const multiBoard = projects.length > 1;
  return (
    <>
      <div
        style={{
          padding: collapsed ? "16px 0 12px" : "16px 16px 14px",
          display: collapsed ? "flex" : "block",
          justifyContent: "center",
          borderBottom: "1px solid var(--sidebar-border)",
        }}
      >
        <Wordmark markOnly={collapsed} />
        {/* Board switcher (DESIGN §13.1) — hidden in the collapsed icon rail */}
        {!collapsed && (
          <div style={{ marginTop: 12 }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: ".06em",
                textTransform: "uppercase",
                color: "var(--muted-foreground)",
                marginBottom: 5,
              }}
            >
              {t("shell.board")}
            </div>
            {multiBoard ? (
              <Select
                options={projects.map((p) => p.repo)}
                value={repo}
                onChange={(e) => {
                  const r = e && e.target ? e.target.value : e;
                  const hit = projects.find((p) => p.repo === r);
                  if (hit) onSelect(hit.project_id);
                }}
                style={{ width: "100%" }}
              />
            ) : (
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--foreground)",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <span>⎇</span>
                {repo}
              </div>
            )}
          </div>
        )}
      </div>

      <nav
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 2,
          padding: collapsed ? "10px 8px" : 10,
          flex: 1,
        }}
      >
        {/* Views: board + monitoring — non-config views shown first */}
        {!collapsed && <GroupLabel>{t("shell.group_views")}</GroupLabel>}
        {VIEWS_NAV.map((n) => (
          <NavItem
            key={n.id}
            item={n}
            label={t(n.tkey)}
            active={active === n.id}
            onClick={() => onNav(n.id)}
            collapsed={collapsed}
          />
        ))}
        <div style={{ height: collapsed ? 8 : 14 }} />
        {/* Config: columns, transitions, defaults, validation, yaml — board-scoped */}
        {!collapsed && (
          <GroupLabel>{t("shell.group_config", { repo })}</GroupLabel>
        )}
        {CONFIG_NAV.map((n) => (
          <NavItem
            key={n.id}
            item={n}
            label={t(n.tkey)}
            active={active === n.id}
            onClick={() => onNav(n.id)}
            badge={n.id === "validation" ? errorCount : null}
            collapsed={collapsed}
          />
        ))}
        <div style={{ height: 14 }} />
        {!collapsed && (
          <GroupLabel tone="daemon">
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--health-waiting-fg, #b45309)",
              }}
            />
            {t("shell.group_daemon")}
          </GroupLabel>
        )}
        {DAEMON_NAV.map((n) => (
          <NavItem
            key={n.id}
            item={n}
            label={t(n.tkey)}
            active={active === n.id}
            onClick={() => onNav(n.id)}
            collapsed={collapsed}
          />
        ))}
      </nav>
    </>
  );
}
