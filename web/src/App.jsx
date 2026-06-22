import React from "react";
import * as api from "./api.js";
import AppShell from "./components/AppShell.jsx";
import ColumnsPanel from "./panels/ColumnsPanel.jsx";
import TransitionsPanel from "./panels/TransitionsPanel.jsx";
import {
  DefaultsPanel,
  ValidationPanel,
  YamlPanel,
} from "./panels/SidePanels.jsx";
import DaemonPanel from "./panels/DaemonPanel.jsx";
import ProfilesPanel from "./panels/ProfilesPanel.jsx";
import MonitoringPanel from "./panels/MonitoringPanel.jsx";
import BoardPanel from "./panels/BoardPanel.jsx";
import IssuesPanel from "./panels/IssuesPanel.jsx";
import LoginScreen from "./components/LoginScreen.jsx";
import { useT } from "./i18n/index.jsx";

const { Banner } = window.KanbanMateDesignSystem_2463ad;

// bridge edits config across N boards the daemon manages (DESIGN §13). The shell carries a board
// switcher; board-scoped tabs edit the SELECTED board's config, and a visually distinct "Daemon"
// scope edits the registry (enabled/ingress per project). One draft state per selected board.
export default function App() {
  const { t } = useT();
  const [projects, setProjects] = React.useState(null); // [{project_id, repo, enabled, ingress}]
  const [selected, setSelected] = React.useState(null); // project_id
  const [draft, setDraft] = React.useState(null);
  const [findings, setFindings] = React.useState([]);
  const [dirty, setDirty] = React.useState(false);
  const [saving, setSaving] = React.useState(false); // config-save in flight (spinner + multi-click guard)
  // Persist the active tab across reloads (refresh should keep your place — esp. on mobile).
  // Default landing after login = Monitoring (operator).
  const [active, setActive] = React.useState(() => {
    const stored =
      (typeof localStorage !== "undefined" &&
        localStorage.getItem("bridge.tab")) ||
      "monitoring";
    return stored === "new-ticket" ? "issues" : stored; // legacy id → Issues hub
  }); // tab id; "daemon" = registry scope
  const [error, setError] = React.useState(null);
  const [bootError, setBootError] = React.useState(null);
  const [authed, setAuthed] = React.useState(null); // null = checking; false = needs login; true = ok
  const [authEnabled, setAuthEnabled] = React.useState(false);

  // Boot step 1: check the session (login may be enabled). Open UIs report authenticated=true.
  React.useEffect(() => {
    api
      .getSession()
      .then((s) => {
        setAuthEnabled(s.auth_enabled);
        setAuthed(s.authenticated);
      })
      .catch((e) => setBootError(e.message));
  }, []);

  // Boot step 2: once authenticated, load the project list + restore the last board (else first).
  React.useEffect(() => {
    if (!authed) return;
    api
      .listProjects()
      .then((r) => {
        setProjects(r.projects);
        if (r.projects.length) {
          const saved =
            typeof localStorage !== "undefined"
              ? localStorage.getItem("bridge.board")
              : null;
          const hit = r.projects.find((p) => p.project_id === saved);
          setSelected(hit ? hit.project_id : r.projects[0].project_id);
        }
      })
      .catch((e) => setBootError(e.message));
  }, [authed]);

  // Persist tab + selected board so a refresh lands on the same view.
  React.useEffect(() => {
    try {
      localStorage.setItem("bridge.tab", active);
    } catch (_) {
      /* storage may be unavailable (private mode) — non-fatal */
    }
  }, [active]);
  // Board cards deep-link to their ticket in Monitoring via a window event (avoids threading a
  // callback through the board's nested card components): set the target ticket, switch to the tab.
  React.useEffect(() => {
    const onOpen = (e) => {
      const issue = e && e.detail && e.detail.issue;
      if (issue == null) return;
      try {
        localStorage.setItem("bridge.monitor.ticket", String(issue));
      } catch (_) {
        /* non-fatal */
      }
      setActive("monitoring");
    };
    window.addEventListener("km:open-monitoring", onOpen);
    return () => window.removeEventListener("km:open-monitoring", onOpen);
  }, []);
  React.useEffect(() => {
    if (!selected) return;
    try {
      localStorage.setItem("bridge.board", selected);
    } catch (_) {
      /* non-fatal */
    }
  }, [selected]);

  const onLogout = async () => {
    try {
      await api.logout();
    } catch (_) {
      /* ignore */
    }
    setAuthed(false);
    setProjects(null);
    setSelected(null);
  };

  // (Re)load the selected board's config whenever the selection changes.
  React.useEffect(() => {
    if (!selected) return;
    setDraft(null);
    setFindings([]);
    setDirty(false);
    setError(null);
    api
      .getConfig(selected)
      .then(setDraft)
      .catch((e) => setError(e.message));
  }, [selected]);

  const errorCount = findings.filter((f) => f.severity === "error").length;
  const currentRepo =
    (projects || []).find((p) => p.project_id === selected)?.repo || "—";

  const update = (mut) => {
    setDraft((d) => mut(structuredClone(d)));
    setDirty(true);
  };

  const refreshFindings = async (d) => {
    try {
      const res = await api.validate(d, selected);
      setFindings(res.findings || []);
    } catch (e) {
      setError(e.message);
    }
  };

  const onValidate = () => refreshFindings(draft);

  const onSave = async () => {
    if (saving) return; // guard against double-submit while a save is in flight
    setError(null);
    setSaving(true);
    try {
      await api.saveConfig(draft, selected);
      setDirty(false); // button flips to "Saved" — the confirmation that the write landed
      await refreshFindings(draft);
    } catch (e) {
      setError(e.message);
      await refreshFindings(draft);
    } finally {
      setSaving(false);
    }
  };

  const onGoto = (field) => {
    if (field.startsWith("transitions")) setActive("transitions");
    else if (field.startsWith("defaults")) setActive("defaults");
    else if (field.startsWith("columns")) setActive("columns");
  };

  // Refetch the project list after a daemon-scope edit (enabled/ingress) so the switcher reflects it.
  const onProjectsChanged = () =>
    api
      .listProjects()
      .then((r) => setProjects(r.projects))
      .catch(() => {});

  if (bootError) {
    return (
      <div style={{ padding: 24 }}>
        <Banner tone="error" title={t("app.cannot_reach_title")}>
          {t("app.cannot_reach_body", { err: bootError })}
        </Banner>
      </div>
    );
  }
  if (authed === null)
    return <div style={{ padding: 24 }}>{t("common.loading")}</div>;
  if (authed === false)
    return <LoginScreen onSuccess={() => setAuthed(true)} />;
  if (!projects)
    return <div style={{ padding: 24 }}>{t("common.loading")}</div>;
  if (!projects.length) {
    return (
      <div style={{ padding: 24 }}>
        <Banner tone="error" title={t("app.no_board_title")}>
          {t("app.no_board_body")}
        </Banner>
      </div>
    );
  }

  const isDaemon = active === "daemon";
  const isProfiles = active === "profiles";
  const daemonScope = isDaemon || isProfiles;

  let content;
  if (isDaemon) {
    content = (
      <DaemonPanel
        projects={projects}
        selected={selected}
        onChanged={onProjectsChanged}
      />
    );
  } else if (isProfiles) {
    content = <ProfilesPanel />;
  } else if (active === "monitoring") {
    content = <MonitoringPanel project={selected} />;
  } else if (active === "board") {
    content = <BoardPanel project={selected} />;
  } else if (active === "issues") {
    content = <IssuesPanel project={selected} repo={currentRepo} />;
  } else if (error && !draft) {
    content = (
      <Banner tone="error" title={t("app.cannot_load_board")}>
        {error}
      </Banner>
    );
  } else if (!draft) {
    content = <div>{t("app.loading_board")}</div>;
  } else {
    const panels = {
      columns: (
        <ColumnsPanel
          draft={draft}
          update={update}
          dirty={dirty}
          project={selected}
          onSave={onSave}
          onValidate={onValidate}
          saving={saving}
        />
      ),
      transitions: (
        <TransitionsPanel
          draft={draft}
          update={update}
          findings={findings}
          project={selected}
          onSave={onSave}
          onValidate={onValidate}
          saving={saving}
          dirty={dirty}
        />
      ),
      defaults: <DefaultsPanel draft={draft} update={update} />,
      validation: <ValidationPanel findings={findings} onGoto={onGoto} />,
      yaml: <YamlPanel project={selected} />,
    };
    content = (
      <>
        {error && (
          <div style={{ marginBottom: 14 }}>
            <Banner tone="error" title={t("app.action_failed")}>
              {error}
            </Banner>
          </div>
        )}
        {panels[active]}
      </>
    );
  }

  return (
    <AppShell
      active={active}
      onNav={setActive}
      projects={projects}
      selected={selected}
      onSelect={setSelected}
      repo={currentRepo}
      errorCount={errorCount}
      dirty={dirty}
      saving={saving}
      onSave={onSave}
      onValidate={onValidate}
      onLogout={authEnabled ? onLogout : null}
      boardScope={!daemonScope}
    >
      {content}
    </AppShell>
  );
}
