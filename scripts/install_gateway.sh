#!/usr/bin/env bash
# install_gateway.sh — Idempotent Jetson Orin Nano bastion-host setup
# Installs Tailscale and starts the ttyd container.
# Docker and Docker Compose are pre-installed on this device — skipped automatically.
# Safe to re-run; each step checks before acting.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Updating package lists"
sudo apt-get update -qq

echo "==> Installing curl (required for installers)"
sudo apt-get install -y curl

# ── Docker ───────────────────────────────────────────────────────────────────
# Docker 29.x and Docker Compose v2 are already installed on the Jetson Orin Nano.
if command -v docker &>/dev/null; then
    echo "==> Docker already installed: $(docker --version)"
else
    echo "==> Installing Docker via get.docker.com"
    curl -fsSL https://get.docker.com | sudo sh
fi

# Add current user to docker group so docker commands work without sudo
if ! groups | grep -q docker; then
    echo "==> Adding $USER to docker group (re-login required for this to take effect)"
    sudo usermod -aG docker "$USER"
else
    echo "==> $USER is already in the docker group — OK"
fi

# ── Tailscale ────────────────────────────────────────────────────────────────
if command -v tailscale &>/dev/null; then
    echo "==> Tailscale already installed: $(tailscale version | head -1)"
else
    echo "==> Installing Tailscale via official script"
    curl -fsSL https://tailscale.com/install.sh | sudo sh
fi

echo ""
echo "==> Tailscale is installed. If not yet authenticated, run:"
echo "    sudo tailscale up"
echo "    Then visit the URL shown to authorise this device."
echo ""

# ── ttyd container ───────────────────────────────────────────────────────────
echo "==> Starting ttyd container via docker compose"
cd "$REPO_DIR/deployments"
docker compose up -d

echo ""
echo "==> Done. ttyd is running on port 7681."
echo "    Access via: http://<tailscale-ip>:7681"
echo "    Get your Tailscale IP with: tailscale ip -4"
