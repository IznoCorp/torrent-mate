// AppShell: sidebar + header chrome (ported from the kit ui_kit, ES-module form).
// Carries the board switcher (DESIGN §13.1) and TWO nav groups — board-scoped tabs and a visually
// distinct Daemon scope (DESIGN §13.2). Header Validate/Save apply to the board scope only.
import React from "react";
import { useT, LangSwitcher } from "../i18n/index.jsx";

const { HealthPill, Button, Badge, Select } =
  window.KanbanMateDesignSystem_2463ad;

function Wordmark({ size = 16 }) {
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

const BOARD_NAV = [
  { id: "columns", tkey: "shell.nav.columns", key: "columns.yml" },
  { id: "transitions", tkey: "shell.nav.transitions", key: "transitions.yml" },
  { id: "defaults", tkey: "shell.nav.defaults", key: "defaults" },
  { id: "validation", tkey: "shell.nav.validation", key: "V1–V11" },
  { id: "yaml", tkey: "shell.nav.yaml", key: "read-only" },
  { id: "monitoring", tkey: "shell.nav.monitoring", key: "live" },
];
const DAEMON_NAV = [
  { id: "daemon", tkey: "shell.nav.projects", key: "projects.json" },
  { id: "profiles", tkey: "shell.nav.profiles", key: "read-only" },
];

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

export default function AppShell({
  active,
  onNav,
  projects = [],
  selected,
  onSelect,
  repo = "—",
  errorCount = 0,
  dirty = false,
  onSave,
  onValidate,
  onLogout = null,
  boardScope = true,
  children,
}) {
  const { t } = useT();
  const blocked = errorCount > 0;
  const allNav = [...BOARD_NAV, ...DAEMON_NAV];
  const headerTitle = allNav.find((n) => n.id === active) || BOARD_NAV[0];
  const multiBoard = projects.length > 1;

  return (
    <div
      style={{
        display: "flex",
        height: "100%",
        minHeight: 0,
        background: "var(--background)",
        color: "var(--foreground)",
      }}
    >
      <aside
        style={{
          width: 256,
          flex: "none",
          display: "flex",
          flexDirection: "column",
          background: "var(--sidebar)",
          borderRight: "1px solid var(--sidebar-border)",
        }}
      >
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
      </aside>

      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "14px 22px",
            borderBottom: "1px solid var(--border)",
            background: "color-mix(in oklch, var(--card) 86%, transparent)",
            backdropFilter: "blur(8px)",
            position: "sticky",
            top: 0,
            zIndex: 50,
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h1
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "var(--text-xl)",
                  fontWeight: 600,
                  letterSpacing: "var(--tracking-tight)",
                  margin: 0,
                }}
              >
                {t(headerTitle.tkey)}
              </h1>
              {/* Scope badge: board-scoped vs daemon-scoped, obvious at a glance (DESIGN §13.2) */}
              {boardScope ? (
                <Badge tone="neutral" size="sm">
                  {t("shell.badge_board", { repo })}
                </Badge>
              ) : (
                <Badge tone="amber" size="sm">
                  {t("shell.badge_daemon")}
                </Badge>
              )}
            </div>
          </div>
          <LangSwitcher />
          {onLogout && (
            <Button variant="ghost" size="md" onClick={onLogout}>
              {t("login.logout")}
            </Button>
          )}
          {boardScope && (
            <>
              <HealthPill
                status={blocked ? "BLOCKED" : dirty ? "WAITING" : "ACTIVE"}
                size="md"
                pulse={!blocked && !dirty}
              />
              <Button variant="secondary" size="md" onClick={onValidate}>
                {t("common.validate")}
              </Button>
              <Button
                variant="primary"
                size="md"
                disabled={blocked || !dirty}
                onClick={onSave}
              >
                {blocked
                  ? t("shell.errors_block_save", { n: errorCount })
                  : dirty
                    ? t("common.save")
                    : t("common.saved")}
              </Button>
            </>
          )}
        </header>
        <main
          style={{
            flex: 1,
            minHeight: 0,
            overflow: "auto",
            padding: "22px 26px 72px",
            background: "var(--background)",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
