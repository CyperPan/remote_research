#!/usr/bin/env bash
# test_docker.sh — Validates the docker-compose configuration.
# Requires docker and the docker compose plugin to be installed.
# Exit 0 only if the compose file is valid.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_DIR/deployments/docker-compose.yml"
PASS=0
FAIL=0

ok()   { echo "  PASS  $1"; ((PASS++)); }
fail() { echo "  FAIL  $1"; ((FAIL++)); }

# ── Tool availability ─────────────────────────────────────────────────────────
echo "── Tool checks ─────────────────────────────────────────────────────────"
if command -v docker &>/dev/null; then
    ok "docker installed ($(docker --version | head -1))"
else
    fail "docker not found — install Docker Desktop or Docker Engine"
fi

COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    ok "docker compose plugin available"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    ok "docker-compose (v1) available"
else
    fail "neither 'docker compose' nor 'docker-compose' found"
fi

# ── Compose file validation ───────────────────────────────────────────────────
echo ""
echo "── Compose config validation ───────────────────────────────────────────"
if [ -f "$COMPOSE_FILE" ]; then
    ok "compose file exists: deployments/docker-compose.yml"
    if [ -n "$COMPOSE_CMD" ]; then
        if $COMPOSE_CMD -f "$COMPOSE_FILE" config --quiet 2>/dev/null; then
            ok "docker compose config — valid YAML"
        else
            fail "docker compose config — invalid (see output above)"
            $COMPOSE_CMD -f "$COMPOSE_FILE" config || true
        fi
    fi
else
    fail "compose file missing: deployments/docker-compose.yml"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
