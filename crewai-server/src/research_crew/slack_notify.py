"""Lightweight Slack notification helper — used by flow.py and api.py."""
import os
import requests

# Default channel for flow pipeline progress updates
FLOW_CHANNEL = "C0AJW7E2GBU"   # #all-researchlab

# Per-agent channels
AGENT_CHANNELS = {
    "planner":  "C0AJSUZ7MC5",
    "reviewer": "C0AJQ0WC3KM",
    "coder":    "C0AK00JUFEG",
    "executor": "C0AJWCSDQ10",
}

OWNER_ID = os.getenv("SLACK_OWNER_ID", "")


def post(text: str, channel_id: str = "") -> None:
    """Post a message to Slack. Best-effort — never raises."""
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        return
    target = channel_id or FLOW_CHANNEL
    try:
        requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"channel": target, "text": text, "unfurl_links": False},
            timeout=8,
        )
    except Exception:
        pass


def mention_owner() -> str:
    return f"<@{OWNER_ID}>" if OWNER_ID else "@owner"
