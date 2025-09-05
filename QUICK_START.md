# 🚀 Voice Agent System - Quick Start Guide

Get the voice agent system running in under 30 minutes with this step-by-step guide.

## 📋 Prerequisites Checklist

Before starting, ensure you have:
- [ ] **Docker & Docker Compose** installed ([Get Docker](https://docs.docker.com/get-docker/))
- [ ] **Python 3.8+** installed (`python3 --version`)
- [ ] **Git** for cloning (if needed)
- [ ] **Stable internet connection** for API services

## 🔑 Step 1: Get API Keys (15 minutes)

You'll need accounts and API keys from these services:

### 1. LiveKit (Free tier available)
1. Go to https://livekit.io/ → Sign up
2. Create new project → Copy **API Key** and **API Secret**
3. Go to SIP section → Enable SIP → Copy **SIP URI**

### 2. Twilio (Free $15 credit)
1. Go to https://twilio.com/ → Sign up  
2. Copy **Account SID** and **Auth Token** from dashboard
3. Buy a phone number with Voice capability
4. Create SIP Trunk → Set Origination URI to your LiveKit SIP URI

### 3. Deepgram (STT - Speech-to-Text) (Free $200 credit)
1. Go to https://deepgram.com/ → Sign up
2. Go to API Keys → Create new key → Copy **API Key**
3. **Purpose**: Converts user speech to text (~$0.0043/minute)

### 4. ElevenLabs (TTS - Text-to-Speech) (Free 10k characters/month)
1. Go to https://elevenlabs.io/ → Sign up
2. Go to Profile → Copy **API Key**
3. Go to Voices → Pick a voice → Note **Voice ID** (e.g., "Rachel")
4. **Purpose**: Converts agent responses to speech (~$0.30 per 1,000 characters)

**Note**: Both services are required for optimal performance. They serve different purposes in the conversation flow.

### Alternative: Using One Service

If you want to minimize API dependencies, consider:

#### Option A: OpenAI (Single Provider)
- **Cost**: ~$0.015/minute (higher than separate services)
- **Setup**: Just one API key needed
- **Trade-off**: Less telephony-optimized than Deepgram + ElevenLabs

#### Option B: Skip STT (Limited Functionality)
- Remove Deepgram and use simple keyword detection
- **Result**: Much less responsive, can't handle complex conversations
- **Not recommended** for production use

## ⚙️ Step 2: Configure Environment (5 minutes)

```bash
# Navigate to project directory
cd voice-agent-100calls

# Copy environment template
cp env.template .env

# Edit .env file with your API keys
nano .env  # or use your preferred editor
```

Fill in your `.env` file:
```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Deepgram Configuration
DEEPGRAM_API_KEY=your-deepgram-api-key

# ElevenLabs Configuration
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=Rachel

# Keep other settings as default
```

## 🐍 Step 3: Install Dependencies (3 minutes)

```bash
# Install Python dependencies for testing
cd tools/loadtest
pip3 install -r requirements.txt
cd ../..

# Install latency analysis tools
cd tools/latency  
pip3 install -r requirements.txt
cd ../..

# Verify installations
python3 -c "import aiohttp, asyncio, twilio; print('✅ Dependencies installed!')"

# Make scripts executable
chmod +x scripts/scale.sh
```

## 🚀 Step 4: Start the System (2 minutes)

```bash
# Start with 10 agent workers (recommended for 100 concurrent calls)
./scripts/scale.sh up 10

# Wait for system to start (about 30-60 seconds)
# Check system status
./scripts/scale.sh status

# Should show all green checkmarks:
# ✓ Orchestrator: Healthy
# ✓ Redis: Healthy
# ✓ Prometheus: Healthy
# ✓ Grafana: Healthy
```

## ✅ Step 5: Verify Everything Works (5 minutes)

### Test System Health
```bash
# Run comprehensive health tests
./scripts/scale.sh test

# Manual verification
curl http://localhost:8080/health
curl http://localhost:8080/stats
```

### Test Load Handling
```bash
cd tools/loadtest

# Quick 10-call test
python3 load_test.py --calls 10 --duration 2

# Should show:
# - Success rate: 100%
# - Latency: <600ms
# - No errors
```

### Test Phone Integration (Optional)
```bash
# Call your Twilio phone number
# Should connect to AI agent within 2-3 seconds
# Try having a conversation and interrupting
```

## 🎯 Success Criteria

Your system is ready when:
- ✅ All health checks pass
- ✅ Load test achieves >95% success rate  
- ✅ Latency is <600ms (95th percentile)
- ✅ Phone calls connect to AI agent
- ✅ No critical errors in logs

## 📊 Access Monitoring Dashboards

- **System Stats**: http://localhost:8080/stats
- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **Prometheus Metrics**: http://localhost:9090

## 🧪 Run Production Load Test

```bash
cd tools/loadtest

# Full 100 concurrent call test
python3 load_test.py --calls 100 --duration 5 --ramp-up 30 --output results.json

# Check results
python3 -c "
import json
with open('results.json') as f:
    data = json.load(f)
    success_rate = data.get('test_summary', {}).get('success_rate_percent', 0)
    latency_ok = data.get('test_summary', {}).get('latency_target_met', False)
    print(f'Success Rate: {success_rate}% (Target: ≥95%)')
    print(f'Latency Target: {\"✅ Met\" if latency_ok else \"❌ Failed\"} (<600ms)')
    if success_rate >= 95 and latency_ok:
        print('🎉 PRODUCTION READY!')
    else:
        print('❌ Needs optimization - check scaling and configuration')
"
```

## 🆘 Quick Troubleshooting

### System Won't Start
```bash
# Check Docker is running
docker --version
docker-compose --version

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Load Tests Fail
```bash
# Scale up workers
./scripts/scale.sh up 15

# Check API connectivity
curl -H "Authorization: Token $DEEPGRAM_API_KEY" https://api.deepgram.com/v1/projects
curl -H "Authorization: Bearer $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/voices
```

### High Latency
```bash
# Check external service latency
ping api.deepgram.com
ping api.elevenlabs.io

# Monitor system resources
docker stats
```

## 📚 Complete Documentation

For detailed information, see:
- **[SETUP.md](SETUP.md)** - Complete setup guide with detailed API account instructions
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Comprehensive testing and validation procedures
- **[INSTALL_DEPENDENCIES.md](INSTALL_DEPENDENCIES.md)** - Detailed Python dependency installation
- **[tools/loadtest/README.md](tools/loadtest/README.md)** - Load testing documentation

## 🎉 You're Done!

Your voice agent system is now running and ready to handle 100 concurrent calls with <600ms latency!

**Next Steps:**
- Customize agent behavior in `services/agent/app.py`
- Set up production deployment with `docker-compose.prod.yml`
- Configure monitoring alerts for production use
- Scale workers based on your actual load requirements

**Need Help?** Check the troubleshooting sections in the complete documentation files above.
