#!/usr/bin/env bash
# setup_ssh_trust.sh — Run on the Jetson Orin Nano (bastion host)
# Generates an ed25519 SSH key (if absent) and copies it to the target MacBook.

set -euo pipefail

KEY_FILE="$HOME/.ssh/id_ed25519"
KEY_COMMENT="jetson@remotelab"

# ── Generate key ─────────────────────────────────────────────────────────────
if [ -f "$KEY_FILE" ]; then
    echo "==> SSH key already exists at $KEY_FILE — skipping generation"
else
    echo "==> Generating ed25519 SSH key"
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    ssh-keygen -t ed25519 -C "$KEY_COMMENT" -f "$KEY_FILE" -N ""
    echo "==> Key generated: $KEY_FILE"
fi

echo ""
echo "Public key fingerprint:"
ssh-keygen -lf "${KEY_FILE}.pub"
echo ""

# ── Copy to target machine ────────────────────────────────────────────────────
if [ $# -lt 1 ]; then
    echo "Usage: $0 <user@macbook-ip-or-tailscale-hostname>"
    echo ""
    echo "Example:"
    echo "  $0 alice@100.x.x.x"
    echo "  $0 alice@macbook"
    echo ""
    echo "You can find the MacBook Tailscale IP with: tailscale status"
    exit 1
fi

TARGET="$1"

echo "==> Copying public key to $TARGET"
echo "    You will be prompted for the remote password once."
ssh-copy-id -i "${KEY_FILE}.pub" "$TARGET"

echo ""
echo "==> Verifying passwordless login to $TARGET"
if ssh -o BatchMode=yes -o ConnectTimeout=5 "$TARGET" exit 2>/dev/null; then
    echo "==> SUCCESS — passwordless SSH to $TARGET is working."
else
    echo "==> WARNING — Could not verify passwordless login. Check sshd config on the target."
    echo "    Ensure ~/.ssh has mode 700 and ~/.ssh/authorized_keys has mode 600."
fi

echo ""
echo "==> Optionally add a Host alias to $HOME/.ssh/config:"
echo "    Host macbook"
echo "        HostName <tailscale-ip>"
echo "        User <your-username>"
