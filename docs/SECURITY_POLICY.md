# Security Policy

## Zero-Trust Network Access (ZTNA) Principles

All access to this lab stack is governed by zero-trust principles:

1. **No public ports** — Neither ttyd (port 7681) nor the remotelab chat server (port 7690) is exposed to the public internet. All access routes through the Tailscale VPN.
2. **Identity before connectivity** — Devices must be authenticated with Tailscale before they can reach any service. Tailscale uses WireGuard with per-device keys managed via the Tailscale control plane.
3. **Least privilege** — Each component is granted only the access it needs:
   - The Jetson bastion has SSH keys for specific target machines only.
   - The MacBook runs the AI chat server; it does not expose SSH to the Jetson.
4. **Ephemeral sessions** — ttyd sessions end when the browser tab closes. There is no persistent session state stored outside the process.

---

## Network Topology

```
📱 Mobile Browser
    │
    ▼  (Tailscale WireGuard — device auth required)
🛡️ Jetson Orin Nano :7681   (ttyd — emergency raw terminal)
    │
    └──SSH (key-only)──▶ 🧠 MacBook :7690  (Ninglo remotelab — Claude Code chat UI)
                              │
                              └──SSH/paramiko──▶ 💪 GPU Cluster
```

No port is reachable without a valid Tailscale identity. Port 7681 and 7690 bind to `0.0.0.0` inside Docker/process but are only reachable via the Tailscale overlay network.

---

## SSH Key Lifecycle

### Generation
Keys are generated on the Jetson by `scripts/setup_ssh_trust.sh`:

```bash
ssh-keygen -t ed25519 -C "jetson@remotelab" -f ~/.ssh/id_ed25519 -N ""
```

- Algorithm: **ed25519** (modern, small, fast)
- No passphrase (required for unattended SSH from ttyd sessions)
- Private key stays on the Jetson; never leaves the bastion host

### Distribution
The public key is installed on target machines via `ssh-copy-id`:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@<target>
```

Target `~/.ssh` permissions must be:
- `~/.ssh/` → mode `700`
- `~/.ssh/authorized_keys` → mode `600`

### Rotation
Rotate SSH keys at least annually or immediately if the Jetson is compromised:

1. Generate a new key pair on the Jetson:
   ```bash
   ssh-keygen -t ed25519 -C "jetson@remotelab-$(date +%Y%m)" -f ~/.ssh/id_ed25519_new -N ""
   ```
2. Copy the new public key to all target machines.
3. Remove the old public key from all `authorized_keys` files.
4. Replace `~/.ssh/id_ed25519` with the new key.

### Revocation
If a key is compromised:
1. Remove the corresponding line from `~/.ssh/authorized_keys` on every target machine.
2. Delete `~/.ssh/id_ed25519` and `~/.ssh/id_ed25519.pub` from the Jetson.
3. Run `scripts/setup_ssh_trust.sh` to generate and distribute a fresh key.

---

## Tailscale ACL Recommendations

Use Tailscale ACL policies to restrict which devices can reach which ports. Example policy (edit in Tailscale admin console):

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:mobile"],
      "dst": ["tag:bastion:7681", "tag:macbook:7690"]
    },
    {
      "action": "accept",
      "src": ["tag:bastion"],
      "dst": ["tag:macbook:22", "tag:gpu:22"]
    }
  ],
  "tagOwners": {
    "tag:mobile":  ["autogroup:member"],
    "tag:bastion": ["autogroup:owner"],
    "tag:macbook": ["autogroup:owner"],
    "tag:gpu":     ["autogroup:owner"]
  }
}
```

This ensures:
- Mobile devices can only reach the ttyd terminal and the chat UI.
- The Jetson bastion can SSH to the MacBook and GPU cluster.
- No other cross-device access is permitted.

---

## Secrets Management

| Secret | Location | Access |
|--------|----------|--------|
| `ANTHROPIC_API_KEY` | `~/remotelab-server/.env` on MacBook | MacBook local only; never committed to git |
| Jetson SSH private key | `~/.ssh/id_ed25519` on Jetson | Jetson local only |
| Tailscale auth keys | Tailscale admin console | Rotate via admin console if leaked |

**Never commit `.env` files or private keys to this repository.**
The `.gitignore` should exclude `*.env`, `.env`, and `**/.env`.

---

## Incident Response

| Event | Action |
|-------|--------|
| Jetson stolen/compromised | Revoke SSH keys; disable Jetson in Tailscale admin; rotate `ANTHROPIC_API_KEY` |
| Tailscale key leaked | Rotate in Tailscale admin; re-authenticate all devices |
| API key leaked | Immediately revoke at https://console.anthropic.com and generate a new key |
| Unexpected ttyd access | Check Tailscale logs; confirm ACLs; rotate SSH keys |
