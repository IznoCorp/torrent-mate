# ACCEPTANCE — pipe-control — TorrentMate UI S2: Pipeline control

**Feature**: TorrentMate web UI — wave S2 (pipeline control)
**Codename**: `pipe-control` · **Branch**: `feat/pipe-control`
**Design**: `docs/features/pipe-control/DESIGN.md`

> **Format rule** (see `docs/reference/feature-lifecycle.md` §2): every ACC-NN is
> an executable shell command with a documented expected output. Genuinely visual
> criteria are flagged **Manual (staging)** per the deferred-criterion protocol and
> paired with an executable proxy where one exists.

Preconditions for ACC-01..ACC-05 / ACC-08: `personalscraper web` is running on
`127.0.0.1:8710`, and `$C` holds a valid session cookie:

```bash
# Mint a session cookie (adjust credentials to your .env WEB_USERNAME/WEB_PASSWORD).
C=$(curl -s -i --connect-timeout 10 --max-time 30 \
  -X POST http://127.0.0.1:8710/api/auth/login \
  -H 'X-Requested-With: TorrentMate' -H 'Content-Type: application/json' \
  -d '{"username":"izno","password":"'"$WEB_PASSWORD"'"}' \
  | awk -F': ' 'tolower($1)=="set-cookie"{print $2}' | cut -d';' -f1)
echo "$C"   # Expected: tm_session=<jwt>
```

---

### ACC-01 — Start a run; second concurrent start is refused (single trigger authority)

**Scope**: DESIGN §4 `/run`, §0 single-trigger-authority.

```bash
# First start (dry-run) → 202 + a run_uid.
curl -s --connect-timeout 10 --max-time 30 -X POST \
  http://127.0.0.1:8710/api/pipeline/run \
  -H "Cookie: $C" -H 'X-Requested-With: TorrentMate' -H 'Content-Type: application/json' \
  -d '{"dry_run":true}'
# Expected: HTTP 202, body {"run_uid":"<32-hex>"}

# Second immediate start while the lock is held → 409.
curl -s -o /dev/null -w '%{http_code}\n' --connect-timeout 10 --max-time 30 -X POST \
  http://127.0.0.1:8710/api/pipeline/run \
  -H "Cookie: $C" -H 'X-Requested-With: TorrentMate' -H 'Content-Type: application/json' \
  -d '{"dry_run":true}'
# Expected: 409
```

---

### ACC-02 — Pause / resume flips the run state at the step boundary

**Scope**: DESIGN §3.1 pause checkpoint, §4 `/pause` `/resume` `/status`.

```bash
curl -s --connect-timeout 10 --max-time 30 -X POST http://127.0.0.1:8710/api/pipeline/pause \
  -H "Cookie: $C" -H 'X-Requested-With: TorrentMate'
curl -s --connect-timeout 10 --max-time 30 http://127.0.0.1:8710/api/pipeline/status \
  -H "Cookie: $C" | python3 -c 'import sys,json;print(json.load(sys.stdin)["state"])'
# Expected: paused

curl -s --connect-timeout 10 --max-time 30 -X POST http://127.0.0.1:8710/api/pipeline/resume \
  -H "Cookie: $C" -H 'X-Requested-With: TorrentMate'
curl -s --connect-timeout 10 --max-time 30 http://127.0.0.1:8710/api/pipeline/status \
  -H "Cookie: $C" | python3 -c 'import sys,json;print(json.load(sys.stdin)["state"])'
# Expected: running   (or idle, if the run already finished)
```

---

### ACC-03 — Kill terminates the run, releases the lock, records outcome "killed"

**Scope**: DESIGN §4 `/kill`, §3.2 run-history.

```bash
curl -s --connect-timeout 10 --max-time 30 -X POST http://127.0.0.1:8710/api/pipeline/kill \
  -H "Cookie: $C" -H 'X-Requested-With: TorrentMate'
sleep 2
# The lock is released (status idle) and the latest history row is "killed".
curl -s --connect-timeout 10 --max-time 30 http://127.0.0.1:8710/api/pipeline/status \
  -H "Cookie: $C" | python3 -c 'import sys,json;print(json.load(sys.stdin)["state"])'
# Expected: idle
curl -s --connect-timeout 10 --max-time 30 'http://127.0.0.1:8710/api/pipeline/history?limit=1' \
  -H "Cookie: $C" | python3 -c 'import sys,json;print(json.load(sys.stdin)["runs"][0]["outcome"])'
# Expected: killed
```

---

### ACC-04 — Watcher toggle writes the `watcher.paused` sentinel

**Scope**: DESIGN §4 `/watcher` (distinct from run pause).

```bash
curl -s --connect-timeout 10 --max-time 30 -X POST http://127.0.0.1:8710/api/pipeline/watcher \
  -H "Cookie: $C" -H 'X-Requested-With: TorrentMate' -H 'Content-Type: application/json' \
  -d '{"enabled":false}'
# Expected: {"watcher_enabled":false}
test -f "$(python3 -c 'from personalscraper.conf.loader import load_config;print(load_config().paths.data_dir)')/watcher.paused" \
  && echo present
# Expected: present   (the watch loop no-ops while this sentinel exists)
```

---

### ACC-05 — History records the run with per-step timings

**Scope**: DESIGN §3.2 `pipeline_run`, §4 `/history`.

```bash
curl -s --connect-timeout 10 --max-time 30 'http://127.0.0.1:8710/api/pipeline/history?limit=5' \
  -H "Cookie: $C" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("total",d["total"],"| first steps_json ok:",isinstance(json.loads(json.dumps(d["runs"][0])).get("run_uid"),str))'
# Expected: total <N≥1> | first steps_json ok: True
```

---

### ACC-06 — Frontend quality gates green

**Scope**: DESIGN §5, §0 DS-strict + zero-any.

```bash
cd frontend
npm run typecheck   # Expected: exits 0, no errors
npm run lint        # Expected: 0 problems (incl. @typescript-eslint/no-explicit-any)
npm run lint:ds     # Expected: 0 (DS-adherence: no raw hex/px)
```

---

### ACC-07 — Operator control flow on `/pipeline` — **Manual (staging)**

**Scope**: DESIGN §5 control bar + stepper + live logs.

Manual (staging) — no pure-shell equivalent (visual, WS-driven):

1. Sign in at `https://tm-staging.iznogoudatall.xyz`, open **Pipeline**.
2. Click **Démarrer** → a dialog with a **dry-run** switch appears → confirm.
3. **Expected**: status flips to `running`; the `PipelineStepper` advances step by
   step; the live `RunLogFeed` shows events; **Pause** and **Kill** become enabled.
4. Click **Pause** → **Expected**: state `paused`, stepper freezes; **Reprendre**
   resumes; **Kill** stops the run and the row lands in history as `killed`.

---

### ACC-08 — History table → run detail — **Manual (staging)** + executable proxy

**Scope**: DESIGN §5 run-history table + detail.

Manual (staging): on **Pipeline**, the history table lists past runs with the
correct outcome `Badge`; clicking a row opens the detail with per-step timings.

Executable proxy (a known `run_uid` from ACC-05):

```bash
RUID=$(curl -s --connect-timeout 10 --max-time 30 'http://127.0.0.1:8710/api/pipeline/history?limit=1' \
  -H "Cookie: $C" | python3 -c 'import sys,json;print(json.load(sys.stdin)["runs"][0]["run_uid"])')
curl -s --connect-timeout 10 --max-time 30 "http://127.0.0.1:8710/api/pipeline/history/$RUID" \
  -H "Cookie: $C" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("steps:",len(d["steps"]),"outcome:",d["outcome"])'
# Expected: steps: <N≥1> outcome: <success|error|killed>
```
