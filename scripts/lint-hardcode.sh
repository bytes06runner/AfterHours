#!/usr/bin/env bash
# Fails if a 40-hex address or an http(s) URL appears in source outside the allowed places.
#
# Allowed: config/, deployments/, docs/, any tests/ or test/ directory, *.test.* and *.t.sol
# files, generated or vendored folders, lockfiles, markdown and the kit's tooling files.
# A line may opt out with the marker `hardcode-ok` plus a reason, for protocol constants
# copied from verified source (CLAUDE.md, "Allowed literals").
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

pattern='0x[0-9a-fA-F]{40}|https?://'

hits=$(git ls-files --cached --others --exclude-standard \
  | grep -Ev '^(config|deployments|docs|data|artifacts|updates)/' \
  | grep -Ev '(^|/)(tests?|__tests__|__fixtures__|lib|node_modules|\.next|out|cache)/' \
  | grep -Ev '\.(test|spec)\.[jt]sx?$|\.t\.sol$|\.md$|\.lock$|-lock\.yaml$|\.ico$|\.png$|\.svg$' \
  | grep -Ev '^(\.mcp\.json|\.claude/|\.gitmodules$|contracts/foundry\.lock$)' \
  | while IFS= read -r f; do
      [ -f "$f" ] || continue
      grep -EnH "$pattern" "$f" | grep -v 'hardcode-ok' || true
    done)

if [ -n "$hits" ]; then
  echo "lint-hardcode: literals found outside config/ and deployments/:" >&2
  echo "$hits" >&2
  exit 1
fi
echo "lint-hardcode: clean"
