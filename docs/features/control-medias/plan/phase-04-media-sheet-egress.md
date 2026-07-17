# Phase 04 — Media-sheet egress actions

**Gate:** Every `StagingMediaDetail` state shows ≥1 action; « Relancer et terminer » → 202; « Ignorer / nettoyer » → journal row.

## Sub-phases

### 4.1 — API client: continue + discard hooks

**Commit:** `feat(control-medias): add useContinueMedia + useDiscardMedia hooks`

**File:** `frontend/src/api/client.ts`

Add two new mutation functions (following the existing `enqueueStagingDecision` pattern at the `staging` key section):

```typescript
// POST /api/staging/media/{id}/continue
export function continueMedia(id: string): Promise<ContinueResponse> {
  return apiPost(`/api/staging/media/${encodeURIComponent(id)}/continue`);
}

// POST /api/staging/media/{id}/discard
export function discardMedia(id: string): Promise<DiscardResponse> {
  return apiPost(`/api/staging/media/${encodeURIComponent(id)}/discard`);
}
```

**File:** `frontend/src/api/client.ts` — add `ContinueResponse` + `DiscardResponse` types (generated from `schema.d.ts` already updated in phases 01–02).

**File (NEW):** `frontend/src/hooks/useContinueMedia.ts` — TanStack mutation wrapping `continueMedia`, invalidating `stagingMediaKeys.all` + `decisionsKeys.all` + `pipelineStagesKeys.stages` on success (same invalidation pattern as `enqueueStagingDecision`).

**File (NEW):** `frontend/src/hooks/useDiscardMedia.ts` — mutation wrapping `discardMedia`, invalidating `stagingMediaKeys.all` on success.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 4.2 — StagingMediaDetail: continue action (matched + blocked)

**Commit:** `feat(control-medias): add 'Relancer et terminer' action for matched+blocked media`

**File:** `frontend/src/components/staging/StagingMediaDetail.tsx`

After the existing « Résoudre le matching » button (~line 252), add:

```tsx
{
  /* §5.2 continuation for matched-but-blocked items (verify-gate refusal, etc.) */
}
{
  item.match === "matched" && item.blocked_reason != null && (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        disabled={continueMut.isPending}
        onClick={() => continueMut.mutate(item.id)}
      >
        {continueMut.isPending ? "Envoi…" : "Relancer et terminer le pipeline"}
      </Button>
      {continueMut.isSuccess && continueMut.data.deferred && (
        <p className="text-xs text-muted-foreground">
          En file — un autre run est en cours. Le pipeline reprendra
          automatiquement.
        </p>
      )}
    </div>
  );
}
```

For `matched` + clean (NOT blocked), add a secondary menu entry « Re-scraper cet élément » in a `DropdownMenu` that calls the SAME `continueMut.mutate(item.id)`. Both labels invoke the same §5.2 endpoint — contextual wording only.

Import `useContinueMedia` hook, wire the mutation with toast notifications (success: 202 → "Pipeline relancé", deferred → "En file — run en cours").

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 4.3 — StagingMediaDetail: discard action (other + unknown kind)

**Commit:** `feat(control-medias): add 'Ignorer / nettoyer' action for non-media artifacts`

**File:** `frontend/src/components/staging/StagingMediaDetail.tsx`

After the Film/Série chooser for `other` items (~line 256 area), add:

```tsx
{
  /* §7 — non-media artifact egress: confirmation dialog + journal-backed discard */
}
{
  needsKind && (
    <IgnoreDiscardButton
      mediaId={item.id}
      onSuccess={() => onResolve?.()} // close sheet after discard
    />
  );
}
```

**File (NEW):** `frontend/src/components/staging/IgnoreDiscardButton.tsx`

A self-contained component: renders « Ignorer / nettoyer » danger-outline button → opens a Dialog with FR confirmation text (« Ce dossier ne contient pas un média identifiable... ») → on confirm, calls `discardMedia(id)` → on success toast "Nettoyé" + invalidates staging query.

**File (NEW):** `frontend/src/components/staging/IgnoreDiscardButton.test.tsx` — renders dialog, confirms, asserts mutation called.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 4.4 — Sheet egress tests

**Commit:** `test(control-medias): egress actions — continue + discard in media sheet`

**File (NEW):** `frontend/src/components/staging/StagingMediaDetail.test.tsx`

Tests:

- Matched+blocked item renders « Relancer et terminer » button
- Matched+clean item has secondary « Re-scraper » menu entry
- Non-`other` item does NOT render « Ignorer / nettoyer »
- `other` item renders the Film/Série chooser AND « Ignorer / nettoyer »
- Clicking « Ignorer » opens confirmation dialog

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`
