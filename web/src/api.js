// Thin fetch wrappers over the kanban config API (helm PR 1 + bridge PR 2).
// Every call throws an Error on a non-2xx response so callers surface it in a Banner.
// Board-scoped calls take a `project` (Project v2 node id) → ?project= selector (DESIGN §13.1).

async function call(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
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
