#!/usr/bin/env bash
# test_scripts.sh — Validates all shell scripts and verifies expected files exist.
# Exit 0 only if every check passes.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0

ok()   { echo "  PASS  $1"; ((PASS++)); }
fail() { echo "  FAIL  $1"; ((FAIL++)); }

# ── Syntax-check all .sh files ────────────────────────────────────────────────
echo "── Shell syntax (bash -n) ──────────────────────────────────────────────"
while IFS= read -r -d '' script; do
    rel="${script#"$REPO_DIR/"}"
    if bash -n "$script" 2>/dev/null; then
        ok "$rel"
    else
        fail "$rel  ← syntax error"
        bash -n "$script" || true
    fi
done < <(find "$REPO_DIR/scripts" -name "*.sh" -print0 2>/dev/null)

# ── Expected files exist ──────────────────────────────────────────────────────
echo ""
echo "── File existence ──────────────────────────────────────────────────────"
EXPECTED=(
    "deployments/docker-compose.yml"
    "scripts/install_gateway.sh"
    "scripts/setup_ssh_trust.sh"
    "scripts/setup_macbook.sh"
    "tests/test_scripts.sh"
    "tests/test_docker.sh"
    "docs/SECURITY_POLICY.md"
    "docs/DEVELOPMENT_GUIDE.md"
    "README.md"
)
for rel in "${EXPECTED[@]}"; do
    if [ -f "$REPO_DIR/$rel" ]; then
        ok "$rel"
    else
        fail "$rel  ← missing"
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
