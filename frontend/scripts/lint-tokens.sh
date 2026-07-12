#!/usr/bin/env bash
#
# lint:tokens (C19) — fail on hardcoded colours outside the DS token source.
#
# The design system's colours live ONLY in src/styles/ps/tokens/ (raw oklch/hex)
# and are consumed everywhere else via var(--…) tokens. This guard greps the
# shipped .ts/.tsx/.css for raw colour literals so a stray #hex / oklch() /
# rgb() / hsl() can never re-enter product UI unnoticed. Runs in lint:ds (CI).
#
# Excluded (each justified):
#   - src/styles/ps/tokens/**           the token source itself (raw colours belong here)
#   - src/api/schema.d.ts               generated from OpenAPI (doc comments like "#235")
#   - **/*.test.ts(x)                   test fixtures/strings (e.g. "TMDB #550"), never styled
#   - src/components/StagingBanner.tsx  a deliberately theme-INDEPENDENT ops overlay
#                                       (documented DS exception in the file header)
set -euo pipefail

cd "$(dirname "$0")/.."

# #rgb / #rgba / #rrggbb / #rrggbbaa, plus the functional colour notations.
PATTERN='#[0-9a-fA-F]{3,8}\b|oklch\(|rgba?\(|hsl\('

# rg exits 1 when there are no matches; `|| true` keeps set -e from aborting.
matches=$(rg -n --no-heading "$PATTERN" \
  -g '*.tsx' -g '*.ts' -g '*.css' \
  -g '!src/styles/ps/tokens/**' \
  -g '!src/api/schema.d.ts' \
  -g '!**/*.test.ts' \
  -g '!**/*.test.tsx' \
  -g '!src/components/StagingBanner.tsx' \
  src || true)

if [[ -n "$matches" ]]; then
  echo "✗ lint:tokens — hardcoded colour(s) found outside src/styles/ps/tokens/:" >&2
  echo "$matches" >&2
  echo "" >&2
  echo "Use a DS token — var(--…) defined in src/styles/ps/tokens/ (see C19)." >&2
  exit 1
fi

echo "✓ lint:tokens — no hardcoded colours outside the DS token source."
