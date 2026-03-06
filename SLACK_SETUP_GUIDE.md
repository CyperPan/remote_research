# Slack Integration Setup Guide

## 🔧 Problem: No Slack Response

**Issue**: After connecting to Slack, messages sent in Slack channels receive no response from the agents.

**Root Cause**: Missing Slack environment configuration and bot setup.

## ✅ Solution Overview

Complete the 5-step setup process to enable full Slack integration with agent responses.

## 📋 Step-by-Step Setup

### Step 1: Create Slack Bot and Get Credentials

1. **Go to Slack API**: https://api.slack.com/apps
2. **Create New App**: 
   - Click "Create New App"
   - Choose "From scratch"
   - Name it "ResearchLab Bot"
   - Select your workspace

3. **Get Bot Token**:
   - Go to "OAuth & Permissions"
   - Scroll to "Bot User OAuth Token"
   - Copy the token (starts with `xoxb-`)

4. **Get Your User ID**:
   - Go to your Slack profile
   - Click "More" → "Copy member ID"
   - Or use: https://api.slack.com/methods/auth.test/test

### Step 2: Set Environment Variables

```bash
# Add to your .env file
echo "SLACK_BOT_TOKEN=xoxb-your-bot-token-here" >> crewai-server/.env
echo "SLACK_OWNER_ID=U-your-user-id-here" >> crewai-server/.env

# Or set in your shell
export SLACK_BOT_TOKEN='xoxb-your-bot-token-here'
export SLACK_OWNER_ID='U-your-user-id-here'
```

### Step 3: Create/Verify Slack Channels

The system expects these specific channel IDs (update these to match your workspace):

```python
# Current channel mappings in api.py
SLACK_CHANNELS = {
    "planner":  "C0AJSUZ7MC5",    # #research-planner
    "reviewer": "C0AJQ0WC3KM",    # #research-reviewer  
    "coder":    "C0AK00JUFEG",    # #research-coder
    "executor": "C0AJWCSDQ10",    # #research-executor
}
SLACK_GENERAL_CHANNEL = "C0AJW7E2GBU"   # #all-researchlab
```

**To find your channel IDs**:
1. Open Slack in browser
2. Right-click on channel name
3. "Copy link" - the ID is in the URL
4. Or use: https://api.slack.com/methods/conversations.list/test

### Step 4: Configure Bot Permissions

In your Slack app settings:

1. **OAuth & Permissions** → **Scopes** → Add these **Bot Token Scopes**:
   - `chat:write` - Send messages
   - `chat:write.public` - Send to public channels
   - `conversations:read` - Read channel info
   - `users:read` - Read user info

2. **Install App to Workspace**:
   - Click "Install to Workspace"
   - Select the channels your bot should access
   - Copy the new bot token

3. **Add Bot to Channels**:
   - In each target channel, type: `/invite @ResearchLab Bot`
   - Or manually add the bot via channel settings

### Step 5: Test the Integration

```bash
# Run the diagnostic script
cd /Users/zhiyuanpan/remote_research
python3 diagnose_slack.py

# Expected output:
# ✅ API Connection: Successful
# ✅ Message Posted: Successfully to [channel]
# ✅ All agent channels verified
```

## 🧪 Testing Your Integration

### 1. Test via API
```bash
# Start the API server
cd crewai-server
python3 -m uvicorn api:app --reload --port 8000

# Test via curl
curl -X POST http://localhost:8000/agent/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "planner",
    "task": "Test Slack integration",
    "source_channel_id": "your-channel-id"
  }'
```

### 2. Test via Enhanced API
```bash
# Test with skill enhancement
curl -X POST http://localhost:8000/agent/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "executor",
    "task": "Check GPU availability on explorer",
    "source_channel_id": "your-channel-id"
  }'
```

## 🔍 Troubleshooting Common Issues

### Issue 1: "channel_not_found" Error
**Solution**: Channel ID is incorrect or bot not in channel
```bash
# Get correct channel ID
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.slack.com/api/conversations.list \
  | jq '.channels[] | {name, id}'
```

### Issue 2: "invalid_auth" Error  
**Solution**: Token is invalid or expired
- Regenerate token in Slack API dashboard
- Ensure you're using Bot Token, not User Token

### Issue 3: "not_in_channel" Error
**Solution**: Bot needs to be invited to channel
- Type: `/invite @ResearchLab Bot` in each channel
- Or add via channel settings → Members → Add

### Issue 4: No Response in Channel
**Solution**: Check these items:
1. ✅ Environment variables set
2. ✅ Bot has correct permissions  
3. ✅ Bot is in the channel
4. ✅ Channel IDs are correct
5. ✅ API server is running

## 📊 Integration Points

### Where Slack Messages Are Sent

1. **Agent Completion**: Individual agent channels
   - Planner → #research-planner
   - Reviewer → #research-reviewer
   - Coder → #research-coder  
   - Executor → #research-executor

2. **Flow Completion**: General research channel
   - #all-researchlab

3. **Human Intervention**: All agent channels + owner mention
   - When circuit breaker triggers
   - When human review needed

### Message Types

```python
# Success messages
"✅ *agent_name* done (job `job_id`):
{result_summary}"

# Failure messages  
"❌ *agent_name* failed (job `job_id`): {error}"

# Human intervention
"🚨 @owner Human intervention required (job `job_id`)
{detailed_context}"
```

## 🎯 Expected Behavior After Setup

1. **Agent Kickoff**: Message appears in agent-specific channel
2. **Agent Completion**: Success/failure message with results
3. **Flow Completion**: Summary in general channel
4. **Human Intervention**: Alert in all channels with owner mention
5. **Real-time Updates**: Progress messages during execution

## 🔧 Advanced Configuration

### Custom Channel Mapping
```python
# Modify in api.py
SLACK_CHANNELS = {
    "planner":  "YOUR_PLANNER_CHANNEL_ID",
    "reviewer": "YOUR_REVIEWER_CHANNEL_ID", 
    "coder":    "YOUR_CODER_CHANNEL_ID",
    "executor": "YOUR_EXECUTOR_CHANNEL_ID",
}
SLACK_GENERAL_CHANNEL = "YOUR_GENERAL_CHANNEL_ID"
```

### Message Formatting
```python
# Customize message format in _post_to_slack()
message = f"🎯 *{agent_name}* result:\n{custom_formatting}"
```

### Rate Limiting
```python
# Add delays if needed for high-volume usage
import time
time.sleep(1)  # 1 second between messages
```

## 📋 Verification Checklist

- [ ] SLACK_BOT_TOKEN set in environment
- [ ] SLACK_OWNER_ID set in environment  
- [ ] Bot has chat:write permission
- [ ] Bot is member of target channels
- [ ] Channel IDs are correct
- [ ] diagnostic script shows ✅ for all tests
- [ ] Test API call produces Slack message
- [ ] Agent workflow completes with notifications

## 🏆 Success Criteria

✅ **Basic**: Messages appear in Slack channels when agents complete work
✅ **Advanced**: Real-time progress updates and intelligent routing
✅ **Professional**: Clean formatting and appropriate channel usage
✅ **Reliable**: Error handling and fallback mechanisms

**Status**: 🟢 **READY FOR PRODUCTION** - Complete the 5-step setup above!