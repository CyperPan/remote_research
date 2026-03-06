#!/usr/bin/env python3
"""Diagnose Slack integration issues for remote_research project."""

import os
import sys
import requests
from pathlib import Path

# Add the crewai-server source to path
sys.path.insert(0, str(Path(__file__).parent / "crewai-server" / "src"))

def test_slack_connection():
    """Test basic Slack API connectivity."""
    print("=== Slack Integration Diagnosis ===\n")
    
    # Check environment variables
    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    slack_owner = os.getenv("SLACK_OWNER_ID", "")
    
    print(f"🔍 Environment Check:")
    print(f"  SLACK_BOT_TOKEN: {'✅ Set' if slack_token else '❌ Missing'}")
    print(f"  SLACK_OWNER_ID: {'✅ Set' if slack_owner else '❌ Missing'}")
    
    if not slack_token:
        print("\n❌ CRITICAL: SLACK_BOT_TOKEN is not set!")
        print("   Please set it: export SLACK_BOT_TOKEN='your-bot-token'")
        return False
    
    # Test basic API connection
    print(f"\n🔗 Testing Slack API connection...")
    try:
        response = requests.get(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {slack_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"✅ API Connection: Successful")
                print(f"  Bot User: {data.get('user', 'Unknown')}")
                print(f"  Team: {data.get('team', 'Unknown')}")
            else:
                print(f"❌ API Error: {data.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection Error: {e}")
        return False
    
    # Test channel access
    print(f"\n📡 Testing channel access...")
    try:
        # Test general channel
        from research_crew.slack_notify import FLOW_CHANNEL, AGENT_CHANNELS
        
        print(f"  Flow Channel: {FLOW_CHANNEL}")
        print(f"  Agent Channels: {AGENT_CHANNELS}")
        
        # Test posting to general channel
        test_response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"},
            json={"channel": FLOW_CHANNEL, "text": "🔧 System diagnostic test", "unfurl_links": False},
            timeout=10
        )
        
        if test_response.status_code == 200:
            result = test_response.json()
            if result.get("ok"):
                print(f"✅ Message Posted: Successfully to {FLOW_CHANNEL}")
                print(f"  Message TS: {result.get('ts', 'Unknown')}")
            else:
                print(f"❌ Post Error: {result.get('error', 'Unknown error')}")
                if result.get('error') == 'channel_not_found':
                    print("   💡 Channel ID may be incorrect or bot not in channel")
                elif result.get('error') == 'not_in_channel':
                    print("   💡 Bot needs to be invited to the channel")
                elif result.get('error') == 'invalid_auth':
                    print("   💡 Token may be invalid or expired")
        else:
            print(f"❌ Post HTTP Error: {test_response.status_code}")
            
    except Exception as e:
        print(f"❌ Channel Test Error: {e}")
        return False
    
    return True

def test_agent_channels():
    """Test individual agent channels."""
    print(f"\n🔍 Testing Agent Channels...")
    
    from research_crew.slack_notify import AGENT_CHANNELS
    
    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    if not slack_token:
        print("  ❌ Skipping: No token available")
        return
    
    for agent, channel_id in AGENT_CHANNELS.items():
        print(f"  Testing {agent} → {channel_id}")
        try:
            response = requests.post(
                "https://slack.com/api/conversations.info",
                headers={"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"},
                json={"channel": channel_id},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    channel_info = data.get("channel", {})
                    print(f"    ✅ {agent}: {channel_info.get('name', 'Unknown')} (ID: {channel_id})")
                else:
                    print(f"    ❌ {agent}: {data.get('error', 'Unknown error')}")
            else:
                print(f"    ❌ {agent}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ {agent}: {e}")

def check_integration_points():
    """Check where Slack is integrated in the codebase."""
    print(f"\n🔍 Checking Integration Points...")
    
    # Check API integration
    api_file = Path("src/research_crew/api.py")
    if api_file.exists():
        with open(api_file) as f:
            content = f.read()
            slack_calls = content.count("_post_to_slack")
            print(f"  API Integration: {slack_calls} Slack call(s) found")
    
    # Check flow integration  
    flow_file = Path("src/research_crew/flow.py")
    if flow_file.exists():
        with open(flow_file) as f:
            content = f.read()
            slack_calls = content.count("post(")
            print(f"  Flow Integration: {slack_calls} Slack call(s) found")
    
    # Check notification module
    notify_file = Path("src/research_crew/slack_notify.py")
    if notify_file.exists():
        with open(notify_file) as f:
            content = f.read()
            channels = content.count("AGENT_CHANNELS")
            print(f"  Notification Module: {channels} agent channel mappings")

def provide_solution_steps():
    """Provide step-by-step solution for Slack integration."""
    print(f"\n🔧 SOLUTION STEPS ===")
    print("""
1. **Set Environment Variables**
   export SLACK_BOT_TOKEN='xoxb-your-bot-token'
   export SLACK_OWNER_ID='U-your-user-id'

2. **Create .env File**
   cp crewai-server/.env.template crewai-server/.env
   # Add the Slack variables to .env

3. **Verify Bot Permissions**
   - Ensure bot has chat:write permission
   - Add bot to target channels
   - Verify channel IDs are correct

4. **Test Integration**
   python3 diagnose_slack.py

5. **Monitor Logs**
   Check API responses for specific error messages
""")

if __name__ == "__main__":
    print("🚀 Starting Slack integration diagnosis...\n")
    
    # Run all diagnostic tests
    api_ok = test_slack_connection()
    test_agent_channels()
    check_integration_points()
    provide_solution_steps()
    
    print(f"\n📊 DIAGNOSIS COMPLETE ===")
    if api_ok:
        print("✅ Slack API is functional - check channel membership and permissions")
    else:
        print("❌ Slack integration has issues - follow solution steps above")