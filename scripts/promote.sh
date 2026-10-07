#!/usr/bin/env bash
#
# promote.sh — the only way `main`, `staging` and `prod` move (git flow).
#
#   feature ──PR──▶ develop ──promote main──▶ main ──promote staging──▶ staging ──promote prod──▶ prod (+ tag v<version>)
#
# A plain script any session runs — the orchestrator or any agent — from any
# clone of the repository (the operator's ruling of 2026-10-01,
# docs/reference/operator-method.md § 3 « Environnements et back-end »).
# `main` moves when a lot is validated; `staging` and `prod` move on the
# operator's word only. Design: docs/features/git-flow/DESIGN.md § 3.1.
#
# Usage:
#   scripts/promote.sh main    [<sha>] [--dry-run]   # develop → main
#   scripts/promote.sh staging [<sha>] [--dry-run]   # main → staging
#   scripts/promote.sh prod    [<sha>] [--dry-run]   # staging → prod, then the tag v<__version__>
#   scripts/promote.sh tag             [--dry-run]   # tags prod's tip alone (after a hotfix PR)
#   scripts/promote.sh backport <name> [--dry-run]   # prod's tip + develop → backport/<name>, its merge PR into develop
#   scripts/promote.sh release         [--dry-run]   # develop's version raised one patch, in its own PR into develop
#
# The version rises once per release, never per PR (product-intent § 10-3): a
# pull request leaves `__version__` alone, so parallel PRs never conflict on it.
# When develop's version is already tagged, `release` opens the one PR that
# raises it; that PR then travels main → staging → prod like any other, and prod
# tags it.
#
# <sha> defaults to the source branch's tip. A promotion is a fast-forward of
# an EXISTING commit, pushed without --force: the branches downstream carry
# exactly the commits that were built and read upstream. It refuses, with one
# line saying why, unless:
#   1. <sha> is on the source branch;
#   2. the target's tip is an ancestor of <sha> (a fast-forward — this is what
#      refuses a promotion while a hotfix is not yet merged back);
#   3. main only: every first-parent commit it brings is the merge of a PR into
#      `develop` whose required checks (read from develop's branch rules)
#      passed at its head — the latest run of each name, as GitHub counts it,
#      concluded `success`, `skipped` or `neutral`; a commit with no PR is named.
#      Exemption: a PR listed in scripts/promote-exemptions.txt (`<number> | <reason>`,
#      added by a PR) skips the required-checks test; each one used is printed as
#      `promote: #<n> exempt — <reason>`, and an entry with no reason stops the script;
#   4. prod and tag: the `__version__` at <sha> has no tag `v<version>` yet.
#
# `--dry-run` runs every check and prints what would move, pushing nothing.
# GH overrides the `gh` command (its tests stub it); TM_GIT_NET_TIMEOUT bounds
# every network git operation (60 s); TM_PROMOTE_EXEMPTIONS points at another
# exemption list (its tests).
#
set -euo pipefail

GH="${GH:-gh}"
GIT_NET_TIMEOUT="${TM_GIT_NET_TIMEOUT:-60}"
INIT_PATH="personalscraper/__init__.py"
# fd 3 stays promote's stdout inside the command substitutions that capture fd 1.
exec 3>&1
EXEMPTIONS_FILE="${TM_PROMOTE_EXEMPTIONS:-$(dirname "${BASH_SOURCE[0]}")/promote-exemptions.txt}"

refuse() { printf 'promote: REFUSED — %s\n' "$*" >&2; exit 1; }
say() { printf 'promote: %s\n' "$*"; }
short() { git rev-parse --short "$1"; }

usage() {
  sed -n '13,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
  exit 2
}

dry_run=false
args=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=true ;;
    -h|--help) usage ;;
    *) args+=("$arg") ;;
  esac
done
[ "${#args[@]}" -ge 1 ] || usage
action="${args[0]}"
operand="${args[1]:-}"
[ "${#args[@]}" -le 2 ] || usage

git rev-parse --show-toplevel >/dev/null 2>&1 || refuse "not inside a clone of the repository"

# The remote's refs, fresh — every rule below reads origin, never a local branch.
timeout "$GIT_NET_TIMEOUT" git fetch --quiet --prune origin \
  || refuse "git fetch origin failed (network?)"

# remote_tip <branch> — the SHA of origin/<branch>, or nothing when it does not exist.
remote_tip() { git rev-parse --verify --quiet "refs/remotes/origin/$1^{commit}" || true; }

# version_at <sha> — the `__version__` the commit carries.
version_at() {
  git show "$1:$INIT_PATH" 2>/dev/null \
    | sed -n 's/^__version__[[:space:]]*=[[:space:]]*["'"'"']\([^"'"'"']*\)["'"'"'].*/\1/p' \
    | head -n 1
}

# Rule 4: the release tag of the version at <sha> does not exist on origin yet.
check_untagged() {
  local sha="$1" version
  version="$(version_at "$sha")"
  [ -n "$version" ] || refuse "no __version__ readable in $INIT_PATH at $(short "$sha")"
  if [ -n "$(timeout "$GIT_NET_TIMEOUT" git ls-remote --tags origin "refs/tags/v$version")" ]; then
    refuse "tag v$version already exists on origin — $(short "$sha") carries a released version: run scripts/promote.sh release, then promote its merge"
  fi
  printf '%s' "$version"
}

push_tag() {
  local sha="$1" version="$2"
  if $dry_run; then
    say "dry run — would tag $(short "$sha") as v$version and push the tag"
    return 0
  fi
  git tag -f -a "v$version" -m "TorrentMate v$version" "$sha" >/dev/null
  timeout "$GIT_NET_TIMEOUT" git push --quiet origin "refs/tags/v$version" \
    || refuse "pushing the tag v$version failed — prod has moved; run: scripts/promote.sh tag"
  say "tagged $(short "$sha") v$version"
}

# The contexts the `develop` branch rules require (its strict status checks).
required_checks() {
  "$GH" api "repos/{owner}/{repo}/rules/branches/develop" | python3 -c '
import json, sys
for rule in json.load(sys.stdin):
    if rule.get("type") == "required_status_checks":
        for check in rule.get("parameters", {}).get("required_status_checks", []):
            print(check["context"])
'
}

# exemption_reason <n> <list> — the reason PR <n> is exempt, or nothing. The list is
# checked whole first, so a malformed entry stops the script whichever PR it names.
exemption_reason() {
  local number="$1" list="$2" line num reason
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    num="$(printf '%s' "${line%%|*}" | tr -d '[:space:]')"
    reason="$(printf '%s' "${line#*|}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    case "$num" in ''|*[!0-9]*) refuse "exemption entry « $line » in $EXEMPTIONS_FILE has no PR number" ;; esac
    case "$line" in *'|'*) ;; *) reason="" ;; esac
    [ -n "$reason" ] || refuse "exemption entry #$num in $EXEMPTIONS_FILE has no reason"
    [ "$num" != "$number" ] || printf '%s' "$reason"
  done <<<"$list"
}

# Rule 3: every first-parent commit from main's tip to <sha> is a merged PR into
# develop whose required checks passed at its head. Prints the PR numbers.
check_pull_requests() {
  local from="$1" to="$2" required commit pr head missing exempt exemptions numbers=""
  [ -r "$EXEMPTIONS_FILE" ] || refuse "cannot read the exemption list $EXEMPTIONS_FILE"
  exemptions="$(cat "$EXEMPTIONS_FILE")"
  # Validate every entry before any PR is looked at.
  exemption_reason 0 "$exemptions" >/dev/null || exit 1
  required="$(required_checks)" || refuse "cannot read develop's branch rules through $GH"
  [ -n "$required" ] || refuse "develop's branch rules require no status check — nothing to prove a PR passed"
  for commit in $(git rev-list --first-parent --reverse "$from..$to"); do
    pr="$("$GH" api "repos/{owner}/{repo}/commits/$commit/pulls" | python3 -c '
import json, sys
commit = sys.argv[1]
for pull in json.load(sys.stdin):
    if pull.get("merge_commit_sha") == commit and pull.get("merged_at") and pull["base"]["ref"] == "develop":
        print(pull["number"], pull["head"]["sha"])
        break
' "$commit")" || refuse "cannot read the pull requests of $(short "$commit") through $GH"
    [ -n "$pr" ] || refuse "$(short "$commit") « $(git log -1 --format=%s "$commit") » is no merged PR into develop (a push that bypassed review)"
    exempt="$(exemption_reason "${pr%% *}" "$exemptions")" || exit 1
    if [ -n "$exempt" ]; then
      # fd 3 is promote's stdout: this runs inside a command substitution that captures fd 1.
      say "#${pr%% *} exempt — $exempt" >&3
      numbers="$numbers #${pr%% *}"
      continue
    fi
    head="${pr#* }"
    missing="$("$GH" api "repos/{owner}/{repo}/commits/$head/check-runs?per_page=100" | python3 -c '
import json, sys
required = sys.argv[1].split()
# GitHub counts only the latest run of a name (a run cancelled by a newer event,
# or a failure re-run green, precedes it at the same head): the most recent
# completion wins, a tie broken by the run id; a run not completed yet is the
# newest of all, and not passed. What GitHub counts as passed:
passing = {"success", "skipped", "neutral"}
latest = {}
for run in json.load(sys.stdin).get("check_runs", []):
    key = (run.get("completed_at") or "9999", run.get("id") or 0)
    if run["name"] not in latest or key > latest[run["name"]][0]:
        latest[run["name"]] = (key, run.get("conclusion"))
print(" ".join(n for n in required if n not in latest or latest[n][1] not in passing))
' "$required")" || refuse "cannot read the checks of PR #${pr%% *} through $GH"
    [ -z "$missing" ] || refuse "PR #${pr%% *} ($(short "$commit")): required checks not green at its head: $missing"
    numbers="$numbers #${pr%% *}"
  done
  printf '%s' "${numbers# }"
}

# The PR numbers squash merges wrote into the subjects between two commits.
pr_numbers_between() {
  git log --format=%s "$1..$2" | sed -n 's/.*(#\([0-9][0-9]*\))$/#\1/p' | tr '\n' ' ' | sed 's/ $//'
}

promote() {
  local target="$1" source="$2" requested="$3" sha old count prs version=""

  old="$(remote_tip "$target")"
  [ -n "$old" ] || refuse "origin/$target does not exist (the git flow's branches are created at the cut-over)"
  [ -n "$(remote_tip "$source")" ] || refuse "origin/$source does not exist"

  sha="$(git rev-parse --verify --quiet "${requested:-refs/remotes/origin/$source}^{commit}")" \
    || refuse "unknown commit: $requested"

  # Rule 1 — the commit is on the source branch.
  git merge-base --is-ancestor "$sha" "refs/remotes/origin/$source" \
    || refuse "$(short "$sha") is not on origin/$source — $target is promoted from $source only"

  if [ "$sha" = "$old" ]; then
    say "$target is already at $(short "$sha") — nothing to promote"
    return 0
  fi

  # Rule 2 — a fast-forward, never a rewrite.
  git merge-base --is-ancestor "$old" "$sha" \
    || refuse "origin/$target ($(short "$old")) is not an ancestor of $(short "$sha") — not a fast-forward (a hotfix not merged back?)"

  count="$(git rev-list --count "$old..$sha")"
  case "$target" in
    # A refusal inside a command substitution ends only its subshell: `|| exit 1` carries it out.
    main) prs="$(check_pull_requests "$old" "$sha")" || exit 1 ;;
    *) prs="$(pr_numbers_between "$old" "$sha")" ;;
  esac
  if [ "$target" = "prod" ]; then
    version="$(check_untagged "$sha")" || exit 1
  fi

  if $dry_run; then
    say "dry run — would move $target $(short "$old")..$(short "$sha") ($count commits${prs:+; PRs $prs})"
  else
    timeout "$GIT_NET_TIMEOUT" git push --quiet origin "$sha:refs/heads/$target" \
      || refuse "git push origin $(short "$sha"):$target failed"
    say "$target moved $(short "$old")..$(short "$sha") ($count commits${prs:+; PRs $prs})"
  fi

  if [ -n "$version" ]; then
    push_tag "$sha" "$version"
  fi

  case "$target" in
    staging) say "the poller deploys staging within 60 s; read it: GET https://tm-staging.iznogoudatall.xyz/api/version → « staging @ $sha »" ;;
    prod) say "the poller deploys prod within 60 s; read it: GET https://tm.iznogoudatall.xyz/api/version → « $sha »" ;;
  esac
  return 0
}

# next_patch <version> — the patch after it: 0.98.140 → 0.98.141.
next_patch() {
  printf '%s' "$1" | awk -F. '{ printf "%s.%s.%s", $1, $2, $3 + 1 }'
}

# merge_version_only <file> — resolves a conflicted file whose only conflict is
# its `__version__` line: the three sides merge with that line masked, and the
# mask is left in place for the caller to fill. Fails when anything else conflicts.
merge_version_only() {
  local file="$1" dir side
  dir="$(mktemp -d)"
  for side in 1 2 3; do
    git show ":$side:$file" 2>/dev/null \
      | sed 's/^__version__[[:space:]]*=.*/__version__ = "@VERSION@"/' >"$dir/$side" \
      || { rm -rf "$dir"; return 1; }
  done
  if git merge-file -p "$dir/2" "$dir/1" "$dir/3" >"$file"; then
    rm -rf "$dir"
    return 0
  fi
  rm -rf "$dir"
  return 1
}

# The hotfix's merge-back (DESIGN § 3.7 step 3): prod's tip merged with develop
# on backport/<name>, then merged into develop by a MERGE commit so prod becomes
# an ancestor of develop. Prod's X.Y.Z.1 always conflicts with develop's
# X.Y.(Z+n) on `__version__`: the merge keeps develop's — the next release
# raises it. Any other conflict is the hand's: nothing is pushed.
backport() {
  local name="$1" prod develop version url
  [ -n "$name" ] || usage
  printf '%s' "$name" | grep -Eq '^[A-Za-z0-9._-]+$' || refuse "backport name '$name' — letters, digits, . _ - only"
  prod="$(remote_tip prod)"
  develop="$(remote_tip develop)"
  [ -n "$prod" ] || refuse "origin/prod does not exist"
  [ -n "$develop" ] || refuse "origin/develop does not exist"
  git merge-base --is-ancestor "$prod" "$develop" \
    && refuse "origin/prod ($(short "$prod")) is already on develop — nothing to bring back"
  [ -z "$(remote_tip "backport/$name")" ] || refuse "origin/backport/$name already exists"
  version="$(version_at "$develop")"
  [ -n "$version" ] || refuse "no __version__ readable in $INIT_PATH at develop $(short "$develop")"

  # The merge is built in a throwaway worktree: the caller's checkout is never touched.
  # `tree` is global: the EXIT trap runs after this function has returned.
  tree="$(mktemp -d)"
  trap 'git worktree remove --force "$tree" >/dev/null 2>&1 || true; rm -rf "$tree"' EXIT
  git worktree add --quiet --detach "$tree" "$prod" >/dev/null 2>&1 \
    || refuse "cannot check out prod $(short "$prod") in a temporary worktree"
  (
    cd "$tree"
    local conflicts file
    git merge --quiet --no-ff --no-commit "$develop" >/dev/null 2>&1 || true
    conflicts="$(git diff --name-only --diff-filter=U)"
    while IFS= read -r file; do
      [ -n "$file" ] || continue
      if [ "$file" != "$INIT_PATH" ] || ! merge_version_only "$file"; then
        refuse "backport/$name: $file conflicts beyond __version__ — nothing pushed; merge origin/develop into prod's tip by hand and resolve it"
      fi
    done <<<"$conflicts"
    sed "s/^__version__[[:space:]]*=.*/__version__ = \"$version\"/" "$INIT_PATH" >"$INIT_PATH.new"
    mv "$INIT_PATH.new" "$INIT_PATH"
    git add -A
    git commit --quiet -m "chore($name): merge prod's hotfix back into develop" \
      || refuse "backport/$name: committing the merge failed — nothing pushed"
  ) || exit 1
  [ "$(version_at "$(git -C "$tree" rev-parse HEAD)")" = "$version" ] \
    || refuse "backport/$name: the merge does not carry develop's $version — nothing pushed"

  if $dry_run; then
    say "dry run — would push prod $(short "$prod") merged with develop $(short "$develop") (version $version kept) to backport/$name and open its merge PR into develop"
    return 0
  fi
  timeout "$GIT_NET_TIMEOUT" git push --quiet origin "$(git -C "$tree" rev-parse HEAD):refs/heads/backport/$name" \
    || refuse "git push origin backport/$name failed — nothing pushed"
  say "backport/$name pushed: prod $(short "$prod") merged with develop $(short "$develop"), version $version kept"
  url="$("$GH" pr create --base develop --head "backport/$name" \
    --title "chore($name): merge prod's hotfix back into develop" \
    --body "Merge-back of prod $(short "$prod") into develop (docs/features/git-flow/DESIGN.md § 3.7). MERGE method, never squash: prod's tip must become an ancestor of develop. The __version__ conflict is resolved to develop's $version.")" \
    || refuse "backport/$name pushed, but opening its PR failed — open it by hand: --base develop, merge method"
  "$GH" pr merge "$url" --auto --merge >/dev/null \
    || refuse "backport/$name pushed and PR $url opened, but arming auto-merge FAILED — arm it: gh pr merge $url --auto --merge"
  say "backport/$name → develop: $url, auto-merge armed (merge commit)"
}

# The release bump: develop's version raised one patch on release/<version>, in
# its own PR into develop (squash, auto-merge). Only when develop's version is
# already tagged — an unreleased version is released as it is.
release() {
  local develop version bumped branch url
  develop="$(remote_tip develop)"
  [ -n "$develop" ] || refuse "origin/develop does not exist"
  version="$(version_at "$develop")"
  [ -n "$version" ] || refuse "no __version__ readable in $INIT_PATH at develop $(short "$develop")"
  if [ -z "$(timeout "$GIT_NET_TIMEOUT" git ls-remote --tags origin "refs/tags/v$version")" ]; then
    say "develop carries $version, not released yet — nothing to raise; promote it as it is"
    return 0
  fi
  bumped="$(next_patch "$version")"
  branch="release/$bumped"
  [ -z "$(remote_tip "$branch")" ] || refuse "origin/$branch already exists — its PR is the release bump"

  # `tree` is global: the EXIT trap runs after this function has returned.
  tree="$(mktemp -d)"
  trap 'git worktree remove --force "$tree" >/dev/null 2>&1 || true; rm -rf "$tree"' EXIT
  git worktree add --quiet --detach "$tree" "$develop" >/dev/null 2>&1 \
    || refuse "cannot check out develop $(short "$develop") in a temporary worktree"
  (
    cd "$tree"
    sed "s/^__version__[[:space:]]*=.*/__version__ = \"$bumped\"/" "$INIT_PATH" >"$INIT_PATH.new"
    mv "$INIT_PATH.new" "$INIT_PATH"
    git commit --quiet -am "chore(release): version $bumped" \
      || refuse "$branch: committing the bump failed — nothing pushed"
  ) || exit 1

  if $dry_run; then
    say "dry run — would push develop $(short "$develop") with version $version → $bumped to $branch and open its PR into develop"
    return 0
  fi
  timeout "$GIT_NET_TIMEOUT" git push --quiet origin "$(git -C "$tree" rev-parse HEAD):refs/heads/$branch" \
    || refuse "git push origin $branch failed — nothing pushed"
  url="$("$GH" pr create --base develop --head "$branch" \
    --title "chore(release): version $bumped" \
    --body "The release bump (scripts/promote.sh release): develop's $version is tagged, the next release carries $bumped.")" \
    || refuse "$branch pushed, but opening its PR failed — open it by hand: --base develop"
  "$GH" pr merge "$url" --auto --squash >/dev/null \
    || refuse "$branch pushed and PR $url opened, but arming auto-merge FAILED — arm it: gh pr merge $url --auto --squash"
  say "$branch → develop: $url, auto-merge armed"
}

case "$action" in
  main) promote main develop "$operand" ;;
  staging) promote staging main "$operand" ;;
  prod) promote prod staging "$operand" ;;
  tag)
    [ -z "$operand" ] || usage
    tip="$(remote_tip prod)"
    [ -n "$tip" ] || refuse "origin/prod does not exist"
    version="$(check_untagged "$tip")" || exit 1
    push_tag "$tip" "$version"
    ;;
  backport) backport "$operand" ;;
  release)
    [ -z "$operand" ] || usage
    release
    ;;
  *) usage ;;
esac
