#!/usr/bin/env bash
# setup_macbook.sh — Run on the MacBook (target / AI host)
# Clones Ninglo/remotelab, installs dependencies, and creates .env template.

set -euo pipefail

REMOTELAB_DIR="$HOME/remotelab-server"
REMOTELAB_REPO="https://github.com/Ninglo/remotelab"
MIN_NODE_MAJOR=18

# ── Node.js version check ─────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js is not installed."
    echo "Install Node.js >= $MIN_NODE_MAJOR from https://nodejs.org or via:"
    echo "  brew install node   (Homebrew)"
    echo "  nvm install 20      (nvm)"
    exit 1
fi

NODE_MAJOR="$(node -e 'process.stdout.write(process.version.replace(/^v(\d+).*/, "$1"))')"
if [ "$NODE_MAJOR" -lt "$MIN_NODE_MAJOR" ]; then
    echo "ERROR: Node.js >= $MIN_NODE_MAJOR required. Found: $(node --version)"
    exit 1
fi
echo "==> Node.js $(node --version) — OK"

# ── Clone remotelab ───────────────────────────────────────────────────────────
if [ -d "$REMOTELAB_DIR/.git" ]; then
    echo "==> remotelab already cloned at $REMOTELAB_DIR — skipping clone"
else
    echo "==> Cloning $REMOTELAB_REPO to $REMOTELAB_DIR"
    git clone "$REMOTELAB_REPO" "$REMOTELAB_DIR"
fi

# ── npm install ───────────────────────────────────────────────────────────────
echo "==> Installing npm dependencies"
cd "$REMOTELAB_DIR"
npm install

# ── .env setup ───────────────────────────────────────────────────────────────
ENV_FILE="$REMOTELAB_DIR/.env"
ENV_EXAMPLE="$REMOTELAB_DIR/.env.example"

if [ -f "$ENV_FILE" ]; then
    echo "==> .env already exists at $ENV_FILE — skipping"
else
    if [ -f "$ENV_EXAMPLE" ]; then
        echo "==> Creating .env from .env.example"
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
        echo "==> Creating .env with placeholder"
        cat > "$ENV_FILE" <<'EOF'
# Anthropic API key — get yours at https://console.anthropic.com
ANTHROPIC_API_KEY=your_api_key_here

# Port for the remotelab chat server (default: 7690)
PORT=7690
EOF
    fi
    echo ""
    echo "ACTION REQUIRED: Edit $ENV_FILE and set your ANTHROPIC_API_KEY"
fi

# ── Process daemon (pm2) ─────────────────────────────────────────────────────
echo "==> Setting up pm2 process manager"

if ! command -v pm2 &>/dev/null; then
    echo "==> Installing pm2 globally"
    npm install -g pm2
fi

echo ""
echo "==> Setup complete."
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE and set ANTHROPIC_API_KEY"
echo "  2. cd $REMOTELAB_DIR"
echo "  3. npm run setup              (first-time configuration)"
echo ""
echo "  Then start and register the service:"
echo "  4. pm2 start npm --name remotelab -- run chat"
echo "  5. pm2 save                   (persist process list)"
echo "  6. pm2 startup                (print & run the shown command to enable auto-start on reboot)"
echo ""
echo "Useful pm2 commands:"
echo "  pm2 status                    — check service health"
echo "  pm2 logs remotelab            — tail live logs"
echo "  pm2 restart remotelab         — restart after config change"
echo "  pm2 stop remotelab            — stop the service"
echo ""
echo "Then open your browser (or phone via Tailscale) at:"
echo "  http://<macbook-tailscale-ip>:7690"
