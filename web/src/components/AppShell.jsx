// AppShell: nav + header chrome. Desktop = 256px sidebar (SidebarNav) + header. Mobile = a top
// app-bar with ☰ that slides in the same SidebarNav as a drawer (responsive mobile, DESIGN §4.1).
import React from "react";
import { Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useT, LangSwitcher } from "../i18n/index.jsx";
import useIsMobile from "../useIsMobile.js";
import ThemeSwitcher from "./ThemeSwitcher.jsx";
import PwaInstallButton from "./PwaInstallButton.jsx";
import SidebarNav, { ALL_NAV } from "./SidebarNav.jsx";

const { HealthPill, Button, Badge, Tooltip } =
  window.KanbanMateDesignSystem_2463ad;

export default function AppShell({
  active,
  onNav,
  projects = [],
  selected,
  onSelect,
  repo = "—",
  errorCount = 0,
  dirty = false,
  saving = false,
  onSave,
  onValidate,
  onLogout = null,
  boardScope = true,
  children,
}) {
  const { t } = useT();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  // Desktop sidebar collapse (mini/icon rail) — persisted client-side (#47).
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(() => {
    try {
      return localStorage.getItem("bridge.sidebar.collapsed") === "1";
    } catch (_) {
      return false;
    }
  });
  React.useEffect(() => {
    try {
      localStorage.setItem(
        "bridge.sidebar.collapsed",
        sidebarCollapsed ? "1" : "0",
      );
    } catch (_) {
      /* storage may be unavailable (private mode) */
    }
  }, [sidebarCollapsed]);
  // Fetch kanbanmate version once at boot (tiller §4.5).
  const [version, setVersion] = React.useState(null);
  React.useEffect(() => {
    import("../api.js").then(({ fetchHealth }) =>
      fetchHealth()
        .then((d) => setVersion(d.version))
        .catch(() => {}),
    );
  }, []);
  const blocked = errorCount > 0;
  const headerTitle = ALL_NAV.find((n) => n.id === active) || ALL_NAV[0];

  // ---- Mobile: top app-bar + slide-in drawer (DESIGN §4.1) ----
  if (isMobile) {
    const navAndClose = (id) => {
      onNav(id);
      setDrawerOpen(false);
    };
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          minHeight: 0,
          background: "var(--background)",
          color: "var(--foreground)",
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 12px",
            borderBottom: "1px solid var(--border)",
            background: "var(--card)",
            position: "sticky",
            top: 0,
            zIndex: 50,
          }}
        >
          <button
            aria-label={t("shell.menu")}
            onClick={() => setDrawerOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--foreground)",
              padding: 4,
              lineHeight: 1,
            }}
          >
            <Menu size={22} strokeWidth={1.75} />
          </button>
          <span
            style={{
              flex: 1,
              minWidth: 0,
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: "var(--text-md)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {t(headerTitle.tkey)}
          </span>
          <PwaInstallButton size="sm" />
          {boardScope && (
            <Tooltip
              label={
                blocked
                  ? t("tip.save_blocked", "Fix validation errors before saving")
                  : t("tip.save", "Save your configuration changes")
              }
              placement="bottom"
            >
              <Button
                variant="primary"
                size="sm"
                disabled={blocked || !dirty}
                loading={saving}
                onClick={onSave}
              >
                {blocked ? `${errorCount}!` : t("common.save")}
              </Button>
            </Tooltip>
          )}
        </header>

        {drawerOpen && (
          <div
            onClick={() => setDrawerOpen(false)}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.4)",
              zIndex: 100,
            }}
          >
            <aside
              onClick={(e) => e.stopPropagation()}
              style={{
                position: "fixed",
                top: 0,
                left: 0,
                bottom: 0,
                width: 280,
                maxWidth: "85vw",
                display: "flex",
                flexDirection: "column",
                background: "var(--sidebar)",
                borderRight: "1px solid var(--sidebar-border)",
                overflow: "auto",
              }}
            >
              <SidebarNav
                active={active}
                onNav={navAndClose}
                projects={projects}
                selected={selected}
                onSelect={onSelect}
                repo={repo}
                errorCount={errorCount}
              />
              <div
                style={{
                  marginTop: "auto",
                  padding: 12,
                  borderTop: "1px solid var(--sidebar-border)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                {boardScope && (
                  <Button variant="secondary" size="md" onClick={onValidate}>
                    {t("common.validate")}
                  </Button>
                )}
                <ThemeSwitcher />
                <LangSwitcher />
                {onLogout && (
                  <Button variant="ghost" size="md" onClick={onLogout}>
                    {t("login.logout")}
                  </Button>
                )}
                {/* Version footer (tiller §4.5) — mobile drawer. */}
                {version && (
                  <div
                    style={{
                      fontSize: "var(--text-2xs)",
                      color: "var(--muted-foreground)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    v{version}
                  </div>
                )}
              </div>
            </aside>
          </div>
        )}

        <main
          style={{
            flex: 1,
            minHeight: 0,
            overflow: "auto",
            padding: "16px 14px 28px",
          }}
        >
          {children}
        </main>
      </div>
    );
  }

  // ---- Desktop: sidebar + header (unchanged) ----
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
          width: sidebarCollapsed ? 64 : 256,
          flex: "none",
          display: "flex",
          flexDirection: "column",
          background: "var(--sidebar)",
          borderRight: "1px solid var(--sidebar-border)",
          transition: "width .15s ease",
        }}
      >
        <div
          style={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            overflow: "auto",
          }}
        >
          <SidebarNav
            active={active}
            onNav={onNav}
            projects={projects}
            selected={selected}
            onSelect={onSelect}
            repo={repo}
            errorCount={errorCount}
            collapsed={sidebarCollapsed}
          />
        </div>
        {/* Collapse toggle (#47): panel-left-close (expanded) / panel-left-open (collapsed). */}
        <Tooltip
          label={sidebarCollapsed ? t("shell.expand") : t("shell.collapse")}
        >
          <button
            onClick={() => setSidebarCollapsed((v) => !v)}
            aria-label={
              sidebarCollapsed ? t("shell.expand") : t("shell.collapse")
            }
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: sidebarCollapsed ? "center" : "flex-start",
              gap: 9,
              padding: sidebarCollapsed ? "10px 0" : "10px 14px",
              border: "none",
              borderTop: "1px solid var(--sidebar-border)",
              background: "transparent",
              color: "var(--muted-foreground)",
              cursor: "pointer",
              fontFamily: "var(--font-sans)",
              fontSize: "var(--text-sm)",
            }}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen size={18} strokeWidth={1.75} />
            ) : (
              <>
                <PanelLeftClose size={18} strokeWidth={1.75} />
                {t("shell.collapse")}
              </>
            )}
          </button>
        </Tooltip>
        {/* Version footer (tiller §4.5): muted at the very bottom of the sidebar. */}
        {version && (
          <div
            style={{
              padding: sidebarCollapsed ? "4px 0" : "6px 14px",
              fontSize: "var(--text-2xs)",
              color: "var(--muted-foreground)",
              textAlign: sidebarCollapsed ? "center" : "left",
              fontFamily: "var(--font-mono)",
              borderTop: sidebarCollapsed
                ? "none"
                : "1px solid var(--sidebar-border)",
            }}
          >
            v{version}
          </div>
        )}
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
          <PwaInstallButton size="md" />
          <ThemeSwitcher />
          <LangSwitcher />
          {onLogout && (
            <Tooltip
              label={t("tip.logout", "Sign out")}
              placement="bottom"
            >
              <Button variant="ghost" size="md" onClick={onLogout}>
                {t("login.logout")}
              </Button>
            </Tooltip>
          )}
          {boardScope && (
            <>
              <HealthPill
                status={blocked ? "BLOCKED" : dirty ? "WAITING" : "ACTIVE"}
                size="md"
                pulse={!blocked && !dirty}
              />
              <Tooltip
                label={t("tip.validate", "Check the configuration for errors")}
                placement="bottom"
              >
                <Button variant="secondary" size="md" onClick={onValidate}>
                  {t("common.validate")}
                </Button>
              </Tooltip>
              <Tooltip
                label={
                  blocked
                    ? t(
                        "tip.save_blocked",
                        "Fix validation errors before saving",
                      )
                    : t("tip.save", "Save your configuration changes")
                }
                placement="bottom"
              >
                <Button
                  variant="primary"
                  size="md"
                  disabled={blocked || !dirty}
                  loading={saving}
                  onClick={onSave}
                >
                  {blocked
                    ? t("shell.errors_block_save", { n: errorCount })
                    : dirty
                      ? t("common.save")
                      : t("common.saved")}
                </Button>
              </Tooltip>
            </>
          )}
        </header>
        <main
          style={{
            flex: 1,
            minHeight: 0,
            overflow: "auto",
            padding: "22px 26px 20px",
            background: "var(--background)",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
