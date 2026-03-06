#!/usr/bin/env python3
"""Simple Slack integration test - basic functionality check."""

import os
import sys
from pathlib import Path

# Add the crewai-server source to path
sys.path.insert(0, str(Path(__file__).parent / "crewai-server" / "src"))

def test_basic_slack():
    """Test basic Slack functionality."""
    print("🚀 Basic Slack Integration Test\n")
    
    # Check if we have the token
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token or "your-bot-token" in token:
        print("❌ No valid Slack token found")
        print("   Please set SLACK_BOT_TOKEN in your .env file")
        print("   Example: SLACK_BOT_TOKEN=xoxb-your-actual-token")
        return False
    
    print(f"✅ Slack token found: {token[:15]}...")
    
    # Test the notification module
    try:
        from research_crew.slack_notify import post, FLOW_CHANNEL, AGENT_CHANNELS
        print(f"✅ Slack notification module imported")
        print(f"   Flow channel: {FLOW_CHANNEL}")
        print(f"   Agent channels: {len(AGENT_CHANNELS)} channels")
        
        # Test channel mapping
        for agent, channel in AGENT_CHANNELS.items():
            print(f"   {agent} → {channel}")
        
        print("\n✅ Basic Slack integration is configured")
        print("   Next steps:")
        print("   1. Get real Slack bot token from https://api.slack.com/apps")
        print("   2. Update .env file with real token")
        print("   3. Test with actual API calls")
        
        return True
        
    except ImportError as e:
        print(f"❌ Cannot import Slack module: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_basic_slack()
    print(f"\n📊 Result: {'✅ Ready for Slack setup' if success else '❌ Needs configuration'}")