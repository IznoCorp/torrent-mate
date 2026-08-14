# Maquette SP1 — the served directory

**Status**: approved by the operator (2026-08-14) · **Branch**: `refactor/maquette-sp1`
**Scope**: sub-project 1 of the maquette structuring — the served directory and the image
extraction. **No logic changes** to the prototype, the harness rules, or the app.

## Context

`frontend/maquette/refonte.html` is the product (product-intent §15): a single 15.0 MB HTML
file, 13.1 MB of which is 930 base64-embedded webp images living in four module-level
constants (`POSTERS` 402, `HEROS` 319, `AFFICHES_HD` 38, `ACTEURS` 170), plus one stray —
the account avatar in `COMPTE.avatar` (line ~9789). 41 harness scripts, `serve.py`, and
`scripts/extract-maquette-css.py` all read this file; several read it as raw source text.

The operator has decided the maquette's future: it will be converted, sub-project by
sub-project, into a standalone front (React + Vite + TanStack Router + Tailwind + TS),
served from a dedicated directory. `file://` support is **abandoned** (measured: classic
scripts and `<img>` work from `file://`, ES modules and `fetch` do not — the future stack
requires a server anyway).

The overall migration is decomposed into five sub-projects; **this spec covers only SP1**:

| #   | Sub-project                                                              | Delivered by |
| --- | ------------------------------------------------------------------------ | ------------ |
| 1   | **Served directory + real image files**                                  | this spec    |
| 2   | Vite shell serving the same page                                         | future spec  |
| 3   | TanStack Router, 74 named states as routes                               | future spec  |
| 4   | Surfaces → components, state ownership                                   | future spec  |
| 5   | Visual language (semantic classes vs Tailwind) + CSS extraction contract | future spec  |

Konsta UI, Motion, TanStack DB/Store are evaluated in SP4/SP5, not before.

## Operator arbitrations (settled — do not re-litigate)

1. **Image values become relative URLs** in the existing tables (option A). The four
   constants keep their keys and lookup semantics (`HEROS[t] ?? HEROS[baseTitle(t)]`);
   only the 931 string values change from `data:` URIs to `assets/...` paths. No manifest
   file, no path-from-title derivation (NFC/NFD and slug-collision traps already paid).
2. **Files are named by content hash** (option A): first 8 hex chars of SHA-1 of the
   decoded bytes, one subdirectory per table. Readable identity stays in the table keys.
3. **Library images stay behind the session gate.** They are the operator's real posters.
   Only the 6 brand assets (PWA icons, favicon) remain session-free, as today.
4. **The ~925 webp files are committed** (~9.9 MB once, versus 13.2 MB of base64 rewritten
   into git on every prototype edit). Nothing on this path is gitignored — no `git add -f`
   for assets.
5. **The design host serves from this working tree** (pm2 `torrentmate-design`, port 8712).
   The move and the `serve.py` update land in the same commit; restart pm2 after.

## Layout

```
frontend/maquette/
  design/                ← the served root: everything a browser reaches, nothing else
    refonte.html
    assets/
      pwa-192-design.png, pwa-512-design.png, maskable-192-design.png,
      maskable-512-design.png, apple-touch-icon-design.png, favicon.svg
      posters/<hash>.webp    × ~402
      heros/<hash>.webp      × ~319
      affiches/<hash>.webp   × ~38
      acteurs/<hash>.webp    × ~170
      avatar.webp            (the stray in COMPTE.avatar)
  harness/               ← measures the prototype; never served
  serve.py               ← the gate; never served
  regions.json, README.md, ecosystem.design.config.cjs
```

`design/` is named after the host (`tm-design`, pm2 `torrentmate-design`) and becomes the
Vite project root in SP2. 931 references over ~925 files: duplicate images converge on the
same hash by construction — intended, not accidental.

## Image extraction

A one-shot conversion script (not committed; described in the commit message):

1. Parse each `data:image/webp;base64,...` value in the four tables + `COMPTE.avatar`.
2. Decode, write `design/assets/<table>/<hash8>.webp`.
3. Replace the value with the relative URL string. Keys, ordering, and every other byte
   of the file stay identical.
4. **Proof**: re-read every written file, re-encode, compare against the original base64;
   assert the rewritten HTML differs from the original only inside the 931 value strings.

Values are consumed as opaque strings (measured: no `startsWith('data:')`, no decoding);
relative URLs flow through `src=` and `url()` unchanged. They resolve against the document
base URL — hence the symlink below.

## serve.py

- `PROTOTYPE` → `design/refonte.html`; `DOSSIER_ASSETS` → `design/assets`.
- New route `GET /assets/<subpath>`, **session-gated**: resolved path must stay under
  `design/assets/` (no traversal), `Content-Type: image/webp`,
  `Cache-Control: public, max-age=31536000, immutable` (hash names: changed content
  changes URL).
- The 6 brand assets keep today's regime: served by exact name, session-free, from the
  new location. The manifest and login flow are untouched.
- After merge to the working tree: `pm2 restart torrentmate-design`.

## Harness and source readers

- `/tmp/tm-refonte/assets` becomes a **symlink** to the repo's `design/assets/`
  (`python -m http.server` follows symlinks — measure before relying on it). The
  wrapped.html re-sync recipe in the README gains that step.
- Path-constant updates, the complete blast radius (nothing else reads the source):
  `harness/panneau.py`, `harness/export.py`, `harness/demarrage.py` (2 sites),
  `harness/palette.py`, `harness/renommer.mjs`, `scripts/extract-maquette-css.py`,
  `regions.json` (`source` field), `frontend/maquette/README.md`, root `CLAUDE.md`,
  `docs/reference/product-intent.md` (§15 path citation). `harness/commun.py` is
  untouched (the 8899 URL does not change).
- **One new rule** (42nd script, `images.py`): `refonte.html` carries no `data:image`
  URI. Mutation-verified: reinsert one data URI → the rule falls naming that defect →
  restore.

## Known risk — image decode becomes asynchronous

The only change of nature: images now load over HTTP instead of being present at parse
time. If a rule measures geometry carried by a decoded image rather than a CSS box, it may
become unstable. Response, in order: (a) the full 42-script run says whether the risk is
real; (b) if a rule flakes, the fix is explicit `width`/`height` or an `await img.decode()`
**inside the affected rule** — never a sleep. A 404'd asset surfaces as a console error,
which `Journal.bilan(erreurs)` already turns into a failure — that guard is free.

## Delivery

New branch from `main`, one commit per item, Conventional Commits, scope `(shell-mobile)`,
messages in French, version bump in the PR:

1. image extraction + `design/` move + `serve.py` (one commit — the host serves from this
   tree, so the move and the server must change together)
2. harness path updates + symlink recipe
3. the new `images.py` rule (with its mutation evidence in the commit message)
4. docs (README, CLAUDE.md, product-intent §15 citation)

## Verification (all executed, none assumed)

- The 42 scripts green, run in background in two halves, one process at a time.
- `make check` green — the CSS-extraction drift guard still bites (verify both directions:
  touch the generated file → check fails → restore).
- Byte-identity proof of every extracted image (step 4 of the extraction).
- Live host measured after `pm2 restart`: `pwa.py` and `entree.py` green; one asset URL
  answers 200 with a session and is refused without; brand icons still session-free.
- Remote SHA verified after every push (the pre-push hook can SIGPIPE the transport).

## Out of scope

Framework, build, routing, componentisation, Tailwind, state ownership, the CSS-extraction
contract's future — all SP2–SP5. Any surface behaviour change. The six `to confirm`
defects in BUGS.md (operator-owned).
