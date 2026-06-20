// The sidebar body (wordmark + board switcher + Board/Daemon nav groups). Shared by the desktop
// aside and the mobile drawer (responsive mobile, DESIGN §4.1). Pure presentational; behaviour
// identical to the pre-extraction AppShell.
import React from "react";
import { useT } from "../i18n/index.jsx";

const { Badge, Select } = window.KanbanMateDesignSystem_2463ad;

export const BOARD_NAV = [
  { id: "columns", tkey: "shell.nav.columns", key: "columns.yml" },
  { id: "transitions", tkey: "shell.nav.transitions", key: "transitions.yml" },
  { id: "defaults", tkey: "shell.nav.defaults", key: "defaults" },
  { id: "validation", tkey: "shell.nav.validation", key: "V1–V11" },
  { id: "yaml", tkey: "shell.nav.yaml", key: "read-only" },
  { id: "monitoring", tkey: "shell.nav.monitoring", key: "live" },
];
export const DAEMON_NAV = [
  { id: "daemon", tkey: "shell.nav.projects", key: "projects.json" },
  { id: "profiles", tkey: "shell.nav.profiles", key: "read-only" },
];
export const ALL_NAV = [...BOARD_NAV, ...DAEMON_NAV];

export function Wordmark({ size = 16 }) {
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
      KanbanMate
    </span>
  );
}

function NavItem({ item, label, active, onClick, badge }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 8,
        width: "100%",
        padding: "7px 10px",
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
      <span style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: 2,
            flex: "none",
            background: active ? "var(--primary)" : "var(--border)",
          }}
        />
        {label}
      </span>
      {badge != null && badge > 0 ? (
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
}) {
  const { t } = useT();
  const multiBoard = projects.length > 1;
  return (
    <>
      <div
        style={{
          padding: "16px 16px 14px",
          borderBottom: "1px solid var(--sidebar-border)",
        }}
      >
        <Wordmark />
        {/* Board switcher (DESIGN §13.1) */}
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
      </div>

      <nav
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 2,
          padding: 10,
          flex: 1,
        }}
      >
        <GroupLabel>{t("shell.group_board", { repo })}</GroupLabel>
        {BOARD_NAV.map((n) => (
          <NavItem
            key={n.id}
            item={n}
            label={t(n.tkey)}
            active={active === n.id}
            onClick={() => onNav(n.id)}
            badge={n.id === "validation" ? errorCount : null}
          />
        ))}
        <div style={{ height: 14 }} />
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
        {DAEMON_NAV.map((n) => (
          <NavItem
            key={n.id}
            item={n}
            label={t(n.tkey)}
            active={active === n.id}
            onClick={() => onNav(n.id)}
          />
        ))}
      </nav>
    </>
  );
}
