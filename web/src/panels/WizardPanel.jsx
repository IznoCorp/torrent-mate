// First-run install wizard (bosun phase 5, DESIGN §10). A 4-step stepper that takes a fresh host
// from nothing to a running orchestrator: token → first project → board provisioning → PM2 bootstrap.
// It shows automatically when GET /api/admin/health reports zero projects (first run). Long steps run
// as jobs (POST returns {job_id}; we poll GET /api/ops/{id} to completion). The PM2 bootstrap is
// first-run-only and confirm-gated; it is DISABLED when GET /api/admin/daemon already lists allowlisted
// apps (the server also enforces this with a 409). Reuses the api.js helpers, the dir-browser server
// route, and the design-system primitives (Dialog, Banner, Button, Input). Spinner is a LOCAL
// component — the DS bundle exports no Spinner, so destructuring it yielded undefined → React #130.
import React from "react";
import * as api from "../api.js";
import Spinner from "../components/Spinner.jsx";
import { useT } from "../i18n/index.jsx";

const { Banner, Badge, KeyChip, Button, Dialog, Input } =
  window.KanbanMateDesignSystem_2463ad;

// Poll a job to completion. Resolves {ok, job} once terminal; rejects on timeout. Transient read
// errors are tolerated (keep polling) — mirrors the AdminPanel poller.
async function pollJob(jobId, attempts = 80) {
  const terminal = new Set(["succeeded", "done", "failed", "error"]);
  for (let i = 0; i < attempts; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    let job;
    try {
      job = await api.getOp(jobId);
    } catch {
      continue; // transient read error — keep polling
    }
    if (job && terminal.has(job.state)) {
      const ok = job.state === "succeeded" || job.state === "done";
      return { ok, job };
    }
  }
  throw new Error("timeout");
}

// The four steps, in order. `key` indexes the i18n labels under wizard.steps.*.
const STEPS = ["token", "project", "provision", "bootstrap"];

export default function WizardPanel({ onComplete }) {
  const { t } = useT();
  // 0..3 = the active step; 4 = the "setup complete" end state.
  const [step, setStep] = React.useState(0);
  // Per-step error (surfaced inline). Cleared on each new attempt.
  const [error, setError] = React.useState(null);
  // In-flight flag → disables the step's action button + shows a spinner.
  const [busy, setBusy] = React.useState(false);

  // Step 1 — token value.
  const [token, setToken] = React.useState("");
  // Step 2 — first project: mode + repo + the picked clone path or git URL. The registered project
  // id (resolved after the add job) drives step 3's provision call.
  const [mode, setMode] = React.useState("local"); // "local" | "clone"
  const [repo, setRepo] = React.useState("");
  const [pickedPath, setPickedPath] = React.useState("");
  const [gitUrl, setGitUrl] = React.useState("");
  const [projectId, setProjectId] = React.useState(null); // resolved node id for provision

  // PM2 bootstrap availability — disabled (and the 409 pre-empted) when allowlisted apps already
  // exist. We probe /api/admin/daemon once when the bootstrap step is reached.
  const [daemonApps, setDaemonApps] = React.useState(null); // [] | null
  const [confirmBootstrap, setConfirmBootstrap] = React.useState(false);

  React.useEffect(() => {
    if (STEPS[step] !== "bootstrap") return;
    api
      .getDaemon()
      // api.getDaemon() unwraps the route's {apps:[...]} envelope to the bare apps array.
      .then((d) => setDaemonApps(Array.isArray(d) ? d : []))
      .catch(() => setDaemonApps([]));
  }, [step]);
  const bootstrapAlreadyDone = !!(daemonApps && daemonApps.length > 0);

  // After a project is registered, resolve its node id so step 3 can provision it. The add job only
  // returns ok/fail; the registry is the source of truth for the new id.
  const resolveProjectId = React.useCallback(async (wantRepo) => {
    try {
      const r = await api.listProjects();
      const hit = (r.projects || []).find((p) => p.repo === wantRepo);
      return hit ? hit.project_id : null;
    } catch {
      return null;
    }
  }, []);

  // --- Step actions ---

  // Step 1: write the token, then advance.
  const submitToken = async () => {
    setError(null);
    setBusy(true);
    try {
      await api.wizardToken(token.trim());
      setStep(1);
    } catch (e) {
      setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  // Step 2: register the first project (clone/local), poll the add job, resolve its id, advance.
  const submitProject = async () => {
    setError(null);
    setBusy(true);
    try {
      const body =
        mode === "local"
          ? { mode: "local", repo: repo.trim(), path: pickedPath }
          : { mode: "clone", repo: repo.trim(), git_url: gitUrl.trim() };
      const { job_id } = await api.wizardProject(body);
      const { ok, job } = await pollJob(job_id);
      if (!ok) {
        setError(
          `${t("wizard.project_failed")}: ${job.stdout_tail || `exit ${job.exit_code != null ? job.exit_code : "?"}`}`,
        );
        return;
      }
      const id = await resolveProjectId(repo.trim());
      // The provision step (step 3) needs the resolved Project v2 node id. If resolution failed
      // (a transient listProjects error, or no registry entry matched the repo), DON'T advance to
      // provisioning with a null id — provision would then send the repo slug and 404 ("Unknown
      // project") one step later, a confusing place to surface the failure. Stop here with a clear
      // message at the point of failure; the operator can retry (re-resolution) from this step.
      if (id == null) {
        setError(t("wizard.project_resolve_failed"));
        return;
      }
      setProjectId(id);
      setStep(2);
    } catch (e) {
      if (e.message === "timeout") setError(t("wizard.job_timeout"));
      else setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  // Step 3: provision the GitHub board for the just-added project, poll, advance.
  const submitProvision = async () => {
    setError(null);
    setBusy(true);
    try {
      const { job_id } = await api.wizardProvision(projectId || repo.trim());
      const { ok, job } = await pollJob(job_id);
      if (!ok) {
        setError(
          `${t("wizard.provision_failed")}: ${job.stdout_tail || `exit ${job.exit_code != null ? job.exit_code : "?"}`}`,
        );
        return;
      }
      setStep(3);
    } catch (e) {
      if (e.message === "timeout") setError(t("wizard.job_timeout"));
      else setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  // Step 4: PM2 bootstrap (first-run-only, confirm-gated). Polls the job, then lands on the
  // "setup complete" end state.
  const runBootstrap = async () => {
    setConfirmBootstrap(false);
    setError(null);
    setBusy(true);
    try {
      const { job_id } = await api.wizardBootstrap();
      const { ok, job } = await pollJob(job_id);
      if (!ok) {
        setError(
          `${t("wizard.bootstrap_failed")}: ${job.stdout_tail || `exit ${job.exit_code != null ? job.exit_code : "?"}`}`,
        );
        return;
      }
      setStep(4);
    } catch (e) {
      if (e.message === "timeout") setError(t("wizard.job_timeout"));
      // 409 = apps already exist (first-run-only) — surface it and disable the step.
      else if (e.status === 409) {
        setDaemonApps([{ app: "exists" }]);
        setError(e.detail || e.message);
      } else setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  const localValid = repo.trim() && pickedPath;
  const cloneValid = repo.trim() && gitUrl.trim();

  return (
    <div
      style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: "32px 20px 64px",
        minHeight: "100%",
        boxSizing: "border-box",
      }}
    >
      <div style={{ textAlign: "center", marginBottom: 8 }}>
        <span
          style={{
            display: "inline-grid",
            placeItems: "center",
            width: 44,
            height: 44,
            borderRadius: "var(--radius-md)",
            background: "var(--primary)",
            color: "var(--primary-foreground)",
            fontFamily: "var(--font-mono)",
            fontWeight: 600,
            fontSize: 20,
          }}
        >
          [▸]
        </span>
      </div>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "var(--text-2xl)",
          fontWeight: 700,
          textAlign: "center",
          margin: "0 0 4px",
          color: "var(--foreground)",
        }}
      >
        {t("wizard.title")}
      </h1>
      <p
        style={{
          textAlign: "center",
          color: "var(--muted-foreground)",
          fontSize: 13.5,
          margin: "0 0 24px",
        }}
      >
        {t("wizard.subtitle")}
      </p>

      <Stepper step={step} t={t} />

      <div
        style={{
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-xs)",
          padding: 20,
          marginTop: 20,
        }}
      >
        {error && (
          <div style={{ marginBottom: 14 }}>
            <Banner
              tone="error"
              title={t("wizard.step_failed")}
              onDismiss={() => setError(null)}
            >
              {error}
            </Banner>
          </div>
        )}

        {step === 0 && (
          <StepBody
            title={t("wizard.token_title")}
            help={t("wizard.token_help")}
          >
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
                {t("wizard.token_label")}
              </span>
              <Input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={t("wizard.token_ph")}
                mono
              />
            </label>
            <Footer>
              <Button
                variant="primary"
                disabled={busy || !token.trim()}
                loading={busy}
                onClick={submitToken}
              >
                {t("wizard.next")}
              </Button>
            </Footer>
          </StepBody>
        )}

        {step === 1 && (
          <StepBody
            title={t("wizard.project_title")}
            help={t("wizard.project_help")}
          >
            <div style={{ display: "flex", gap: 6 }}>
              <Button
                size="sm"
                variant={mode === "local" ? "secondary" : "ghost"}
                onClick={() => setMode("local")}
              >
                {t("admin.onboard_tab_local")}
              </Button>
              <Button
                size="sm"
                variant={mode === "clone" ? "secondary" : "ghost"}
                onClick={() => setMode("clone")}
              >
                {t("admin.onboard_tab_clone")}
              </Button>
            </div>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
                {t("admin.onboard_repo_label")}
              </span>
              <Input
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                placeholder={t("admin.onboard_repo_ph")}
                mono
              />
            </label>
            {mode === "local" ? (
              <DirBrowser picked={pickedPath} onPick={setPickedPath} t={t} />
            ) : (
              <label
                style={{ display: "flex", flexDirection: "column", gap: 4 }}
              >
                <span
                  style={{ fontSize: 12, color: "var(--muted-foreground)" }}
                >
                  {t("admin.onboard_giturl_label")}
                </span>
                <Input
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  placeholder={t("admin.onboard_giturl_ph")}
                  mono
                />
              </label>
            )}
            <Footer onBack={() => setStep(0)} backLabel={t("common.back")}>
              <Button
                variant="primary"
                disabled={
                  busy || (mode === "local" ? !localValid : !cloneValid)
                }
                loading={busy}
                onClick={submitProject}
              >
                {busy ? t("wizard.registering") : t("wizard.next")}
              </Button>
            </Footer>
          </StepBody>
        )}

        {step === 2 && (
          <StepBody
            title={t("wizard.provision_title")}
            help={t("wizard.provision_help")}
          >
            <div
              style={{
                fontSize: 13,
                color: "var(--foreground)",
                display: "flex",
                alignItems: "center",
                gap: 8,
                flexWrap: "wrap",
              }}
            >
              <span>{t("wizard.provision_target")}</span>
              <KeyChip>{repo.trim() || "—"}</KeyChip>
            </div>
            <Footer onBack={() => setStep(1)} backLabel={t("common.back")}>
              <Button
                variant="primary"
                disabled={busy}
                loading={busy}
                onClick={submitProvision}
              >
                {busy ? t("wizard.provisioning") : t("wizard.provision_btn")}
              </Button>
            </Footer>
          </StepBody>
        )}

        {step === 3 && (
          <StepBody
            title={t("wizard.bootstrap_title")}
            help={t("wizard.bootstrap_help")}
          >
            {daemonApps == null ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  color: "var(--muted-foreground)",
                  fontSize: 13,
                }}
              >
                <Spinner />
                {t("common.loading")}
              </div>
            ) : bootstrapAlreadyDone ? (
              <Banner tone="info" title={t("wizard.bootstrap_done_title")}>
                {t("wizard.bootstrap_done_body")}
              </Banner>
            ) : (
              <div
                style={{
                  fontSize: 12.5,
                  color: "var(--muted-foreground)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                {["kanban-km", "kanban-km-serve", "kanban-km-config"].map(
                  (a) => (
                    <span
                      key={a}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Badge tone="neutral" size="sm">
                        {a}
                      </Badge>
                    </span>
                  ),
                )}
              </div>
            )}
            <Footer onBack={() => setStep(2)} backLabel={t("common.back")}>
              {bootstrapAlreadyDone ? (
                <Button variant="primary" onClick={() => setStep(4)}>
                  {t("wizard.finish")}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  disabled={busy || daemonApps == null}
                  loading={busy}
                  onClick={() => setConfirmBootstrap(true)}
                >
                  {busy ? t("wizard.bootstrapping") : t("wizard.bootstrap_btn")}
                </Button>
              )}
            </Footer>
          </StepBody>
        )}

        {step === 4 && (
          <StepBody title={t("wizard.done_title")} help={t("wizard.done_help")}>
            <div style={{ textAlign: "center", padding: "8px 0" }}>
              <Badge tone="accent" size="md">
                {t("wizard.done_badge")}
              </Badge>
            </div>
            <Footer>
              <Button
                variant="primary"
                onClick={() => onComplete && onComplete()}
              >
                {t("wizard.open_dashboard")}
              </Button>
            </Footer>
          </StepBody>
        )}
      </div>

      {/* PM2 bootstrap confirm — high-impact, first-run-only (DESIGN §10 step 4). */}
      <Dialog
        open={confirmBootstrap}
        onClose={busy ? undefined : () => setConfirmBootstrap(false)}
        width={460}
        title={t("wizard.confirm_bootstrap_title")}
        footer={
          <>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => setConfirmBootstrap(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button variant="danger" loading={busy} onClick={runBootstrap}>
              {t("wizard.confirm_bootstrap_apply")}
            </Button>
          </>
        }
      >
        <div style={{ color: "var(--foreground)", fontSize: 14 }}>
          {t("wizard.confirm_bootstrap_body")}
        </div>
      </Dialog>
    </div>
  );
}

// The numbered step rail across the top. The active step is highlighted; completed steps show a check.
function Stepper({ step, t }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        flexWrap: "wrap",
      }}
    >
      {STEPS.map((s, i) => {
        const done = step > i;
        const active = step === i;
        return (
          <React.Fragment key={s}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                padding: "5px 10px",
                borderRadius: "var(--radius-md)",
                background: active
                  ? "var(--sidebar-accent, var(--muted))"
                  : "transparent",
              }}
            >
              <span
                style={{
                  display: "inline-grid",
                  placeItems: "center",
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  fontSize: 12,
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  background: done
                    ? "var(--primary)"
                    : active
                      ? "var(--primary)"
                      : "var(--muted)",
                  color:
                    done || active
                      ? "var(--primary-foreground)"
                      : "var(--muted-foreground)",
                }}
              >
                {done ? "✓" : i + 1}
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: active ? 600 : 500,
                  color: active
                    ? "var(--foreground)"
                    : "var(--muted-foreground)",
                  whiteSpace: "nowrap",
                }}
              >
                {t(`wizard.steps.${s}`)}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span
                style={{
                  width: 16,
                  height: 1,
                  background: "var(--border)",
                  flex: "none",
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// A step body — title + help blurb + the step's controls.
function StepBody({ title, help, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--text-lg)",
            fontWeight: 600,
            margin: "0 0 4px",
            color: "var(--foreground)",
          }}
        >
          {title}
        </h2>
        <p
          style={{
            fontSize: 12.5,
            color: "var(--muted-foreground)",
            margin: 0,
          }}
        >
          {help}
        </p>
      </div>
      {children}
    </div>
  );
}

// The step footer — optional back link on the left, the primary action(s) on the right.
function Footer({ onBack, backLabel, children }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: onBack ? "space-between" : "flex-end",
        gap: 8,
        marginTop: 6,
      }}
    >
      {onBack && (
        <Button variant="ghost" size="sm" onClick={onBack}>
          {backLabel}
        </Button>
      )}
      <div style={{ display: "flex", gap: 8 }}>{children}</div>
    </div>
  );
}

// Directory browser confined server-side to ONBOARD_BASE_DIRS (GET /api/admin/browse). Same behaviour
// as the AdminPanel onboarding browser — click into a sub-folder to descend, ".." ascends, and the
// currently-listed path IS the pickable clone dir. Reuses the admin.onboard_browse_* i18n keys.
function DirBrowser({ picked, onPick, t }) {
  const [path, setPath] = React.useState("");
  const [entries, setEntries] = React.useState(null); // [] | null
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);

  const browse = React.useCallback(async (target) => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.browseDir(target || undefined);
      setPath(r.path);
      setEntries((r.entries || []).filter((e) => e.is_dir));
    } catch (e) {
      setErr(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  }, []);

  React.useEffect(() => {
    browse("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const parentOf = (p) => {
    const i = p.replace(/\/+$/, "").lastIndexOf("/");
    return i > 0 ? p.slice(0, i) : p;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
        {t("admin.onboard_browse_label")}
      </span>
      {err && (
        <Banner tone="error" title={t("admin.onboard_browse_failed")}>
          {err}
        </Banner>
      )}
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          background: "var(--surface-app, var(--background))",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "7px 10px",
            borderBottom: "1px solid var(--border)",
            flexWrap: "wrap",
          }}
        >
          <KeyChip>{path || "…"}</KeyChip>
          {busy && <Spinner />}
        </div>
        <div style={{ maxHeight: 200, overflow: "auto" }}>
          <button
            type="button"
            onClick={() => browse(parentOf(path))}
            disabled={busy || !path}
            style={dirRowStyle}
          >
            {t("admin.onboard_browse_up")}
          </button>
          {entries == null ? (
            <div
              style={{
                padding: "8px 10px",
                fontSize: 12,
                color: "var(--muted-foreground)",
              }}
            >
              {t("admin.onboard_browse_loading")}
            </div>
          ) : entries.length === 0 ? (
            <div
              style={{
                padding: "8px 10px",
                fontSize: 12,
                color: "var(--muted-foreground)",
              }}
            >
              {t("admin.onboard_browse_empty")}
            </div>
          ) : (
            entries.map((e) => (
              <button
                key={e.name}
                type="button"
                onClick={() => browse(`${path.replace(/\/+$/, "")}/${e.name}`)}
                disabled={busy}
                style={dirRowStyle}
              >
                {"\u{1F4C1}"} {e.name}
              </button>
            ))
          )}
        </div>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <Button
          variant="secondary"
          size="sm"
          disabled={busy || !path}
          onClick={() => onPick(path)}
        >
          {t("admin.onboard_browse_pick_btn")}
        </Button>
        <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
          {picked
            ? t("admin.onboard_browse_pick", { path: picked })
            : t("admin.onboard_browse_none")}
        </span>
      </div>
    </div>
  );
}

const dirRowStyle = {
  display: "block",
  width: "100%",
  textAlign: "left",
  padding: "7px 10px",
  border: "none",
  borderBottom: "1px solid var(--border)",
  background: "transparent",
  color: "var(--foreground)",
  fontFamily: "var(--font-mono)",
  fontSize: 12.5,
  cursor: "pointer",
};
