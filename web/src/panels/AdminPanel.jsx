// Admin / Ops panel — host-wide health dashboard (bosun phase 1) + daemon control / PAUSE /
// log tail (bosun phase 2). Polls /api/admin/health, /api/admin/version, /api/ops, /api/admin/daemon
// and /api/admin/pause. Daemon-scoped (host-wide, not per-board) so it lives in the daemon nav group.
// Mutating actions (daemon control, PAUSE) carry the X-KM-CSRF header (wired once in api.js).
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import Spinner from "../components/Spinner.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

// Spinner is a local component (../components/Spinner.jsx) — the DS bundle exports no Spinner
// primitive; destructuring it from the DS global yielded `undefined` → React #130 (blank page).
const { Banner, Badge, KeyChip, Button, Dialog, Input } =
  window.KanbanMateDesignSystem_2463ad;

// PM2 UI apps (the config servers) — standalone start/stop/restart is refused server-side (D1);
// they are only ever bounced as the tail of a redeploy. Their mutate buttons are disabled in the UI.
const UI_APP_NAMES = new Set(["kanban-km-config", "kanban-staging-config"]);
const MUTATE_ACTIONS = ["start", "stop", "restart"];

// Poll `fn` every `ms` while the tab is visible; runs once immediately.
function usePoll(fn, ms) {
  React.useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") fn();
    };
    tick();
    const id = setInterval(tick, ms);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

// A boolean chip — green/accent for true, red for the alarm case (e.g. daemon dead).
function BoolChip({ ok, label }) {
  return (
    <Badge tone={ok ? "accent" : "red"} size="sm">
      {label}
    </Badge>
  );
}

export default function AdminPanel() {
  const { t } = useT();
  // Drives the mobile-first layout branches below: rows stack vertically, action buttons go
  // full-width for tap targets, and multi-column grids collapse to a single column (DESIGN §3).
  const isMobile = useIsMobile();
  const [health, setHealth] = React.useState(null);
  const [version, setVersion] = React.useState(null);
  const [ops, setOps] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [daemon, setDaemon] = React.useState(null);
  const [pause, setPauseState] = React.useState(null); // {active:bool} | null
  // Transient control feedback (one Banner): {tone, msg}.
  const [notice, setNotice] = React.useState(null);
  // Pending confirm: {kind:"restart"|"pause_on", app?, run:()=>Promise} | null.
  const [confirm, setConfirm] = React.useState(null);
  // Apps with an in-flight control job → buttons disabled + spinner.
  const [busyApps, setBusyApps] = React.useState({});
  // Redeploy progress: {target, phase:"running"|"bouncing"|"done"|"failed", log:string} | null.
  // `phase==="bouncing"` is the tolerated window where the config server is restarting and fetches
  // are EXPECTED to fail — we surface "reconnecting…" rather than an error (DESIGN §8).
  const [redeploy, setRedeploy] = React.useState(null);
  const redeployBusy =
    !!redeploy && redeploy.phase !== "done" && redeploy.phase !== "failed";
  // Registered projects (the deregister list); polled so a fresh add/remove shows up.
  const [projects, setProjects] = React.useState(null); // [] | null
  // In-flight add job → disables the add buttons + drives a status badge.
  const [adding, setAdding] = React.useState(false);
  // Graceful UI-app restart: {app, phase:"running"|"bouncing"|"done"|"failed"} | null. Like the
  // redeploy bounce, `phase==="bouncing"` is the tolerated window where (for the app serving THIS
  // page) fetches are expected to fail — we show "reconnecting…" and resolve when it is back online.
  const [uiRestart, setUiRestart] = React.useState(null);

  usePoll(
    () =>
      api
        .getAdminHealth()
        .then(setHealth)
        .catch((e) => setError(e.message)),
    5000,
  );
  usePoll(
    () =>
      api
        .getAdminVersion()
        .then(setVersion)
        .catch(() => {}),
    30000,
  );
  usePoll(
    () =>
      api
        .listOps()
        .then((r) => setOps(r.jobs || []))
        .catch(() => {}),
    5000,
  );
  usePoll(
    () =>
      api
        .getDaemon()
        .then(setDaemon)
        .catch(() => {}),
    5000,
  );
  usePoll(
    () =>
      api
        .getPause()
        .then(setPauseState)
        .catch(() => {}),
    5000,
  );
  const refreshProjects = React.useCallback(
    () =>
      api
        .listProjects()
        .then((r) => setProjects((r && r.projects) || []))
        // 503 = no project registered → show the empty state rather than a perpetual spinner.
        .catch((e) => setProjects(e.status === 503 ? [] : (p) => p)),
    [],
  );
  usePoll(refreshProjects, 10000);

  // Poll a control job to completion, then surface succeeded/failed and refresh the daemon rows.
  const pollJob = React.useCallback(
    async (app, jobId) => {
      const terminal = new Set(["succeeded", "done", "failed", "error"]);
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        let job;
        try {
          job = await api.getOp(jobId);
        } catch {
          continue; // transient read error — keep polling
        }
        if (job && terminal.has(job.state)) {
          const ok = job.state === "succeeded" || job.state === "done";
          setNotice({
            tone: ok ? "success" : "error",
            msg: ok
              ? t("admin.ctl_job_ok", { app })
              : t("admin.ctl_job_failed", {
                  app,
                  code: job.exit_code != null ? job.exit_code : "?",
                }),
          });
          api
            .getDaemon()
            .then(setDaemon)
            .catch(() => {});
          return;
        }
      }
      setNotice({ tone: "error", msg: t("admin.ctl_job_timeout", { app }) });
    },
    [t],
  );

  // Fire a daemon control action → job, then poll it (with per-app busy gating).
  const runDaemonAction = React.useCallback(
    async (app, action) => {
      setBusyApps((b) => ({ ...b, [app]: true }));
      setNotice(null);
      try {
        const { job_id } = await api.daemonAction(app, action);
        await pollJob(app, job_id);
      } catch (e) {
        setNotice({ tone: "error", msg: e.message });
      } finally {
        setBusyApps((b) => ({ ...b, [app]: false }));
      }
    },
    [pollJob],
  );

  // restart requires explicit confirm; start/stop fire directly.
  const onDaemonAction = (app, action) => {
    if (action === "restart") {
      setConfirm({
        kind: "restart",
        app,
        run: () => runDaemonAction(app, action),
      });
    } else {
      runDaemonAction(app, action);
    }
  };

  // Graceful restart of a UI config server (Option A). The POST spawns a DETACHED `pm2 restart`
  // job that survives this server's own death; we then tolerate the bounce and reconnect by polling
  // the daemon list until the app is back online with a FRESH pid (or a bumped restart count). Works
  // whether we are restarting the app serving THIS page (fetches fail mid-bounce — tolerated) or the
  // other UI app (fetches keep working — we just detect the pid flip). Mirrors the redeploy bounce,
  // but the liveness signal is the process identity (no build-SHA flip on a plain restart).
  const runUiRestart = React.useCallback(
    async (app) => {
      // Set "running" FIRST (synchronously, before any await) so the row's button disables before
      // the confirm modal closes — closes the double-click window without holding the modal open.
      setNotice(null);
      setUiRestart({ app, phase: "running" });
      // Snapshot the pre-restart identity from a FRESH daemon read (not the possibly-stale polled
      // `daemon` closure): a reliable baseline rules out a false "done" when the closure lacked the
      // app / its pid. Tolerate a read failure — detection below still works off the restart count.
      let beforePid = null;
      let beforeRestarts = 0;
      try {
        const snap = await api.getDaemon();
        const b = snap.find((d) => d.app === app);
        if (b) {
          beforePid = b.pid ?? null;
          beforeRestarts = b.restarts ?? 0;
        }
      } catch {
        // Couldn't snapshot — proceed; the pid-flip OR restart-bump check stays conservative.
      }
      let jobId;
      try {
        ({ job_id: jobId } = await api.uiRestart(app));
      } catch (e) {
        setUiRestart({ app, phase: "failed" });
        setNotice({ tone: "error", msg: e.detail || e.message });
        return;
      }
      // The detached job now runs `pm2 restart` — the server may die under us at any moment.
      setUiRestart({ app, phase: "bouncing" });
      const deadline = Date.now() + 90 * 1000; // 90s cap — a pm2 restart is quick; generous for slow hosts
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000));
        // Fast-fail: the detached job's record is durable on disk and survives the bounce, so an
        // explicit failure surfaces with its log tail instead of waiting out the whole deadline.
        try {
          const job = await api.getOp(jobId);
          if (job && (job.state === "failed" || job.state === "error")) {
            setUiRestart({ app, phase: "failed" });
            setNotice({
              tone: "error",
              msg: job.stdout_tail || t("admin.ui_restart_failed", { app }),
            });
            return;
          }
        } catch {
          // Server bouncing (or transient) — ignore and try the liveness probe below.
        }
        // Success: the app is back online with a brand-new process. Confirmed by EITHER a pid flip
        // (definitive) OR a bumped restart count (covers the rare pid reuse). Against the fresh
        // baseline above, the restart-count clause is a true signal — it only bumps on a real
        // restart — so neither a reused pid nor a missing baseline pid yields a false "done".
        try {
          const apps = await api.getDaemon();
          const cur = apps.find((d) => d.app === app);
          if (cur && cur.status === "online" && cur.pid != null) {
            const flipped =
              (beforePid != null && cur.pid !== beforePid) ||
              (cur.restarts ?? 0) > beforeRestarts;
            if (flipped) {
              setDaemon(apps);
              setUiRestart({ app, phase: "done" });
              return;
            }
          }
        } catch {
          // Expected while the app serving this page is down — keep waiting, stay "bouncing".
        }
      }
      // Never confirmed it came back within the deadline. Mark failed (not done) — the detached
      // job's real outcome is still in the jobs ledger below for the operator to check.
      setUiRestart({ app, phase: "failed" });
      setNotice({
        tone: "error",
        msg: t("admin.ui_restart_reconnect_slow", { app }),
      });
    },
    // No `daemon` dep: the baseline is read fresh inside, so the callback need not be recreated on
    // every 5s daemon poll.
    [t],
  );

  // Graceful restart is high-impact (it bounces a config server) → confirm-gated, like restart.
  const onGracefulRestart = (app) => {
    setConfirm({
      kind: "ui_restart",
      app,
      // Fire-and-forget (no returned promise) so the confirm modal closes immediately; the bounce +
      // reconnect can take tens of seconds and shows inline on the row via `uiRestart`, not as a
      // modal held open the whole time. Safe: runUiRestart wraps every await, so the promise never
      // rejects (no unhandled rejection), and it sets phase:"running" synchronously before the modal
      // closes, so the row button is already disabled (no double-fire). On React 18 a late setState
      // after an unmount is a silent no-op, so an in-flight restart needs no mounted-ref guard.
      run: () => {
        runUiRestart(app);
      },
    });
  };

  // Flip the PAUSE kill-switch. Turning it ON requires confirm (it stops all launches).
  const flipPause = React.useCallback(async (active) => {
    setNotice(null);
    try {
      const r = await api.setPause(active);
      setPauseState(r);
    } catch (e) {
      setNotice({ tone: "error", msg: e.message });
    }
  }, []);
  const onTogglePause = () => {
    const next = !(pause && pause.active);
    if (next) {
      setConfirm({ kind: "pause_on", run: () => flipPause(true) });
    } else {
      flipPause(false);
    }
  };

  // Drive a redeploy: POST → stream the job log → tolerate the config-server bounce → reconnect
  // when the SERVED build SHA actually flips (the deploy script stamps it into webui/BUILD_COMMIT;
  // /api/admin/version exposes it as `build`). We capture the served `build` BEFORE the redeploy and
  // resolve "done" only once it changes — a meaningful confirmation the new code is live, unlike the
  // old semver-vs-SHA `local === remote` check, which could never be true so every redeploy reported
  // "done" via the timeout fallback (masking a failed/stale bounce). If the build never flips within
  // the deadline we mark the bounce "failed" rather than falsely "done". Every fetch is wrapped so a
  // transient error mid-bounce never throws out of the loop — it just means "still bouncing".
  const runRedeploy = React.useCallback(
    async (target) => {
      setNotice(null);
      setRedeploy({ target, phase: "running", log: "" });
      // Snapshot the currently-served build SHA so we can detect when the bounce serves new code.
      // null = couldn't read it (we then fall back to "build is known and matches remote").
      let beforeBuild = null;
      try {
        const v0 = await api.getAdminVersion();
        beforeBuild = v0 && v0.build ? v0.build : null;
      } catch {
        // No baseline — the reconnect loop still resolves on build===remote (build caught up).
      }
      let jobId;
      try {
        const r = await api.redeploy(target);
        jobId = r.job_id;
      } catch (e) {
        setRedeploy({ target, phase: "failed", log: e.message });
        return;
      }
      // Phase 1 — stream the job log until the deploy script itself ends or the server starts to
      // bounce (fetch begins to fail). Whichever comes first flips us into the reconnect phase.
      const deadline = Date.now() + 5 * 60 * 1000; // 5 min cap for the whole redeploy
      let bouncing = false;
      while (Date.now() < deadline && !bouncing) {
        await new Promise((r) => setTimeout(r, 1500));
        let job;
        try {
          job = await api.getOp(jobId);
        } catch {
          // The config server is bouncing (or a transient blip) — switch to reconnect mode.
          bouncing = true;
          break;
        }
        if (job) {
          const tail = job.stdout_tail || "";
          if (job.state === "failed" || job.state === "error") {
            setRedeploy({ target, phase: "failed", log: tail });
            return;
          }
          const done = job.state === "succeeded" || job.state === "done";
          // A finished job still means the config server is about to bounce as the script tail.
          setRedeploy({
            target,
            phase: done ? "bouncing" : "running",
            log: tail,
          });
          if (done) {
            bouncing = true;
            break;
          }
        }
      }
      // Phase 2 — reconnect. The config server is restarting; poll the version endpoint and treat
      // every fetch error as "still bouncing". Done only when the SERVED build SHA confirms the new
      // code is live: either it changed from the pre-redeploy snapshot, or (no snapshot) it caught up
      // to origin/main (build === remote, both real SHAs). This is a signal that can actually flip.
      setRedeploy((s) => ({
        ...(s || { target, log: "" }),
        phase: "bouncing",
      }));
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const v = await api.getAdminVersion();
          const build = v && v.build ? v.build : null;
          const confirmed =
            build && build !== "unknown"
              ? beforeBuild
                ? build !== beforeBuild
                : v.remote && v.remote !== "unknown" && build === v.remote
              : false;
          if (confirmed) {
            setVersion(v);
            setRedeploy((s) => ({
              ...(s || { target, log: "" }),
              phase: "done",
            }));
            return;
          }
        } catch {
          // Expected during the bounce — keep waiting, stay in "bouncing".
        }
      }
      // Timed out without confirming the served build flipped. The bounce is UNCONFIRMED — it may
      // have failed, never come back, or come back serving the OLD build. Mark it "failed" (not
      // "done") so an unconfirmed bounce is never falsely reported as a successful redeploy.
      setRedeploy((s) => ({ ...(s || { target, log: "" }), phase: "failed" }));
      setNotice({ tone: "error", msg: t("admin.redeploy_reconnect_slow") });
    },
    [t],
  );

  // High-impact — both targets require explicit confirm (DESIGN §8).
  const onRedeploy = (target) => {
    setConfirm({ kind: "redeploy", target, run: () => runRedeploy(target) });
  };

  // Drive an add-project job (local or clone): POST returns {job_id}; poll getOp to completion and
  // surface succeeded/failed. The 422 (bad path / bad git URL) is thrown by the POST itself and
  // surfaced inline by the caller; here we only own the job lifecycle once the job exists.
  const runAddProject = React.useCallback(
    async (repo, doPost) => {
      setNotice(null);
      setAdding(true);
      try {
        const { job_id } = await doPost();
        const terminal = new Set(["succeeded", "done", "failed", "error"]);
        for (let i = 0; i < 80; i++) {
          await new Promise((r) => setTimeout(r, 1500));
          let job;
          try {
            job = await api.getOp(job_id);
          } catch {
            continue; // transient read error — keep polling
          }
          if (job && terminal.has(job.state)) {
            const ok = job.state === "succeeded" || job.state === "done";
            setNotice({
              tone: ok ? "success" : "error",
              msg: ok
                ? t("admin.onboard_add_ok", { repo })
                : `${t("admin.onboard_add_failed")}: ${job.stdout_tail || `exit ${job.exit_code != null ? job.exit_code : "?"}`}`,
            });
            refreshProjects();
            return;
          }
        }
        setNotice({ tone: "info", msg: t("admin.onboard_add_timeout") });
      } catch (e) {
        // 422 (bad path / bad URL) and any POST error land here — surface verbatim.
        setNotice({
          tone: "error",
          msg: `${t("admin.onboard_add_failed")}: ${e.detail || e.message}`,
        });
      } finally {
        setAdding(false);
      }
    },
    [t, refreshProjects],
  );

  // Deregister a project (confirm-gated). The 409 "live agent" refusal is surfaced inline, never a
  // crash; on success refresh the registered list.
  const runRemoveProject = React.useCallback(
    async (p) => {
      setNotice(null);
      try {
        await api.removeProject(p.project_id);
        setNotice({
          tone: "success",
          msg: t("admin.onboard_remove_ok", { repo: p.repo }),
        });
        refreshProjects();
      } catch (e) {
        setNotice({
          tone: "error",
          msg: `${t("admin.onboard_remove_failed")}: ${e.detail || e.message}`,
        });
      }
    },
    [t, refreshProjects],
  );
  const onRemoveProject = (p) => {
    setConfirm({
      kind: "remove_project",
      repo: p.repo,
      run: () => runRemoveProject(p),
    });
  };

  if (error && !health)
    return (
      <Banner tone="error" title={t("admin.intro_title")}>
        {error}
      </Banner>
    );

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <PageIntro title={t("admin.intro_title")} scope="daemon">
        {t("admin.intro_body")}
      </PageIntro>

      {/* version badge + global flags strip */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 10,
          marginBottom: 16,
        }}
      >
        <VersionBadge version={version} t={t} />
        {health && (
          <>
            <BoolChip
              ok={!health.pause_active}
              label={
                health.pause_active
                  ? t("admin.flag_paused")
                  : t("admin.flag_active")
              }
            />
            <BoolChip
              ok={health.session_secret_pinned}
              label={
                health.session_secret_pinned
                  ? t("admin.flag_secret_pinned")
                  : t("admin.flag_secret_random")
              }
            />
            <Badge tone="blue" size="sm">
              {t("admin.flag_agents_waiting", {
                n: health.agents_waiting ?? 0,
              })}
            </Badge>
          </>
        )}
      </div>

      {/* transient control feedback */}
      {notice && (
        <div style={{ marginBottom: 14 }}>
          <Banner
            tone={notice.tone}
            title={t("admin.ctl_notice_title")}
            onDismiss={() => setNotice(null)}
          >
            {notice.msg}
          </Banner>
        </div>
      )}

      {/* global kill-switch (PAUSE) */}
      <SectionLabel>{t("admin.section_pause")}</SectionLabel>
      <PauseControl
        pause={pause}
        onToggle={onTogglePause}
        isMobile={isMobile}
        t={t}
      />

      {/* daemon control + log tail */}
      <SectionLabel>{t("admin.section_daemon")}</SectionLabel>
      <DaemonList
        daemon={daemon}
        busyApps={busyApps}
        onAction={onDaemonAction}
        onGracefulRestart={onGracefulRestart}
        uiRestart={uiRestart}
        isMobile={isMobile}
        t={t}
      />

      {/* redeploy from main (prod / staging) — high-impact, confirm-gated, reconnects post-bounce */}
      <SectionLabel>{t("admin.section_redeploy")}</SectionLabel>
      <RedeployControl
        redeploy={redeploy}
        busy={redeployBusy}
        onRedeploy={onRedeploy}
        isMobile={isMobile}
        t={t}
      />

      {/* project onboarding — add local/clone + guarded remove */}
      <SectionLabel>{t("admin.section_onboard")}</SectionLabel>
      <OnboardingControl
        projects={projects}
        adding={adding}
        onAddLocal={(repo, path) =>
          runAddProject(repo, () => api.addProjectLocal(repo, path))
        }
        onAddClone={(repo, gitUrl) =>
          runAddProject(repo, () => api.addProjectClone(repo, gitUrl))
        }
        onRemove={onRemoveProject}
        isMobile={isMobile}
        t={t}
      />

      {/* per-project health cards */}
      <SectionLabel>{t("admin.section_health")}</SectionLabel>
      {!health ? (
        <div style={{ padding: 16, color: "var(--muted-foreground)" }}>
          {t("common.loading")}
        </div>
      ) : (health.projects || []).length === 0 ? (
        <div style={{ padding: 16, color: "var(--muted-foreground)" }}>
          {t("admin.no_projects")}
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            // Phones: one card per row (minmax(280px,…) can overflow the narrowest viewports).
            gridTemplateColumns: isMobile
              ? "1fr"
              : "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 12,
            marginBottom: 22,
          }}
        >
          {health.projects.map((p) => (
            <ProjectCard key={p.project_id} p={p} t={t} />
          ))}
        </div>
      )}

      {/* recent jobs ledger */}
      <SectionLabel>{t("admin.section_jobs")}</SectionLabel>
      <JobsList ops={ops} isMobile={isMobile} t={t} />

      {/* confirm modal for destructive actions (restart, PAUSE-on) */}
      <ConfirmDialog confirm={confirm} onClose={() => setConfirm(null)} t={t} />
    </div>
  );
}

// Confirm modal — gates restart (a daemon bounce) and PAUSE-on (the kill-switch). Reuses the
// design-system Dialog (same primitive as SyncBoardDialog). On confirm, runs the deferred action.
function ConfirmDialog({ confirm, onClose, t }) {
  const [busy, setBusy] = React.useState(false);
  if (!confirm) return null;
  const isPause = confirm.kind === "pause_on";
  const isRedeploy = confirm.kind === "redeploy";
  const isRemove = confirm.kind === "remove_project";
  const isUiRestart = confirm.kind === "ui_restart";
  const title = isPause
    ? t("admin.confirm_pause_title")
    : isRedeploy
      ? t("admin.confirm_redeploy_title", { target: confirm.target })
      : isRemove
        ? t("admin.confirm_remove_title")
        : isUiRestart
          ? t("admin.confirm_ui_restart_title", { app: confirm.app })
          : t("admin.confirm_restart_title");
  const body = isPause
    ? t("admin.confirm_pause_body")
    : isRedeploy
      ? t("admin.confirm_redeploy_body", { target: confirm.target })
      : isRemove
        ? t("admin.confirm_remove_body", { repo: confirm.repo })
        : isUiRestart
          ? t("admin.confirm_ui_restart_body", { app: confirm.app })
          : t("admin.confirm_restart_body", { app: confirm.app });
  const run = async () => {
    setBusy(true);
    try {
      await confirm.run();
    } finally {
      setBusy(false);
      onClose();
    }
  };
  return (
    <Dialog
      open={true}
      onClose={busy ? undefined : onClose}
      width={460}
      title={title}
      footer={
        <>
          <Button variant="ghost" disabled={busy} onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" loading={busy} onClick={run}>
            {isPause
              ? t("admin.confirm_pause_apply")
              : isRedeploy
                ? t("admin.confirm_redeploy_apply")
                : isRemove
                  ? t("admin.confirm_remove_apply")
                  : isUiRestart
                    ? t("admin.confirm_ui_restart_apply")
                    : t("admin.confirm_restart_apply")}
          </Button>
        </>
      }
    >
      <div style={{ color: "var(--foreground)", fontSize: 14 }}>{body}</div>
    </Dialog>
  );
}

// Global PAUSE kill-switch toggle. Reads GET /api/admin/pause; the button flips it (POST). When
// active, a red banner makes the kill-switch state unmistakable.
function PauseControl({ pause, onToggle, isMobile, t }) {
  if (pause == null)
    return (
      <div style={{ padding: 16, color: "var(--muted-foreground)" }}>
        {t("common.loading")}
      </div>
    );
  const active = !!pause.active;
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
        padding: 14,
        marginBottom: 22,
        display: "flex",
        // Mobile: stack badge + help over a full-width button so the help text is readable and the
        // toggle is a comfortable tap target instead of being squeezed at the end of a wrapped row.
        flexDirection: isMobile ? "column" : "row",
        alignItems: isMobile ? "stretch" : "center",
        gap: 12,
        flexWrap: "wrap",
      }}
    >
      <Badge tone={active ? "red" : "accent"} size="sm">
        {active ? t("admin.flag_paused") : t("admin.flag_active")}
      </Badge>
      <span
        style={{
          flex: 1,
          minWidth: 0,
          fontSize: 12.5,
          color: "var(--muted-foreground)",
        }}
      >
        {t("admin.pause_help")}
      </span>
      <Button
        variant={active ? "secondary" : "danger"}
        size={isMobile ? "md" : "sm"}
        fullWidth={isMobile}
        onClick={onToggle}
      >
        {active ? t("admin.pause_resume") : t("admin.pause_activate")}
      </Button>
    </div>
  );
}

// Redeploy-from-main control — two confirm-gated buttons (prod / staging). While a redeploy runs,
// it streams the job log into a scrollable <pre> and, during the config-server bounce, shows a
// "reconnecting…" status instead of an error. Resolves when the new build answers (version flip).
function RedeployControl({ redeploy, busy, onRedeploy, isMobile, t }) {
  const phase = redeploy ? redeploy.phase : null;
  // Status line under the buttons reflects the lifecycle phase.
  let statusMsg = null;
  let statusTone = "blue";
  if (phase === "running")
    statusMsg = t("admin.redeploy_running", { target: redeploy.target });
  else if (phase === "bouncing") {
    statusMsg = t("admin.redeploy_reconnecting", { target: redeploy.target });
    statusTone = "amber";
  } else if (phase === "done") {
    statusMsg = t("admin.redeploy_done", { target: redeploy.target });
    statusTone = "accent";
  } else if (phase === "failed") {
    statusMsg = t("admin.redeploy_failed", { target: redeploy.target });
    statusTone = "red";
  }
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
        padding: 14,
        marginBottom: 22,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <div
        style={{
          display: "flex",
          // Mobile: help text on its own line, then the two targets as full-width stacked buttons.
          flexDirection: isMobile ? "column" : "row",
          alignItems: isMobile ? "stretch" : "center",
          gap: isMobile ? 8 : 12,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 12.5,
            color: "var(--muted-foreground)",
          }}
        >
          {t("admin.redeploy_help")}
        </span>
        <Button
          variant="secondary"
          size={isMobile ? "md" : "sm"}
          fullWidth={isMobile}
          disabled={busy}
          onClick={() => onRedeploy("staging")}
        >
          {t("admin.redeploy_staging")}
        </Button>
        <Button
          variant="danger"
          size={isMobile ? "md" : "sm"}
          fullWidth={isMobile}
          disabled={busy}
          onClick={() => onRedeploy("prod")}
        >
          {t("admin.redeploy_prod")}
        </Button>
      </div>
      {statusMsg && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          <Badge tone={statusTone} size="sm">
            {statusMsg}
          </Badge>
          {(phase === "running" || phase === "bouncing") && <Spinner />}
        </div>
      )}
      {redeploy && redeploy.log && (
        <pre
          style={{
            margin: 0,
            maxHeight: 280,
            overflow: "auto",
            background: "var(--surface-app, var(--background))",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: 10,
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            lineHeight: 1.5,
            color: "var(--muted-foreground)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
          }}
        >
          {redeploy.log}
        </pre>
      )}
    </div>
  );
}

// Project onboarding — two add modes (local folder via the /api/admin/browse dir-browser, or git
// URL clone) plus the registered-projects list with a confirm-gated remove. The 422 (bad path / bad
// URL) and the 409 (live-agent) refusals surface in the shared notice Banner above — never a crash.
function OnboardingControl({
  projects,
  adding,
  onAddLocal,
  onAddClone,
  onRemove,
  isMobile,
  t,
}) {
  const [tab, setTab] = React.useState("local"); // "local" | "clone"
  const [repo, setRepo] = React.useState("");
  const [pickedPath, setPickedPath] = React.useState("");
  const [gitUrl, setGitUrl] = React.useState("");

  const cardStyle = {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-lg)",
    boxShadow: "var(--shadow-xs)",
    padding: 14,
    marginBottom: 22,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  };

  const localValid = repo.trim() && pickedPath;
  const cloneValid = repo.trim() && gitUrl.trim();

  return (
    <div style={cardStyle}>
      <span style={{ fontSize: 12.5, color: "var(--muted-foreground)" }}>
        {t("admin.onboard_help")}
      </span>

      {/* mode tabs */}
      <div style={{ display: "flex", gap: 6 }}>
        <Button
          size="sm"
          variant={tab === "local" ? "secondary" : "ghost"}
          onClick={() => setTab("local")}
        >
          {t("admin.onboard_tab_local")}
        </Button>
        <Button
          size="sm"
          variant={tab === "clone" ? "secondary" : "ghost"}
          onClick={() => setTab("clone")}
        >
          {t("admin.onboard_tab_clone")}
        </Button>
      </div>

      {/* shared repo (owner/name) field */}
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

      {tab === "local" ? (
        <>
          <DirBrowser
            picked={pickedPath}
            onPick={setPickedPath}
            isMobile={isMobile}
            t={t}
          />
          <div
            style={{
              display: "flex",
              justifyContent: isMobile ? "stretch" : "flex-end",
            }}
          >
            <Button
              variant="primary"
              size={isMobile ? "md" : "sm"}
              fullWidth={isMobile}
              disabled={adding || !localValid}
              loading={adding}
              onClick={() => onAddLocal(repo.trim(), pickedPath)}
            >
              {adding
                ? t("admin.onboard_adding", { repo: repo.trim() })
                : t("admin.onboard_add_local")}
            </Button>
          </div>
        </>
      ) : (
        <>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
              {t("admin.onboard_giturl_label")}
            </span>
            <Input
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              placeholder={t("admin.onboard_giturl_ph")}
              mono
            />
          </label>
          <div
            style={{
              display: "flex",
              justifyContent: isMobile ? "stretch" : "flex-end",
            }}
          >
            <Button
              variant="primary"
              size={isMobile ? "md" : "sm"}
              fullWidth={isMobile}
              disabled={adding || !cloneValid}
              loading={adding}
              onClick={() => onAddClone(repo.trim(), gitUrl.trim())}
            >
              {adding
                ? t("admin.onboard_adding", { repo: repo.trim() })
                : t("admin.onboard_add_clone")}
            </Button>
          </div>
        </>
      )}

      {/* registered projects — confirm-gated remove per row */}
      <div style={{ height: 1, background: "var(--border)" }} />
      <SectionLabel>{t("admin.onboard_registered")}</SectionLabel>
      {projects == null ? (
        <div style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          {t("common.loading")}
        </div>
      ) : projects.length === 0 ? (
        <div style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          {t("admin.onboard_no_registered")}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {projects.map((p) => (
            <div
              key={p.project_id}
              style={{
                display: "flex",
                // Mobile: repo (+ disabled badge) over a full-width remove button, so a long
                // owner/name slug never collides with the destructive control.
                flexDirection: isMobile ? "column" : "row",
                alignItems: isMobile ? "stretch" : "center",
                gap: 10,
                padding: "8px 10px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                flexWrap: "wrap",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--foreground)",
                  flex: 1,
                  minWidth: isMobile ? 0 : 120,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {p.repo}
              </span>
              {p.enabled === false && (
                <Badge tone="neutral" size="sm">
                  disabled
                </Badge>
              )}
              <Button
                variant="danger"
                size={isMobile ? "md" : "sm"}
                fullWidth={isMobile}
                onClick={() => onRemove(p)}
              >
                {t("admin.onboard_remove")}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Directory browser confined server-side to ONBOARD_BASE_DIRS (GET /api/admin/browse). Click into a
// sub-folder to descend; ".." ascends (still server-confined — a 422 outside the roots surfaces as an
// inline error and the descent is refused). The currently-listed `path` IS the pickable clone dir.
function DirBrowser({ picked, onPick, isMobile, t }) {
  const [path, setPath] = React.useState("");
  const [entries, setEntries] = React.useState(null); // [] | null
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);

  const browse = React.useCallback(async (target) => {
    setBusy(true);
    setErr(null);
    try {
      // Empty target → server starts at the first ONBOARD_BASE_DIRS root.
      const r = await api.browseDir(target || undefined);
      setPath(r.path);
      setEntries((r.entries || []).filter((e) => e.is_dir));
    } catch (e) {
      // 422 (outside roots) or any browse error — keep the current listing, show the reason.
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
          // Mobile: full-width pick button with the "picked: …" caption beneath it.
          flexDirection: isMobile ? "column" : "row",
          alignItems: isMobile ? "stretch" : "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <Button
          variant="secondary"
          size={isMobile ? "md" : "sm"}
          fullWidth={isMobile}
          disabled={busy || !path}
          onClick={() => onPick(path)}
        >
          {t("admin.onboard_browse_pick_btn")}
        </Button>
        <span
          style={{
            fontSize: 12,
            color: "var(--muted-foreground)",
            wordBreak: "break-all",
          }}
        >
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

// Daemon list — one row per allowlisted PM2 app with start/stop/restart/status buttons and a
// per-row log-tail toggle. UI apps (the config servers) swap the standalone mutate buttons (refused
// by D1) for a single confirm-gated "graceful restart" that bounces + reconnects.
function DaemonList({
  daemon,
  busyApps,
  onAction,
  onGracefulRestart,
  uiRestart,
  isMobile,
  t,
}) {
  if (daemon == null)
    return (
      <div style={{ padding: 16, color: "var(--muted-foreground)" }}>
        {t("common.loading")}
      </div>
    );
  if (daemon.length === 0)
    return (
      <div style={{ padding: 16, color: "var(--muted-foreground)" }}>
        {t("admin.no_daemons")}
      </div>
    );
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
        overflow: "hidden",
        marginBottom: 22,
      }}
    >
      {daemon.map((d) => (
        <DaemonRow
          key={d.app}
          d={d}
          busy={!!busyApps[d.app]}
          onAction={onAction}
          onGracefulRestart={onGracefulRestart}
          restartPhase={
            uiRestart && uiRestart.app === d.app ? uiRestart.phase : null
          }
          isMobile={isMobile}
          t={t}
        />
      ))}
    </div>
  );
}

function DaemonRow({
  d,
  busy,
  onAction,
  onGracefulRestart,
  restartPhase,
  isMobile,
  t,
}) {
  const [logs, setLogs] = React.useState(null); // null = closed; [] = open, fetching/empty
  const [logErr, setLogErr] = React.useState(null);
  const [logBusy, setLogBusy] = React.useState(false);
  const isUiApp = UI_APP_NAMES.has(d.app);
  const online = d.status === "online";
  // A graceful restart is in flight for THIS app while its phase is running/bouncing.
  const restarting = restartPhase === "running" || restartPhase === "bouncing";

  const toggleLogs = async () => {
    if (logs != null) {
      setLogs(null);
      setLogErr(null);
      return;
    }
    setLogBusy(true);
    setLogErr(null);
    try {
      const r = await api.getDaemonLogs(d.app, 200);
      setLogs(r.lines || []);
    } catch (e) {
      setLogErr(e.message);
      setLogs([]);
    } finally {
      setLogBusy(false);
    }
  };

  return (
    <div style={{ borderBottom: "1px solid var(--border)" }}>
      <div
        style={{
          display: "flex",
          // Mobile: stack identity → meta → action grid so nothing is squeezed onto a wrapping row.
          flexDirection: isMobile ? "column" : "row",
          alignItems: isMobile ? "stretch" : "center",
          gap: isMobile ? 8 : 10,
          padding: "10px 13px",
          flexWrap: "wrap",
        }}
      >
        {/* identity: status chip + app name (truncates) + the in-flight spinner */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            minWidth: 0,
            flex: isMobile ? undefined : 1,
          }}
        >
          <Badge tone={online ? "accent" : "red"} size="sm">
            {d.status || "—"}
          </Badge>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              fontWeight: 600,
              color: "var(--foreground)",
              flex: 1,
              minWidth: 0,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {d.app}
          </span>
          {/* Generic daemon-action spinner; the graceful restart shows its own button + status. */}
          {busy && <Spinner />}
        </div>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--muted-foreground)",
          }}
        >
          {t("admin.daemon_meta", {
            pid: d.pid != null ? d.pid : "—",
            uptime: d.uptime_s != null ? `${Math.round(d.uptime_s)}s` : "—",
            restarts: d.restarts != null ? d.restarts : "—",
          })}
        </span>
        <div
          style={{
            // Mobile: a 2-column grid of comfortable (36px) tap targets instead of a tight wrap.
            display: isMobile ? "grid" : "flex",
            gridTemplateColumns: isMobile ? "1fr 1fr" : undefined,
            gap: 6,
            flexWrap: isMobile ? undefined : "wrap",
          }}
        >
          {isUiApp ? (
            // UI config server: the naked start/stop/restart are refused (D1, foot-gun). Offer the
            // sanctioned graceful restart instead — a detached pm2 restart this page reconnects to.
            <Button
              size={isMobile ? "md" : "sm"}
              fullWidth={isMobile}
              variant="secondary"
              disabled={busy || restarting}
              loading={restarting}
              title={t("admin.daemon_graceful_restart_tip")}
              onClick={() => onGracefulRestart(d.app)}
            >
              {t("admin.daemon_graceful_restart")}
            </Button>
          ) : (
            MUTATE_ACTIONS.map((action) => {
              // Reflect the live PM2 state: "start" is meaningless while the app is online; "stop"
              // and "restart" are meaningless while it is stopped.
              const stateDisabled = action === "start" ? online : !online;
              const why = stateDisabled
                ? t(
                    action === "start"
                      ? "admin.daemon_already_running"
                      : "admin.daemon_not_running",
                  )
                : undefined;
              return (
                <Button
                  key={action}
                  size={isMobile ? "md" : "sm"}
                  fullWidth={isMobile}
                  // All control buttons use the bordered `secondary` variant: the `ghost` variant
                  // has a transparent border + transparent fill, so Start/Stop read as borderless
                  // text — invisible as buttons in dark theme (--border is white at 11%).
                  variant="secondary"
                  disabled={busy || stateDisabled}
                  title={why}
                  onClick={() => onAction(d.app, action)}
                >
                  {t(`admin.daemon_${action}`)}
                </Button>
              );
            })
          )}
          <Button
            size={isMobile ? "md" : "sm"}
            fullWidth={isMobile}
            variant="secondary"
            disabled={logBusy}
            onClick={toggleLogs}
          >
            {logs != null
              ? t("admin.daemon_logs_hide")
              : t("admin.daemon_logs")}
          </Button>
        </div>
      </div>
      {restartPhase && (
        <div
          style={{
            padding: "0 13px 12px",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Badge
            tone={
              restartPhase === "done"
                ? "accent"
                : restartPhase === "failed"
                  ? "red"
                  : "amber"
            }
            size="sm"
          >
            {t(
              restartPhase === "done"
                ? "admin.ui_restart_done"
                : restartPhase === "failed"
                  ? "admin.ui_restart_failed"
                  : restartPhase === "bouncing"
                    ? "admin.ui_restart_reconnecting"
                    : "admin.ui_restart_running",
              { app: d.app },
            )}
          </Badge>
          {restarting && <Spinner />}
        </div>
      )}
      {logs != null && (
        <div style={{ padding: "0 13px 12px" }}>
          {logErr && (
            <Banner tone="error" title={t("admin.daemon_logs_failed")}>
              {logErr}
            </Banner>
          )}
          {!logErr && (
            <pre
              style={{
                margin: 0,
                maxHeight: 280,
                overflow: "auto",
                background: "var(--surface-app, var(--background))",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: 10,
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                lineHeight: 1.5,
                color: "var(--muted-foreground)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
              }}
            >
              {logs.length === 0
                ? t("admin.daemon_logs_empty")
                : logs.join("\n")}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// Version badge — "Update available" pill when update_available; "offline" muted state when the
// remote probe couldn't resolve (remote === "unknown").
function VersionBadge({ version, t }) {
  if (!version)
    return (
      <Badge tone="neutral" size="sm">
        {t("common.loading")}
      </Badge>
    );
  const offline = version.remote === "unknown";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <KeyChip>v{version.local}</KeyChip>
      {offline ? (
        <Badge tone="neutral" size="sm">
          {t("admin.version_offline")}
        </Badge>
      ) : version.update_available ? (
        <Badge tone="amber" size="sm">
          {t("admin.version_update", { remote: version.remote })}
        </Badge>
      ) : (
        <Badge tone="accent" size="sm">
          {t("admin.version_uptodate")}
        </Badge>
      )}
    </span>
  );
}

// One project health card — repo header + the five liveness chips + heartbeat age.
function ProjectCard({ p, t }) {
  const daemonOk = !!p.daemon_alive;
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
        padding: 14,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 13,
            fontWeight: 600,
            color: "var(--foreground)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {p.repo}
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <BoolChip
          ok={daemonOk}
          label={
            daemonOk ? t("admin.chip_daemon_up") : t("admin.chip_daemon_down")
          }
        />
        <BoolChip ok={!!p.github_api_ok} label={t("admin.chip_github")} />
        <BoolChip ok={!!p.board_ok} label={t("admin.chip_board")} />
        <BoolChip ok={!!p.token_present} label={t("admin.chip_token")} />
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--muted-foreground)",
        }}
      >
        {t("admin.heartbeat_age", {
          age:
            p.heartbeat_age_s == null
              ? "—"
              : `${Math.round(p.heartbeat_age_s)}s`,
        })}
      </div>
    </div>
  );
}

// Recent jobs list — id / type / actor / state / exit-code, newest first (as returned).
function JobsList({ ops, isMobile, t }) {
  if (ops == null)
    return (
      <div style={{ padding: 16, color: "var(--muted-foreground)" }}>
        {t("common.loading")}
      </div>
    );
  if (ops.length === 0)
    return (
      <div style={{ padding: 16, color: "var(--muted-foreground)" }}>
        {t("admin.no_jobs")}
      </div>
    );
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
        overflow: "hidden",
      }}
    >
      {ops.map((j) => (
        <div
          key={j.id}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "9px 13px",
            borderBottom: "1px solid var(--border)",
            flexWrap: "wrap",
          }}
        >
          <Badge tone={JOB_TONE[j.state] || "neutral"} size="sm">
            {j.state}
          </Badge>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              fontWeight: 600,
              color: "var(--foreground)",
            }}
          >
            {j.type}
          </span>
          {j.args_summary && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--muted-foreground)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                flex: 1,
                // Mobile: take the whole next line rather than fighting the badges for width.
                flexBasis: isMobile ? "100%" : undefined,
                minWidth: 0,
              }}
            >
              {j.args_summary}
            </span>
          )}
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10.5,
              color: "var(--muted-foreground)",
            }}
          >
            {j.actor}
          </span>
          {j.exit_code != null && (
            <Badge tone={j.exit_code === 0 ? "accent" : "red"} size="sm">
              {t("admin.exit_code", { code: j.exit_code })}
            </Badge>
          )}
        </div>
      ))}
    </div>
  );
}

// Job-state → Badge tone. Mirrors the agent-state tone scheme used in MonitoringPanel.
const JOB_TONE = {
  queued: "neutral",
  running: "accent",
  succeeded: "accent",
  done: "accent",
  failed: "red",
  error: "red",
};

function SectionLabel({ children }) {
  return (
    <div
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        letterSpacing: ".08em",
        textTransform: "uppercase",
        color: "var(--muted-foreground)",
        marginBottom: 8,
      }}
    >
      {children}
    </div>
  );
}
