# Phase 03 — Config polish (G2 + Secrets + FR)

**Goal**: Apply the three Config defects from the design overhaul:

1. First file auto-selected (G2) — no more "Sélectionnez un fichier dans la liste" dead start.
2. Secrets becomes a sibling tab of the file list (G2) — no more scroll-to-find below the editor.
3. Restart hint tap-accessible (E3) — the "Redémarrage requis" chip gets a visible explanation,
   no hover-only.
4. Secret descriptions translated to French (E3).

**Constitution served**: §3.3, G2, E3, DOIT-2 (tap-accessible reasons), DOIT-9.

## Surface

| File                                            | Action                                                        |
| ----------------------------------------------- | ------------------------------------------------------------- |
| `frontend/src/pages/Config.tsx`                 | Auto-select first file; Secrets tab restructure; restart hint |
| `frontend/src/components/config/SecretsTab.tsx` | FR descriptions, tab mode (not bottom section)                |
| `frontend/src/pages/Config.test.tsx`            | Update assertions for auto-select + Secrets tab               |

## Sub-phases

### 3.1 — First file auto-selected + Secrets sibling tab

**Commit**: `feat(systeme-hub): auto-select first config file, restructure Secrets as sibling tab`

**First file auto-select (G2)**:

In `Config.tsx`, when the page mounts and `selectedFile === null` (no `?file=` in URL), select
the first file from `filesQ.data?.files`:

```typescript
// In Config(), after all hooks are set up:
useEffect(() => {
  if (selectedFile === null && filesQ.data && filesQ.data.files.length > 0) {
    // Auto-select the first file only when the user hasn't explicitly chosen one.
    // Don't push into history (replace: true keeps Back predictable).
    const first = filesQ.data.files[0];
    if (first) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("file", first.name);
          return next;
        },
        { replace: true },
      );
    }
  }
}, [selectedFile, filesQ.data, setSearchParams]);
```

The `selectedFile === null` guard ensures:

- First visit → auto-selects first file.
- User explicitly navigates back (clears `?file=`) → auto-selects again.
- User has a `?file=Nonexistent` → stays null (the file list handles the missing case).

**Secrets sibling tab**:

Today SecretsTab is a bottom section below the two-panel editor. Restructure as a sibling tab
in the file list sidebar:

```
┌──────────────────────────────────────────────┐
│ Configuration                                │
├──────────┬───────────────────────────────────┤
│ FileList │ SchemaForm editor                 │
│ (tabs:   │                                   │
│  Fichiers│                                   │
│  Secrets)│                                   │
├──────────┴───────────────────────────────────┤
│ (Secrets content when Secrets tab active)    │
└──────────────────────────────────────────────┘
```

Implementation: add a segmented control at the top of the left sidebar with two options:

```typescript
// Left sidebar tab state (separate from URL; purely local UI state)
const [leftTab, setLeftTab] = useState<"files" | "secrets">("files");
```

When `leftTab === "files"`, render the FileList (current behavior).
When `leftTab === "secrets"`, render SecretsTab in the left panel (replacing FileList).

Remove the bottom `<SecretsTab>` section from the page return.

This also changes the mobile dropdown to include a "Secrets" option — the mobile Select
selector already shows files; add a separator + "Secrets" entry that sets `leftTab` to secrets
and clears the file selection.

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run -- src/pages/Config.test.tsx
```

### 3.2 — Restart hint tap-accessible + FR secret descriptions

**Commit**: `feat(systeme-hub): tap-accessible restart hint, French secret descriptions`

**Restart hint (E3)**:

Today the restart-required chip on file changes is a dismissible banner. Add a visible,
always-rendered microcopy line below the restart banner button:

```tsx
// In the restart-required banner:
{restartRequired && (
  <div ...>
    <div ...>
      <p>
        <span className="font-medium">Redémarrage requis</span>
        {" "}— <span className="text-muted-foreground">Redémarrage requis après modification</span>
      </p>
      ...
    </div>
    ...
  </div>
)}
```

The key phrase "Redémarrage requis après modification" is always visible — no hover-only
tooltip (DOIT-9). The existing stale-files list stays as-is.

**FR secret descriptions (E3)**:

In `SecretsTab.tsx`, ensure every secret `description` property rendered in the UI is in
French. If the backend serves English descriptions, map them client-side:

```typescript
/** Map backend secret descriptions to French. */
const FR_DESCRIPTIONS: Record<string, string> = {
  "TMDB API key for scraping metadata":
    "Clé API TMDB pour le scraping de métadonnées",
  "TVDB API key for scraping metadata":
    "Clé API TVDB pour le scraping de métadonnées",
  "qBittorrent password": "Mot de passe qBittorrent",
  // ... add every known description
};
```

Alternatively, if the descriptions are already FR or are dynamic, add a fallback that
leaves them as-is. Check the real backend response first:

```bash
# Verify what descriptions the /api/config/secrets endpoint returns
```

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run
```

### Files-in-scope summary

| Phase | Files touched | New files | Deleted files |
| ----- | ------------- | --------- | ------------- |
| 3.1   | 1             | 0         | 0             |
| 3.2   | 2             | 0         | 0             |

**Total**: 3 files modified. All frontend-only, zero backend.
