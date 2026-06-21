# Repo safety — never lose code

Three operator rules (2026-06-21), born from losing uncommitted UI work to a
rebuild:

## 1. Obligation de commit

**Le code doit toujours être commité.** Nothing of value lives only in a working
tree: uncommitted changes are invisible to git and are destroyed by a
checkout / reset / rebuild. Commit early and often, on a branch.

- The deploy guardrail (`scripts/deploy.sh`) **refuses to build a dirty tree**, so
  uncommitted code can never be served.
- The branch guard below ensures that once committed, your work cannot be
  silently deleted before it is pushed and merged.

## 2. Interdiction de nettoyer une branche locale non sauvegardée

**On ne supprime une branche locale QUE si elle est poussée sur `origin` ET
mergée dans `main`.** A branch that holds un-pushed or un-merged commits must not
be deleted — those commits would be lost.

This is enforced **hard** by the `hooks/reference-transaction` git hook: it
aborts the deletion of any `refs/heads/<b>` unless `origin/<b>` exists _and_ the
branch tip is an ancestor of `main`. It catches `git branch -D`,
`git update-ref -d`, worktree-branch pruning — any path.

### Activation (once per clone)

```bash
./scripts/install-git-guards.sh   # sets core.hooksPath → hooks/
```

Run it in the deploy clone and in each dev clone. To delete a branch it blocks,
satisfy the rule first: `git push -u origin <branch>` (and/or merge it to main).

## 3. Rétro-compatibilité de l'état on-disk (rend le staging-sur-prod sûr)

The **staging** instance (`scripts/deploy-staging.sh`, subdomain
`km-staging.iznogoudatall.xyz`) runs a not-yet-merged feature build against the
**real prod root** (`~/.kanban-km`) — there is **no test board**: a card move /
config edit in the staging UI applies for real, even mid-feature-test (operator
rule). For that to be safe, **a feature must never break the on-disk state/config
format**: changes must be **backward-compatible** (additive fields, versioned
docs — as `board.json`'s `version` field and `projects.json`'s default-tolerant
loader already are), so the feature build (staging) and the prod daemon (`main`)
read/write the same files without corrupting each other.

If a feature genuinely needs an incompatible format change, handle it as an
**explicit versioned migration** — never by faking the board.

> Combined with the deploy discipline ([deployment.md](deployment.md)), the loop
> is closed: code is always committed → branches can't be lost before push+merge
> → only clean `main` is ever served in prod, and non-main is tested on staging
> against the real board.
