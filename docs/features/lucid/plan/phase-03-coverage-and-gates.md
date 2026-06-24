# Phase 3 — Coverage audit & verification gates

> Covers DESIGN §5.4 (coverage audit — add tooltips on icon-only/ambiguous controls) and §7
> (all 5 verification gates including staging build/deploy). After this phase `lucid` is
> ready for the feature PR.

## Gate

**Phase 2 must have produced:** All 39 native `title=` migrated to `<Tooltip>` across 15 files;
`rg native title=` gate returns 0; i18n keys for migrated sites present in both `en.yaml` and
`fr.yaml` with key-set parity; `make lint` and `make test` green.

---

### Sub-phase 3.1 — Coverage audit: add tooltips on icon-only / ambiguous controls

**DESIGN:** §5.4 (exhaustive audit), §3 context (DS `<Tooltip>` already has 24 existing consumers
— those are fine, this is for uncovered controls).

**Files to audit:** The 15 migration files from §3 + `DaemonPanel.jsx` + `IssuesPanel.jsx`
(neither in the migration list — may have icon-only controls).

**What to look for:**

1. **Icon-only buttons** — any `<button>` or `<IconButton>` with no visible label, no `aria-label`,
   and no enclosing `<Tooltip>`.
2. **Ambiguous controls** — a button whose purpose isn't obvious from its icon alone (e.g. a gear
   icon that could mean "settings", "configure", or "options").
3. **Controls that already have `<Tooltip>`** — skip; the 24 existing DS `<Tooltip>` consumers are
   already covered.

**How to add (pattern identical to Phase 2):**

```jsx
<Tooltip label={t("tip.<new_key>", "Terse imperative hint")}>
  <IconButton icon={SomeIcon} onClick={…} />
</Tooltip>
```

**Wording convention** (DESIGN §5.4): terse imperative hint, verb-first, no trailing period, ≤ ~6
words. Examples: "Edit the description", "Close the panel", "Open settings".

**Commit:** `feat(lucid): add tooltips on icon-only and ambiguous controls (coverage audit)`

---

### Sub-phase 3.2 — Complete i18n (keys from coverage audit + key-set parity)

**DESIGN:** §5.4 (i18n), gate 3 (§7).

**Files:** Modify `web/src/i18n/en.yaml`, `web/src/i18n/fr.yaml`

1. Collect every `t("tip.<key>", "…")` call introduced in sub-phase 3.1 (coverage additions) using
   a key not already in the `tip:` namespace.
2. Add each new key + English text to `en.yaml` under `tip:`.
3. Add each new key + French translation to `fr.yaml` under `tip:`.
4. Assert **key-set parity**: the set of keys under `tip:` in `en.yaml` equals the set in `fr.yaml`.

**Parity assertion** (same script as gate 3 below — run after adding keys):
```bash
python3 -c "import yaml;en=yaml.safe_load(open('web/src/i18n/en.yaml'))['tip'];fr=yaml.safe_load(open('web/src/i18n/fr.yaml'))['tip'];assert set(en.keys())==set(fr.keys()),f'en≠fr:{set(en)^set(fr)}';print(f'OK: {len(en)} keys each')"
```

**Commit:** `feat(lucid): add i18n keys for coverage audit additions (en+fr parity)`

---

### Sub-phase 3.3 — Run all 5 verification gates (§7)

**DESIGN §7.** All gates must pass before the feature PR.

**Gate 1 — Lint/test:**
```bash
make lint && make test
```
Expected: zero errors. `tests/web/test_design_system_contract.py` must pass (Tooltip export intact).

**Gate 2 — No native `title=` left (tag-aware):** the line proxy
`rg 'title=' | rg -v '<[A-Z]'` is invalid (false-positives multi-line component-prop `title=` — DESIGN
§3). Walk each `title=` to its opening tag and assert **0** sit on a lowercase intrinsic element:
```bash
python3 - <<'PY'
import re, glob
tag=re.compile(r'<([A-Za-z][A-Za-z0-9.]*)')
native=[]
for path in glob.glob('web/src/**/*.jsx', recursive=True):
    if '/ds/' in path: continue
    L=open(path).read().splitlines()
    for i,line in enumerate(L):
        if re.search(r'(?<![A-Za-z])title=', line):
            t=None; j=i
            while j>=0:
                m=None
                for mm in tag.finditer(L[j]): m=mm
                if m and (j<i or m.start()<line.index('title=')): t=m.group(1); break
                j-=1
            if t and t[0].islower(): native.append(f"{path}:{i+1}")
print('native intrinsic-DOM title= remaining:', len(native)); [print(' ',n) for n in native]
PY
```
Expected: **0**. If any remain, return to Phase 2 and migrate them.

**Gate 3 — i18n key-set parity:**
```bash
python3 -c "
import yaml
en = yaml.safe_load(open('web/src/i18n/en.yaml'))['tip']
fr = yaml.safe_load(open('web/src/i18n/fr.yaml'))['tip']
assert set(en.keys()) == set(fr.keys()), f'en≠fr: {set(en)^set(fr)}'
print(f'OK: {len(en)} keys each')
"
```
Also verify every `t("tip.<k>", …)` call site in `web/src` has a matching key in both bundles.

**Gate 4 — Tokens present:**
```bash
# colors.css defines both tokens in both scopes
rg -c '--tooltip-bg' web/src/ds/tokens/colors.css  # expect 2
rg -c '--tooltip-text' web/src/ds/tokens/colors.css # expect 2
# Bundle Tooltip no longer references the old tokens
rg '--surface-inverse|--text-inverse' web/src/ds/_ds_bundle.js -g '*2008*' -g '*2095*'
# ^ expect 0 matches inside the Tooltip function
rg 'var\(--tooltip-bg\)' web/src/ds/_ds_bundle.js   # expect >=1 match
```

**Gate 5 — Staging build & deploy (live visual check):**
```bash
cd web && npm run build                 # vite build → src/kanbanmate/webui/
cd ~/staging/kanban-mate \
  && git remote update --prune origin \
  && git reset --hard origin/staging \
  && PATH="$HOME/staging/venv/bin:$PATH" bash scripts/deploy-staging.sh
```
Open `https://km-staging.iznogoudatall.xyz` in a real browser. Confirm in **both themes**
(light and dark, via the ThemeSwitcher at top-right):
- [ ] Tooltip text is legible (dark bubble/light text in light mode; light bubble/dark text in
  dark mode — the "noir sur noir" bug is gone).
- [ ] Hover opens a tooltip; **tap** (mobile devtools or real device) opens a tooltip.
- [ ] A screen reader (VoiceOver or devtools accessibility tree) announces the hint on a
  previously icon-only control.
- [ ] No native browser tooltip (`title=`) appears anywhere — only the styled DS bubble.

**Commit:** None — verification-only sub-phase. If any gate fails, fix the corresponding source
file and re-commit in the earlier sub-phase's scope.

---

### Phase 3 completion — ready for feature PR

Gate status at PR time (the `lucid` build):

- **Gate 1 (lint/test):** `make lint` green; the relevant web test
  `tests/web/test_design_system_contract.py` passes. (The repo-wide `make test` in this *agent
  worktree* reports failures that are env artifacts — the editable install resolves to the dev clone,
  and the kanban-helper tests are refused by the #76 worktree pin; all pass against `PYTHONPATH=src`,
  i.e. what CI runs.)
- **Gate 2 (no native `title=`):** tag-aware scan → **0** native intrinsic-DOM `title=`.
- **Gate 3 (i18n parity):** `tip:` key-sets identical in en/fr (**29** keys each); 6 new `tip.md_*`
  keys added with FR translations.
- **Gate 4 (tokens):** `--tooltip-bg`/`--tooltip-text` present in both theme scopes; bundle Tooltip
  references them and no longer reads `--surface-inverse`/`--text-inverse`.
- **Gate 5 (live staging visual check):** the SPA `vite build` succeeds; the build/deploy +
  both-theme browser confirmation is the **operator checkpoint** (staging deploy is a heavy outward
  action, run via `scripts/deploy-staging.sh` per CLAUDE.md) — left for the human reviewer.

Gates 1–4 pass; gate 5 is the operator staging check. `lucid` is feature-PR-ready.
