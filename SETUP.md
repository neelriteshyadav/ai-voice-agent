# Complete Setup Guide - Voice Agent System

This guide will walk you through setting up the entire voice agent system from scratch, including all dependencies, API accounts, and testing.

## 🚀 Prerequisites

### System Requirements
- **Operating System**: macOS, Linux, or Windows with WSL2
- **Docker**: Version 20.0+ with Docker Compose
- **Python**: Version 3.8+ (we'll install pip if needed)
- **Git**: For cloning the repository
- **curl**: For API testing (usually pre-installed)

### Hardware Requirements (for 100 concurrent calls)
- **CPU**: 8+ cores recommended
- **RAM**: 16GB+ recommended
- **Network**: Stable internet connection with low latency

## 📋 Step 1: System Setup

### Install Docker and Docker Compose

**macOS:**
```bash
# Install Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop
# Or using Homebrew:
brew install --cask docker
```

**Linux (Ubuntu/Debian):**
```bash
# Update package index
sudo apt-get update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

**Windows (WSL2):**
```bash
# Install Docker Desktop for Windows
# Download from: https://www.docker.com/products/docker-desktop
# Ensure WSL2 backend is enabled
```

### Verify Docker Installation
```bash
docker --version
docker-compose --version
```

## 📥 Step 2: Project Setup

### Clone the Repository
```bash
# Navigate to your desired directory
cd ~/Downloads  # or wherever you prefer

# If you have the project already:
cd voice-agent-100calls

# Or if cloning from a repository:
# git clone <repository-url>
# cd voice-agent-100calls
```

### Install Python and pip
```bash
# Check if Python 3.8+ is installed
python3 --version

# If not installed on macOS:
brew install python3

# If not installed on Linux:
sudo apt-get install python3 python3-pip

# Install pip if needed (using the get-pip.py file in the project)
python3 get-pip.py --user
```

### Install Project Dependencies

**📖 Complete Installation Guide Available:**
For detailed dependency installation instructions, see [INSTALL_DEPENDENCIES.md](INSTALL_DEPENDENCIES.md)

**Quick Installation:**
```bash
# Install load testing dependencies (required)
cd tools/loadtest
pip3 install -r requirements.txt
cd ../..

# Install latency analysis dependencies (required for call analysis)
cd tools/latency
pip3 install -r requirements.txt
cd ../..

# Note: Agent and orchestrator dependencies are handled by Docker
# Only install testing/analysis tools locally
```

**Verify Python installations:**
```bash
# Test that key packages are installed
python3 -c "import aiohttp, asyncio; print('✅ Load test dependencies: OK')"
python3 -c "import twilio, pydub, numpy; print('✅ Latency analysis dependencies: OK')"

# If any imports fail, see INSTALL_DEPENDENCIES.md for troubleshooting
```

**Alternative: Install All Dependencies at Once:**
```bash
# Install everything needed for testing and analysis
pip3 install aiohttp asyncio twilio pydub numpy scipy matplotlib pandas prometheus-client

# Verify all installations
python3 -c "
import aiohttp, asyncio, twilio, pydub, numpy, pandas
print('✅ All dependencies installed successfully!')
"
```

## 🔑 Step 3: API Account Setup

### 3.1 LiveKit Account Setup

1. **Create LiveKit Account**:
   - Go to https://livekit.io/
   - Click "Sign Up" and create a free account
   - Verify your email address
   - Create a new project (give it a memorable name like "voice-agent-system")

2. **Get API Credentials**:
   - In your LiveKit dashboard, click on your project
   - Go to "Settings" → "Keys" in the left sidebar
   - Click "Create API Key"
   - Copy your `API Key` (starts with "API...")
   - Copy your `API Secret` (long string, keep this secure!)
   - Note your LiveKit URL format: `wss://[project-name].livekit.cloud`

3. **Configure SIP Integration**:
   - In LiveKit dashboard, go to "SIP" in the left sidebar
   - Click "Enable SIP" if not already enabled
   - Create a new SIP trunk:
     - Name: "Voice Agent Trunk"
     - Leave other settings as default
   - Note your SIP URI (format: `sip:[random-id].sip.livekit.cloud`)
   - **Important**: Copy this SIP URI - you'll need it for Twilio configuration

4. **Configure Dispatch Rules** (Important for routing):
   - Still in the SIP section, go to "Dispatch Rules"
   - Create a new rule with these settings:
     - Rule Type: "c"
     - Room Prefix: "call-"
     - Max Participants: 2
   - This ensures each call gets its own room

### 3.2 Twilio Account Setup

1. **Create Twilio Account**:
   - Go to https://www.twilio.com/
   - Click "Sign up for free" (includes $15 credit)
   - Complete account verification with your phone number
   - Choose "Programmable Voice" as your primary use case

2. **Get API Credentials**:
   - In Twilio Console dashboard, look for the "Account Info" section
   - Copy your `Account SID` (starts with "AC...")
   - Copy your `Auth Token` (click the eye icon to reveal it)
   - **Keep these secure** - they're like your username/password

3. **Purchase a Phone Number**:
   - Go to "Phone Numbers" → "Manage" → "Buy a number"
   - Choose your country (e.g., United States)
   - Filter by "Voice" capability
   - Select a number you like and click "Buy"
   - Note the full phone number (e.g., `+18883522916`)

4. **Create SIP Trunk** (This connects Twilio to LiveKit):
   - Go to "Elastic SIP Trunking" → "Trunks"
   - Click "Create new SIP Trunk"
   - Settings:
     - Friendly Name: "LiveKit Voice Agent Trunk"
     - Request URL: Leave empty for now
   - Click "Create"
   - In the trunk settings, go to "Origination"
   - Add Origination URI: `sip:[your-livekit-sip-uri]` (from LiveKit step 3)
   - Set Priority: 10, Weight: 10

5. **Configure Phone Number to Use SIP Trunk**:
   - Go back to "Phone Numbers" → "Manage" → "Active numbers"
   - Click on your purchased number
   - In "Voice Configuration":
     - Configure with: "SIP Trunk"
     - SIP Trunk: Select your "LiveKit Voice Agent Trunk"
     - Click "Save"

### 3.3 Deepgram Account Setup (STT Service)

1. **Create Deepgram Account**:
   - Go to https://deepgram.com/
   - Click "Get Started Free" (includes $200 credit)
   - Sign up with email or GitHub
   - Complete email verification

2. **Get API Key**:
   - In Deepgram Console, go to "API Keys" in the left sidebar
   - Click "Create a New API Key"
   - Give it a name like "Voice Agent System"
   - Select permissions: "Member" (default is fine)
   - Click "Create Key"
   - **Important**: Copy the API key immediately - you can't see it again!
   - The key starts with a long string of characters

3. **Verify API Key Works**:
   ```bash
   # Test the API key (replace YOUR_API_KEY with actual key)
   curl -H "Authorization: Token YOUR_API_KEY" \
        "https://api.deepgram.com/v1/projects"
   ```

**Note**: Deepgram handles Speech-to-Text (STT) - converting user speech to text

### 3.4 ElevenLabs Account Setup (TTS Service)

1. **Create ElevenLabs Account**:
   - Go to https://elevenlabs.io/
   - Click "Get Started Free" (includes 10,000 characters/month)
   - Sign up with email or Google
   - Complete email verification

2. **Get API Key**:
   - In ElevenLabs dashboard, click your profile picture (top right)
   - Click "Profile + API Key"
   - Copy the API key (long string starting with letters/numbers)
   - **Keep this secure** - it's linked to your usage credits

3. **Choose a Voice**:
   - Go to "Voices" in the left sidebar
   - Browse the available voices
   - Click on a voice to hear a sample (e.g., "Rachel", "Adam", "Sarah")
   - Note the Voice ID (shown when you click on a voice)
   - Popular choices for phone calls: "Rachel" (clear female), "Adam" (clear male)

4. **Test Your API Key**:
   ```bash
   # Test the API key (replace YOUR_API_KEY with actual key)
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        "https://api.elevenlabs.io/v1/voices"
   ```

**Note**: ElevenLabs handles Text-to-Speech (TTS) - converting agent responses to speech

### Alternative: Using a Single Provider

If you prefer to use just one service, here are your options:

#### Option 1: Use OpenAI (Unified STT + TTS)
```bash
# OpenAI provides both STT and TTS
pip install openai

# Environment variables (replace Deepgram/ElevenLabs with OpenAI)
OPENAI_API_KEY=your-openai-key
OPENAI_STT_MODEL=whisper-1
OPENAI_TTS_MODEL=tts-1
OPENAI_VOICE=alloy
```

**Pros**: Single API key, consistent quality
**Cons**: Higher cost (~$0.015/minute), less optimized for telephony

#### Option 2: Use Azure Cognitive Services (Unified)
```bash
# Microsoft Azure provides both STT and TTS
AZURE_SPEECH_KEY=your-azure-key
AZURE_SPEECH_REGION=eastus
AZURE_VOICE=en-US-AriaRUS
```

**Pros**: Enterprise-grade, good telephony optimization
**Cons**: More complex setup, higher minimum usage

#### Option 3: Use Just ElevenLabs (TTS Only)
You could remove STT and use simple keyword detection, but this significantly reduces functionality.

**Recommendation**: Keep both services for optimal performance and user experience.

## ⚙️ Step 4: Environment Configuration

### Create .env File
```bash
# Copy the template
cp env.template .env

# Edit the .env file with your credentials
nano .env  # or use your preferred editor
```

### Fill in Your .env File
```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret

# Twilio Configuration (for PSTN)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+18883522916

# STT/TTS Service Configuration
DEEPGRAM_API_KEY=your-deepgram-api-key
DEEPGRAM_MODEL=nova-2-general-telephone
DEEPGRAM_LANGUAGE=en-US
DEEPGRAM_INTERIM_RESULTS=true

ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=Rachel
ELEVENLABS_SPEED=1.05
ELEVENLABS_STABILITY=0.5
ELEVENLABS_SIMILARITY_BOOST=0.75

# Redis Configuration
REDIS_URL=redis://redis:6379

# Orchestrator Configuration
ORCH_HTTP_PORT=8080
METRICS_PORT=9300

# Performance Tuning
MAX_CONCURRENT_AGENTS=100
AGENT_TIMEOUT_SECONDS=300
CONNECTION_POOL_SIZE=20
WORKER_SCALE_FACTOR=10

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
LOG_LEVEL=INFO

# Regional Configuration (for latency optimization)
LIVEKIT_REGION=us-central
DEEPGRAM_REGION=us-central

# Advanced Performance Settings
AUDIO_BUFFER_SIZE=160  # 10ms at 16kHz
AUDIO_SAMPLE_RATE=16000
ENABLE_ECHO_CANCELLATION=true
ENABLE_NOISE_SUPPRESSION=true
VAD_THRESHOLD=0.5

# Load Testing
LOAD_TEST_DURATION_MINUTES=10
LOAD_TEST_RAMP_UP_SECONDS=30
LOAD_TEST_TARGET_CALLS=100
```

## 🚀 Step 5: Start the System

### Method 1: Using the Scale Script (Recommended)
```bash
# Make the script executable
chmod +x scripts/scale.sh

# Start with 10 agent workers
./scripts/scale.sh up 10

# Check system status
./scripts/scale.sh status
```

### Method 2: Using Docker Compose Directly
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check running containers
docker-compose ps
```

### Verify System is Running
```bash
# Check orchestrator health
curl http://localhost:8080/health

# Check system stats
curl http://localhost:8080/stats

# Check Prometheus metrics
curl http://localhost:9090/metrics

# Access Grafana dashboard
# Open http://localhost:3000 in browser (admin/admin)
```

## 🧪 Step 6: Test the System

### 6.1 Basic Health Tests

**Run System Health Checks:**
```bash
# Run built-in health tests
./scripts/scale.sh test

# Check individual service health
curl http://localhost:8080/health
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3000/api/health  # Grafana

# Check system statistics
curl http://localhost:8080/stats | python3 -m json.tool
```

**Manual Agent Dispatch Test:**
```bash
# Test agent dispatch manually
curl -X POST "http://localhost:8080/manual/dispatch?room=test-room&participant_identity=test-user"

# Check if agent was dispatched
curl http://localhost:8080/stats | grep -i active
```

### 6.2 Load Testing

**Prerequisites for Load Testing:**
```bash
# Ensure system is running with adequate workers
./scripts/scale.sh status

# Should show at least 10 agent workers running
# If not, scale up:
./scripts/scale.sh up 10
```

#### Small Scale Test (Development)
```bash
cd tools/loadtest

# Verify load test dependencies
python3 -c "import aiohttp, asyncio; print('Dependencies OK')"

# Quick 10-call test (good for development)
python3 load_test.py --calls 10 --duration 2 --ramp-up 5

# Medium test with more detailed output
python3 load_test.py --calls 25 --duration 3 --ramp-up 10 --output medium_test.json

# View results
cat medium_test.json | python3 -m json.tool
```

#### Full Scale Test (100 Concurrent Calls)
```bash
# Ensure system is scaled appropriately first
cd ../..
./scripts/scale.sh up 10
cd tools/loadtest

# Full production load test
python3 load_test.py --calls 100 --duration 5 --ramp-up 30 --output full_test.json

# Monitor system during test (in another terminal)
watch -n 2 'curl -s http://localhost:8080/stats | python3 -m json.tool'

# View detailed results
cat full_test.json | python3 -m json.tool

# Check if test passed
python3 -c "
import json
with open('full_test.json') as f:
    data = json.load(f)
    success_rate = data.get('test_summary', {}).get('success_rate_percent', 0)
    latency_ok = data.get('test_summary', {}).get('latency_target_met', False)
    print(f'Success Rate: {success_rate}% (Target: >95%)')
    print(f'Latency Target Met: {latency_ok}')
    if success_rate >= 95 and latency_ok:
        print('✅ LOAD TEST PASSED!')
    else:
        print('❌ Load test failed - check system scaling and configuration')
"
```

### 6.3 Real Phone Call Testing

1. **Configure Twilio Webhook**:
   ```bash
   # Set your webhook URL in Twilio Console
   # Webhook URL: https://your-domain.com/webhooks/livekit
   # Or use ngrok for local testing:
   
   # Install ngrok
   npm install -g ngrok
   # or download from https://ngrok.com/
   
   # Expose local orchestrator
   ngrok http 8080
   
   # Use the ngrok URL in Twilio webhook configuration
   ```

2. **Make a Test Call**:
   - Call your Twilio phone number
   - You should be connected to an AI agent
   - Test conversation and barge-in functionality

### 6.4 Latency Analysis (After Phone Calls)
```bash
cd tools/latency

# Set Twilio credentials for recording analysis
export TWILIO_ACCOUNT_SID=your-account-sid
export TWILIO_AUTH_TOKEN=your-auth-token

# Analyze call recordings
python3 analyze_recordings.py

# View latency analysis
cat latency.csv
```

## 📊 Step 7: Monitoring and Debugging

### Access Monitoring Dashboards

1. **Grafana Dashboard**:
   - URL: http://localhost:3000
   - Login: admin/admin
   - View the "Voice Agent System" dashboard

2. **Prometheus Metrics**:
   - URL: http://localhost:9090
   - Explore metrics like `turn_rtt_ms`, `active_calls`, etc.

3. **System Statistics**:
   - URL: http://localhost:8080/stats
   - Real-time system status

### Debug Common Issues

#### High Latency
```bash
# Check external service response times
curl -w "@curl-format.txt" -s -o /dev/null https://api.deepgram.com/v1/listen

# Monitor resource usage
docker stats

# Check agent logs
docker-compose logs agent-worker-1
```

#### Low Success Rate
```bash
# Check orchestrator logs
docker-compose logs orchestrator

# Check Redis queue
docker-compose exec redis redis-cli llen rooms

# Verify API credentials
curl -H "Authorization: Token YOUR_DEEPGRAM_KEY" https://api.deepgram.com/v1/projects
```

#### System Not Starting
```bash
# Check Docker status
docker system info

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check for port conflicts
netstat -tulpn | grep :8080
```

## 🔧 Step 8: Scaling and Optimization

### Scale Up for Production
```bash
# Scale to 20 workers for higher capacity
./scripts/scale.sh up 20

# Use production configuration
docker-compose -f docker-compose.prod.yml up -d
```

### Performance Tuning
```bash
# Monitor performance during load
watch -n 1 'curl -s http://localhost:8080/stats | jq'

# Adjust worker count based on load
docker-compose up -d --scale agent-worker=15

# Check resource utilization
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

## ✅ Step 9: Validation Checklist

### Pre-Flight Checklist (Before Testing)
- [ ] Docker and Docker Compose installed (`docker --version`)
- [ ] Python 3.8+ installed (`python3 --version`)
- [ ] All API accounts created (LiveKit, Twilio, Deepgram, ElevenLabs)
- [ ] .env file configured with all API keys
- [ ] Load test dependencies installed (`pip3 list | grep aiohttp`)

### System Health Checklist
- [ ] All containers are running (`docker-compose ps`)
- [ ] Health endpoint returns 200 (`curl http://localhost:8080/health`)
- [ ] Prometheus is collecting metrics (`curl http://localhost:9090/-/healthy`)
- [ ] Grafana dashboard accessible (`curl http://localhost:3000/api/health`)
- [ ] Redis queue is operational (`docker-compose exec redis redis-cli ping`)
- [ ] At least 10 agent workers running (`./scripts/scale.sh status`)

### API Integration Validation
- [ ] LiveKit API key works (`curl -H "Authorization: Bearer $LIVEKIT_API_KEY" https://api.livekit.io/`)
- [ ] Twilio credentials valid (`curl -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID`)
- [ ] Deepgram API key works (`curl -H "Authorization: Token $DEEPGRAM_API_KEY" https://api.deepgram.com/v1/projects`)
- [ ] ElevenLabs API key works (`curl -H "Authorization: Bearer $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/voices`)

### Performance Validation
- [ ] Small load test passes (10 calls, >95% success rate)
- [ ] Medium load test passes (25 calls, >95% success rate)
- [ ] Full load test achieves >95% success rate
- [ ] 95th percentile latency < 600ms
- [ ] System handles 100 concurrent calls
- [ ] No memory leaks during extended testing
- [ ] Error rates remain below 5%

### Integration Testing
- [ ] Manual agent dispatch works (`curl -X POST "http://localhost:8080/manual/dispatch?room=test&participant_identity=test"`)
- [ ] System stats endpoint returns data (`curl http://localhost:8080/stats`)
- [ ] Monitoring dashboards show metrics
- [ ] Load test produces valid JSON output
- [ ] No critical errors in container logs (`docker-compose logs | grep -i error`)

## 🆘 Troubleshooting Guide

### Common Issues and Solutions

**Issue**: "Permission denied" when running scripts
```bash
# Solution: Make scripts executable
chmod +x scripts/scale.sh
chmod +x tools/loadtest/load_test.py
```

**Issue**: "Port already in use"
```bash
# Solution: Stop conflicting services
sudo lsof -i :8080
sudo kill -9 <PID>
```

**Issue**: "API key invalid"
```bash
# Solution: Verify credentials
curl -H "Authorization: Bearer $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/voices
```

**Issue**: Docker containers failing to start
```bash
# Solution: Check logs and rebuild
docker-compose logs
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Issue**: High latency in tests
```bash
# Solution: Check network and service latency
ping api.deepgram.com
ping api.elevenlabs.io
curl -w "@curl-format.txt" -s -o /dev/null https://api.deepgram.com/health
```

## 🎯 Next Steps

After successful setup:

1. **Optimize Configuration**: Tune parameters based on your specific requirements
2. **Production Deployment**: Use `docker-compose.prod.yml` for production
3. **Custom Agents**: Modify agent logic in `services/agent/app.py`
4. **Monitoring Setup**: Configure alerting rules for production monitoring
5. **Security Hardening**: Implement proper authentication and encryption

## 📞 Support

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Verify your `.env` configuration
3. Ensure all API keys are valid and have sufficient credits
4. Check system resources (CPU, memory, network)
5. Review the troubleshooting section above

The system is now ready for production use with 100 concurrent calls and <600ms latency! 🚀
