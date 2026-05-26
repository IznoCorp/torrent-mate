# Drafts — Scope-Drift Preservation

> Operator + agent scratchpad for findings produced **out-of-scope** by sub-agents during tech-debt 0.16.0 execution. Never delete — promote or archive.

## Why this exists

During Phases 2-5, a dispatched sub-agent produced `audit/12-ntfs-cache-pressure.md` while working on a different sub-phase (2.6 backfill-ids CLI). The file was out-of-scope for 2.6, was deleted by the orchestrator (correct decision per scope-bound discipline), but the **content was valuable** — the operator later asked to recreate it manually.

Information was lost. This directory exists so that doesn't happen again.

## Policy

**For orchestrators handling a sub-agent's scope drift** :

1. **NEVER delete** an out-of-scope artifact silently.
2. Move it here :
   ```bash
   git mv <out-of-scope-file> docs/features/tech-debt/drafts/<original-name>
   git commit -m "chore(tech-debt-drafts): preserve out-of-scope finding from <sub-phase-N.M>"
   ```
3. Surface to the operator with 3 options :
   - **Promote** : create a new sub-phase to integrate the finding (e.g. Phase 5.9 NTFS was promoted from a drift).
   - **Archive** : `git mv` to `docs/archive/drafts/` with a note explaining why it's not actionable.
   - **Discard** : `git rm` only after operator explicit ACK.

**For sub-agents who notice they're drifting** :

If you realize mid-task that you're producing something outside your sub-phase scope but think it has value, output it to `drafts/<descriptive-name>.md` instead of mixing it with your sub-phase commit. Note it in your report under "Out-of-scope findings". The orchestrator will route it per the policy above.

## Lifecycle

- **Active drafts** : files in this directory awaiting promote / archive / discard decision.
- **Promoted** : moved to `audit/NN-*.md` or integrated into a phase file. Removed from `drafts/`.
- **Archived** : moved to `docs/archive/drafts/<feature>/`. Removed from `drafts/`.
- **Discarded** : `git rm` after operator ACK. Disappears from `drafts/` but preserved in git history.

## Current contents

(Empty at creation time. As of 2026-05-23, `audit/12-ntfs-cache-pressure.md` is the only known prior drift — it was recreated by the operator and committed directly to `audit/`, bypassing this directory.)
