// Thin fetch wrappers over the kanban config API (helm PR 1 + bridge PR 2).
// Every call throws an Error on a non-2xx response so callers surface it in a Banner.
// Board-scoped calls take a `project` (Project v2 node id) → ?project= selector (DESIGN §13.1).

// Read the non-HttpOnly `km_csrf` cookie minted by the app-wide CSRF middleware (bosun §6).
// Returns "" when absent (e.g. before the first response set it).
function readCsrfCookie() {
  const m = (document.cookie || "").match(/(?:^|;\s*)km_csrf=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : "";
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function call(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  // Double-submit CSRF: echo the km_csrf cookie in X-KM-CSRF on every mutating request
  // (DESIGN §6). Done once here so all helpers below inherit it automatically.
  if (MUTATING.has(method.toUpperCase())) {
    const token = readCsrfCookie();
    if (token) opts.headers["X-KM-CSRF"] = token;
  }
  const resp = await fetch(path, opts);
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = data && data.detail ? data.detail : resp.statusText;
    const msg = typeof detail === "string" ? detail : JSON.stringify(detail);
    const err = new Error(`${resp.status}: ${msg}`);
    err.status = resp.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

// Append ?project= when a board is selected (board-scoped endpoints).
const q = (project) =>
  project ? `?project=${encodeURIComponent(project)}` : "";

// --- Auth (optional UI login) ---
export const getSession = () => call("GET", "/api/session");
export const login = (creds) => call("POST", "/api/login", creds);
export const logout = () => call("POST", "/api/logout", {});
export const fetchHealth = () => call("GET", "/api/health");

// --- Daemon-scoped (registry) ---
export const listProjects = () => call("GET", "/api/projects");
export const patchProject = (projectId, changes) =>
  call("PATCH", `/api/projects/${encodeURIComponent(projectId)}`, changes);

// --- Board-scoped (per-project config) ---
export const getConfig = (project) => call("GET", `/api/config${q(project)}`);
export const validate = (draft, project) =>
  call("POST", `/api/config/validate${q(project)}`, draft);
export const saveConfig = (draft, project) =>
  call("POST", `/api/config${q(project)}`, draft);
export const renderConfig = (project) =>
  call("GET", `/api/config/render${q(project)}`);
export const getPlaceholders = () => call("GET", "/api/placeholders");
export const getProfiles = () => call("GET", "/api/profiles");
export const listFiles = (project, path) =>
  call(
    "GET",
    `/api/files?path=${encodeURIComponent(path || "")}${project ? `&project=${encodeURIComponent(project)}` : ""}`,
  );
export const provisionBoard = ({ dryRun, renames, project }) =>
  call("POST", `/api/board/provision${q(project)}`, {
    dry_run: dryRun,
    renames: renames || {},
  });

// --- Native board (anchor) — placement authority is the native store; drives GitHub via mirror ---
export const boardState = (project) =>
  call("GET", `/api/board/state${q(project)}`);
export const boardMove = ({ itemId, toColumn, ifVersion }, project) =>
  call("POST", `/api/board/move${q(project)}`, {
    item_id: itemId,
    to_column: toColumn,
    ...(ifVersion != null ? { if_version: ifVersion } : {}),
  });
export const boardReorder = (
  { columnKey, orderedItemIds, ifVersion },
  project,
) =>
  call("POST", `/api/board/reorder${q(project)}`, {
    column_key: columnKey,
    ordered_item_ids: orderedItemIds,
    ...(ifVersion != null ? { if_version: ifVersion } : {}),
  });
export const boardPlace = ({ itemId, columnKey, index, ifVersion }, project) =>
  call("POST", `/api/board/place${q(project)}`, {
    item_id: itemId,
    column_key: columnKey,
    index: index ?? null,
    ...(ifVersion != null ? { if_version: ifVersion } : {}),
  });
export const boardImport = ({ dryRun }, project) =>
  call("POST", `/api/board/import${q(project)}`, { dry_run: !!dryRun });
export const newTicket = ({ title, body }, project) =>
  call("POST", `/api/board/new-ticket${q(project)}`, { title, body });

// --- Monitoring (read-only) ---
export const monitorBoard = (project) =>
  call("GET", `/api/monitor/board${q(project)}`);
export const monitorAgents = (project) =>
  call("GET", `/api/monitor/agents${q(project)}`);
export const monitorPane = (issue, project) =>
  call(
    "GET",
    `/api/monitor/agent/${encodeURIComponent(issue)}/pane${q(project)}`,
  );
export const monitorTicket = (number, project) =>
  call("GET", `/api/monitor/ticket/${encodeURIComponent(number)}${q(project)}`);
export const patchTicketBody = (number, freeform, project) =>
  call(
    "PATCH",
    `/api/monitor/ticket/${encodeURIComponent(number)}/body${q(project)}`,
    { freeform },
  );
// Enqueue an ad-hoc agent launch on a ticket (no transition / no card move).
export const launchAgent = (number, { prompt, profile }, project) =>
  call(
    "POST",
    `/api/monitor/ticket/${encodeURIComponent(number)}/launch${q(project)}`,
    { prompt, profile: profile || "dev" },
  );
// Change a ticket's column from Monitoring (operator move intent).
export const moveTicket = (number, toCol, project) =>
  call(
    "POST",
    `/api/monitor/ticket/${encodeURIComponent(number)}/move${q(project)}`,
    { to_col: toCol },
  );
// Poll an enqueued intent's result (so the UI shows the real outcome, not an optimistic "queued").
export const intentResult = (intentId, project) =>
  call(
    "GET",
    `/api/monitor/intent/${encodeURIComponent(intentId)}${q(project)}`,
  );

export const monitorFile = (path, project, ticket) =>
  call(
    "GET",
    `/api/monitor/file?path=${encodeURIComponent(path)}${project ? `&project=${encodeURIComponent(project)}` : ""}${ticket != null ? `&ticket=${encodeURIComponent(ticket)}` : ""}`,
  );

// --- Admin / Ops (read-only, host-wide; bosun phase 1) ---
// Auth-gated GETs (no CSRF for reads). Health = per-project liveness + global flags;
// version = {local (semver), build (served SHA), remote (origin/main SHA), update_available};
// ops = the recent jobs ledger.
export const getAdminHealth = () => call("GET", "/api/admin/health");
export const getAdminVersion = () => call("GET", "/api/admin/version");
export const listOps = () => call("GET", "/api/ops");

// --- Admin / daemon control + PAUSE + logs (bosun phase 2; mutating calls carry X-KM-CSRF) ---
// Daemon liveness rows; per-app start/stop/restart/status (UI apps refuse standalone mutate → 422);
// bounded PM2 log tail; the global PAUSE kill-switch; a single job record (poll a control job).
// The route returns {apps:[...], error?}; unwrap to the bare apps array here so every consumer
// gets an array (DaemonList does .length/.map on it) and they can't drift on the response shape.
export const getDaemon = async () => {
  const r = await call("GET", "/api/admin/daemon");
  return Array.isArray(r?.apps) ? r.apps : [];
};
export const daemonAction = (app, action) =>
  call(
    "POST",
    `/api/admin/daemon/${encodeURIComponent(app)}/${encodeURIComponent(action)}`,
  );
// Graceful restart of a UI config server (kanban-km-config / kanban-staging-config): spawns a
// DETACHED `pm2 restart` job that survives this server's own death. The SPA briefly loses the
// backend, then reconnects by polling getDaemon() until the app is back with a fresh pid (Option A).
export const uiRestart = (app) =>
  call("POST", `/api/admin/ui-restart/${encodeURIComponent(app)}`);
export const getDaemonLogs = (app, lines) =>
  call(
    "GET",
    `/api/admin/daemon/${encodeURIComponent(app)}/logs${lines != null ? `?lines=${encodeURIComponent(lines)}` : ""}`,
  );
export const getPause = () => call("GET", "/api/admin/pause");
export const setPause = (active) =>
  call("POST", "/api/admin/pause", { active: !!active });
export const getOp = (id) => call("GET", `/api/ops/${encodeURIComponent(id)}`);

// --- Admin / redeploy from main (bosun phase 3; mutating, carries X-KM-CSRF) ---
// Spawns a detached job shelling the audited deploy script for `target` ("prod"|"staging").
// The job bounces the config server as its tail, so the SPA briefly loses the backend — the caller
// polls getOp(job_id) for progress and getAdminVersion() until the served `build` SHA flips (DESIGN §8).
export const redeploy = (target) =>
  call("POST", "/api/admin/redeploy", { target });

// --- Admin / project onboarding (bosun phase 4; mutating calls carry X-KM-CSRF) ---
// Dir-browser confined server-side to ONBOARD_BASE_DIRS (~/dev, ~/deploy, ~/staging); a path
// outside → 422. add-local registers an existing clone (mode:local); add-clone git-clones then
// registers (mode:clone) — both return {job_id} (poll getOp). removeProject deregisters the entry
// (clone left on disk); 409 while the project has a live agent, 404 if unknown.
export const browseDir = (path) =>
  call(
    "GET",
    `/api/admin/browse${path ? `?path=${encodeURIComponent(path)}` : ""}`,
  );
export const addProjectLocal = (repo, path) =>
  call("POST", "/api/projects", { mode: "local", repo, path });
export const addProjectClone = (repo, gitUrl) =>
  call("POST", "/api/projects", { mode: "clone", repo, git_url: gitUrl });
export const removeProject = (projectId) =>
  call("DELETE", `/api/projects/${encodeURIComponent(projectId)}`);

// --- Admin / first-run install wizard (bosun phase 5; mutating calls carry X-KM-CSRF) ---
// Step 1 writes <root>/token (0600). Step 2 registers the first project (same body/behaviour as
// POST /api/projects → {job_id}). Step 3 provisions the board (job). Step 4 bootstraps the known PM2
// apps — first-run-only: 409 if any allowlisted app already exists. Steps 2-4 return {job_id} (poll
// getOp). The wizard shows when GET /api/admin/health reports zero projects (DESIGN §10).
export const wizardToken = (token) =>
  call("POST", "/api/admin/wizard/token", { token });
export const wizardProject = (body) =>
  call("POST", "/api/admin/wizard/project", body);
export const wizardProvision = (project) =>
  call("POST", "/api/admin/wizard/provision", { project });
export const wizardBootstrap = () =>
  call("POST", "/api/admin/wizard/bootstrap", {});
