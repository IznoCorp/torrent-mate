# Maquette — the host switch

**Status**: approved by the operator (2026-08-14, « Bascule puis SP3 ») · **Branch**: `refactor/maquette-bascule`
**Scope**: the step that closes the SP2 family — the design host serves the **Vite build**
instead of a synthesized wrapper around the source. What the operator judges on a phone
becomes, byte for byte, what the build pipeline produces — before SP3 starts transforming
anything.

## Context

SP2 (merged, PR #430) delivered the shell and its proof: `npm run build` in
`frontend/maquette/design/` emits `dist/index.html` — the real envelope with the prototype
injected verbatim — and R72 (`coquille.py`) holds byte-exactness plus DOM/geometry identity
per driven state. Measured on this branch: a full rebuild takes **0.4 s** end to end.

Today three envelopes exist: `serve.py`'s HEAD/TAIL synthesis (with the PWA head), the
harness `wrapped.html` recipe, and the Vite `index.html`. The host switch retires the
first — `serve.py` stops synthesizing documents and serves the build. The harness recipe
**stays**: `wrapped.html` is a scratch copy that isolates rule mutations from what the host
serves, and that isolation is load-bearing (SP1 lesson: measure what a guard carries before
removing it). R72 keeps comparing the raw source against the build — that contract is what
makes the switch safe, and SP3 will renegotiate it explicitly when source and output start
to differ by design.

## Decisions this spec makes

1. **The envelope's document concerns move into `index.html`.** The PWA head that
   `serve.py` injected (`manifest` link, theme-color, apple-touch-icon, favicon link, the
   apple/mobile-web-app metas, the SW registration script) becomes part of the Vite
   envelope — the document's single source of truth. `serve.py` keeps its SERVER concerns:
   the synthesized `manifest.webmanifest`, `sw.js`, `hors-ligne.html`, brand-asset routes,
   the session gate, and the login page extracted from the prototype source (markers —
   unchanged, it reads `refonte.html` as before).
2. **`serve.py` serves `design/dist/index.html`, auto-rebuilding when stale.** On each
   request for the document, compare the newest mtime of (`refonte.html`, `index.html`,
   `vite.config.mjs`) against `dist/index.html`'s. If stale or missing, run the build
   (absolute npm path, `/Users/izno/.nvm/versions/node/v22.13.1/bin/npm`, cwd `design/`,
   ~0.4 s) under the existing document lock/cache discipline, then serve the fresh bytes
   (mtime_ns cache as today). The live-editing property survives: the operator still sees
   uncommitted work at the next reload.
3. **A failed build is shown, never masked.** If the build exits non-zero, answer 503 with
   a page that says the BUILD failed and carries the last lines of its stderr (the
   prototype-missing 503 stays for the missing-source case). A design host that silently
   served the previous build would be a stale reference — the exact failure the host
   exists to avoid (§13: honesty on screen).
4. **The harness keeps measuring the source.** `commun.py`, the `wrapped.html` recipe, and
   all 43 rules are untouched by the switch, except the rules that exercise `serve.py`
   itself (`demarrage.py`, `deconnexion.py` boot it on a scratch port; `pwa.py`,
   `entree.py` measure the live host) — those must stay green against the new serving
   path, and their expectations are updated ONLY where the mechanism genuinely changed
   (e.g. the served document now contains the PWA head from the envelope rather than from
   HEAD synthesis).
5. **One new rule — R73, `bascule.py`:** the host serves the build. Boots `serve.py` on a
   scratch port with a session and holds: (a) the authenticated `GET /` body is
   byte-identical to `design/dist/index.html`; (b) touching the source and re-requesting
   yields a document carrying the change (auto-rebuild works); (c) a deliberately broken
   source (unparseable `vite.config.mjs` swap or equivalent injected failure) yields a 503
   whose body names the build failure — then restore and green. Mutation-verified like
   every rule.

## What does NOT change

- `refonte.html` (except nothing — zero bytes), `assets/`, the CSS extraction contract.
- The session gate, credentials, cookie mechanics, the login screen extraction.
- The harness's measuring URL (8899 `wrapped.html`) and the mutation-isolation ritual.
- R72 — still raw-source vs build; the byte-exact assertion already covers the emitted
  document.
- Caddy, ports, pm2 process identity.

## Delivery

Branch `refactor/maquette-bascule` from `main` (`61fe2b7b`). One commit per item:

1. the envelope gains the PWA head (`index.html`) — and `serve.py` loses `TETE_PWA`
   injection in the same commit (one source of truth, no transition state)
2. `serve.py` serves the build with auto-rebuild + build-failure 503
3. R73 `bascule.py` + `regions.json` entry + README row (mutation evidence in the message)
4. affected host rules updated (`demarrage.py`/`deconnexion.py`/`pwa.py`/`entree.py` — only
   what the mechanism change requires)
5. docs + version bump (patch → 0.97.3)

`pm2 restart torrentmate-design` after merge — this time it is REQUIRED (serve.py changed).

## Verification (all executed, none assumed)

- R73 green with its three holds, each mutation felling exactly its own check.
- R72 green (the comparison survives the envelope change — its source side wraps the raw
  source itself, its build side is the same dist).
- The full 44-script suite green (background, sequential, one measuring process).
- The LIVE host measured after `pm2 restart`: authenticated `GET /` byte-identical to the
  local `dist/index.html` at the same commit; `pwa.py` and `entree.py` green against it.
- `make check` green; `git status` clean; push with remote SHA verified; PR; CI; merge on
  the operator's standing instruction, then the live byte-identity check ONCE MORE on the
  merged tree.

## Out of scope

- SP3 (routing) — next, with its own spec; carry there: `vite dev` binds `::1`; the dev
  path is measured by no rule; R72's identity contract must be renegotiated when source
  and output begin to differ by design.
- The permanent `/assets/` gate rule (still carried; candidate for R73's file or its own).
- SP4, SP5.
