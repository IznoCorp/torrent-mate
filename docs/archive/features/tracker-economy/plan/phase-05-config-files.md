# Phase 5 — Config files + .env.example + reference doc

## Gate

**Requires Phase 4:**
`python -c "from personalscraper.api._activation import resolve_optional_secret; print(resolve_optional_secret('c411', env={}))"` → `{'C411_PASSKEY': None}`

---

## Goal

Update `config.example/tracker.json5` (add commented economy block), `config/tracker.json5` (add live economy block for `c411`), `.env.example` (add passkey vars), and `docs/reference/config-overlay-layout.md` (new economy section). No source code changes.

## Files

- **Modify:** `config.example/tracker.json5`
- **Modify:** `config/tracker.json5`
- **Modify:** `.env.example`
- **Modify:** `docs/reference/config-overlay-layout.md`

---

## Tasks

### Task 5.1 — Replace `config.example/tracker.json5`

```json5
{
  // PROVIDER_CREDS (activation-gating): lacale → LACALE_API_KEY, c411 → C411_API_KEY
  // PROVIDER_OPTIONAL_SECRETS (non-gating, RP2): lacale → LACALE_PASSKEY, c411 → C411_PASSKEY
  // A missing passkey never deactivates a tracker (DESIGN §Non-Goals, D3).
  tracker: {
    providers: {
      lacale: {
        enabled: false,
        // economy: {
        //   target_ratio: 2.0,        // Ratio-C1 loops toward this
        //   min_ratio: 1.0,           // deletion floor (O2)
        //   min_seed_time: "72h",     // humanized: s/m/h/d/w → stored as seconds
        //   hit_and_run_grace: "48h", // grace after download before H&R counting
        // },
      },
      c411: {
        enabled: false,
        // economy: {
        //   target_ratio: 2.0,
        //   min_ratio: 1.0,
        //   min_seed_time: "72h",
        //   hit_and_run_grace: "48h",
        // },
      },
    },
    priority: ["lacale", "c411"],
    priority_by_media_type: {
      // movie: ["c411", "lacale"],
      // tv:    ["lacale", "c411"],
    },
    max_total_results: 50,
    max_per_tracker: 30,
    timeout_per_tracker: 15,
  },
}
```

### Task 5.2 — Replace `config/tracker.json5` (live overlay)

```json5
{
  // PROVIDER_CREDS: lacale → LACALE_API_KEY, c411 → C411_API_KEY
  // PROVIDER_OPTIONAL_SECRETS (non-gating): lacale → LACALE_PASSKEY, c411 → C411_PASSKEY
  tracker: {
    providers: {
      lacale: { enabled: true },
      c411: {
        enabled: true,
        economy: {
          target_ratio: 2.0,
          min_ratio: 1.0,
          min_seed_time: "72h",
          hit_and_run_grace: "0h",
        },
      },
    },
    priority: ["lacale", "c411"],
    max_total_results: 50,
    max_per_tracker: 30,
    timeout_per_tracker: 15,
  },
}
```

### Task 5.3 — Append to `.env.example`

Add at the very end of `.env.example`:

```bash
# ── Tracker passkeys (optional, non-gating — tracker-economy RP2) ──────────
# A missing passkey never deactivates a tracker. Used only by Vague-5
# seeding consumers (Ratio C1, Seed-Safety O2) once implemented.
# LACALE_PASSKEY=
# C411_PASSKEY=
```

### Task 5.4 — Append to `docs/reference/config-overlay-layout.md`

Add after the Key ownership table (end of file):

```markdown
## Tracker economy schema (tracker-economy RP2)

`tracker.json5` providers may include an optional `economy` block:

    c411: {
      enabled: true,
      economy: {
        target_ratio: 2.0,        // required; must be >= min_ratio
        min_ratio: 1.0,           // default 1.0; deletion floor (Vague 5 O2)
        min_seed_time: "72h",     // humanized string → integer seconds at load
        hit_and_run_grace: "0h",  // default "0h"; grace before H&R counting
      },
    },

Duration fields accept `"<N><unit>"` (unit `s/m/h/d/w`) or bare integer seconds.
Invalid strings raise `ValueError` at boot.

### Optional-secret convention

Announce passkeys are **non-gating**: a missing `<TRACKER>_PASSKEY` never
deactivates a tracker. Resolved via `resolve_optional_secret()` in
`api/_activation.py` — never consulted by `resolve_active()`.
See `.env.example` for variable names (`LACALE_PASSKEY`, `C411_PASSKEY`).
```

---

### Task 5.5 — Commit

```bash
git add config.example/tracker.json5 config/tracker.json5 .env.example \
        docs/reference/config-overlay-layout.md
git commit -m "feat(tracker-economy): config files, .env.example, reference doc"
```

---

## Gate exit checklist

- [ ] `config.example/tracker.json5` has commented `economy` block
- [ ] `config/tracker.json5` has live `economy` block for `c411`
- [ ] `.env.example` has `LACALE_PASSKEY` and `C411_PASSKEY` (commented)
- [ ] `docs/reference/config-overlay-layout.md` has the economy section
- [ ] Commit SHA recorded
