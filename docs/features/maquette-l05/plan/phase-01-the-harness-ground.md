# Phase 1 — The harness's ground

**Nothing else in this wave is measurable until this lands.** Under D1 a page sits at `/media`;
the harness reads `http://127.0.0.1:8899/wrapped.html`, served by a plain `http.server` that
answers a file for a file's own path and 404 for everything else. That pathname would match no
route, the router would render the not-found page, and 52 rules, the oracle's 2 739 measurements
and the accessibility audit would all fail at once for a reason unrelated to the change under test.

**This phase changes the instruments while the prototype is untouched**, which is the only moment
at which the swap is provable on its own: the suite must be green before and after, at unchanged
hold counts, with zero oracle divergence.

## What is in the way, measured rather than assumed

1. `harness/server.py` already holds the fallback — files as-is, any unresolved address folded onto
   `wrapped.html`, except under `ASSET_PREFIXES = ("/assets/", "/vite/")` where a missing file
   still 404s. It was written for `screen_addresses.py`, its only current caller.
2. **`start_server()` refuses port 8899** — it is in `RESERVED_PORTS`, deliberately, so that a rule
   cannot race the prototype's host for the socket. That reason survives this phase and must not be
   deleted: what changes is that the HOST itself now needs to bind it.
3. **`python3 server.py` is itself a rule** — its `__main__` runs a self-proof on port 8917, and
   `run.sh` executes every `*.py` in the directory. Turning the module into a launcher by
   overloading its bare invocation would silently remove a rule from the suite.
4. **31 files name `wrapped.html`**, `oracle.py` and `a11y.py` among them.
   <sub>`grep -rl "wrapped.html" frontend/maquette/harness/*.py frontend/maquette/oracle.py frontend/maquette/a11y.py | wc -l`</sub>

## Steps

1. **Give `server.py` a launcher that is not its self-proof.** A flag — `python3 server.py --serve
   <port> --root <dir>` — binds and serves in the foreground; the bare invocation keeps running the
   self-proof exactly as it does today, so the rule count does not move. The launcher binds
   directly rather than through `start_server()`, whose `RESERVED_PORTS` guard keeps its subject:
   refusing a RULE the prototype's port.
2. **`run.sh` starts that launcher instead of `python3 -m http.server`**, and the comment above it
   says why — a plain server answers 404 to every address the router owns.
3. **Move the three instruments off the document's own filename.** `common.py`'s `PROTOTYPE`,
   `oracle.py` and `a11y.py` read `http://127.0.0.1:8899/`. Every remaining mention of
   `wrapped.html` must be the FILE COPY operation, never a navigation target — that distinction is
   what ACC-02 records.
4. **Update the ritual in `IMPLEMENTATION.md` § « Where to start »**, which currently prints the
   `python3 -m http.server 8899` recipe twice. A recipe left standing after the work that falsified
   it is the stale-directive disease; both copies move.
5. **Check the rules that build a URL from `PROTOTYPE` by concatenation.** `url_state.py` writes
   `PROTOTYPE + "?page=nimportequoi"`; with a trailing-slash base that still forms a valid address,
   but every such site is read rather than assumed to survive.

## The rule that bites

The launcher's own proof extends `server.py`'s existing self-proof: a deep address requested
directly against the RUNNING host answers 200 and serves the document.

**Mutation**: point `run.sh` back at `python3 -m http.server`. The proof must fall and say the host
does not fold unknown addresses — not merely "connection refused", which would be the same message
as a host that never started.

## Done when

- ACC-01, ACC-02, ACC-06 pass.
- ACC-03 (full suite), ACC-04 (hold counts), ACC-05 (oracle), ACC-20 (a11y) are all green **and the
  prototype has not been touched** — `git diff main..HEAD -- frontend/maquette/design/` is empty.
- The mutation above has been seen to fall and has been restored.
