# Production-Grade Voice Agent System

A scalable voice agent system designed to handle 100 concurrent calls with <600ms end-to-end latency using Pipecat AI agents and LiveKit for media routing.

## 🎯 System Overview

This system demonstrates a production-ready architecture capable of:
- **100 concurrent voice calls** with full duplex audio and barge-in support
- **<600ms end-to-end latency** from caller speech to AI response
- **Telephony integration** via Twilio SIP trunk to LiveKit rooms
- **Horizontal scaling** with containerized workers and load balancing
- **Comprehensive monitoring** with Prometheus, Grafana, and real-time metrics
- **Automated load testing** and latency analysis tools

### Architecture Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PSTN Caller   │───▶│  Twilio SIP     │───▶│  LiveKit Room   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Pipecat Agent  │◀───│  Orchestrator   │◀───│  Webhook Event  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ Deepgram STT    │    │ Redis Queue     │
│ ElevenLabs TTS  │    │ Load Balancer   │
└─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

**⚡ New to this system? Start here:** [QUICK_START.md](QUICK_START.md) - Get running in 30 minutes!

### Prerequisites

- **Docker & Docker Compose**: Version 20.0+ ([Install Guide](https://docs.docker.com/get-docker/))
- **Python 3.8+**: For load testing and analysis tools
- **API Accounts**: LiveKit, Twilio, Deepgram, ElevenLabs (see [SETUP.md](SETUP.md) for detailed signup instructions)

### 1. Complete Setup (First Time)

**Follow the complete setup guide for detailed instructions:**
```bash
# Read the complete setup guide first
cat SETUP.md

# Or view it online: https://github.com/your-repo/SETUP.md
```

**Quick setup summary:**
```bash
# 1. Clone and navigate to the project
cd voice-agent-100calls

# 2. Install Python dependencies for testing
python3 get-pip.py --user  # Install pip if needed
cd tools/loadtest && pip3 install -r requirements.txt && cd ../..

# 3. Copy and configure environment variables
cp env.template .env
# Edit .env with your API keys (see SETUP.md for account setup)

# 4. Make scripts executable
chmod +x scripts/scale.sh
```

### 2. Start the System

```bash
# Start with default 10 agent workers (recommended for 100 calls)
./scripts/scale.sh up 10

# Check system status
./scripts/scale.sh status

# Should show all services running:
# ✓ Orchestrator: Healthy
# ✓ Redis: Healthy  
# ✓ Prometheus: Healthy
# ✓ Grafana: Healthy
```

### 3. Verify System Health

```bash
# Run comprehensive health tests
./scripts/scale.sh test

# Manual verification
curl http://localhost:8080/health
curl http://localhost:8080/stats | python3 -m json.tool

# Access monitoring dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

### 4. Run Load Tests

📖 **Complete Testing Guide Available:** [TESTING_GUIDE.md](TESTING_GUIDE.md)

```bash
cd tools/loadtest

# Quick development test (10 calls)
python3 load_test.py --calls 10 --duration 2 --ramp-up 5

# Production scale test (100 concurrent calls)
python3 load_test.py --calls 100 --duration 5 --ramp-up 30 --output results.json

# View results and check if test passed
cat results.json | python3 -m json.tool
python3 -c "
import json
with open('results.json') as f:
    data = json.load(f)
    success_rate = data.get('test_summary', {}).get('success_rate_percent', 0)
    latency_ok = data.get('test_summary', {}).get('latency_target_met', False)
    if success_rate >= 95 and latency_ok:
        print('🎉 LOAD TEST PASSED!')
    else:
        print('❌ Load test failed - see TESTING_GUIDE.md for troubleshooting')
"

# Success criteria: >95% success rate, <600ms latency
```

### 5. Test with Real Phone Calls

```bash
# Configure Twilio webhook (see SETUP.md for details)
# Then call your Twilio phone number to test the AI agent

# Analyze call recordings (after making calls)
cd tools/latency
export TWILIO_ACCOUNT_SID=your_sid
export TWILIO_AUTH_TOKEN=your_token
python3 analyze_recordings.py
```

## 📊 Monitoring and Metrics

### Access Points

- **Orchestrator API**: http://localhost:8080
- **Prometheus Metrics**: http://localhost:9090
- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **System Health**: http://localhost:8080/health
- **System Stats**: http://localhost:8080/stats

### Key Metrics

- **End-to-End Latency**: 95th percentile <600ms target
- **Active Calls**: Current concurrent call count
- **Success Rate**: >95% target for production readiness
- **Error Rates**: Connection, pipeline, and dispatch errors
- **Resource Utilization**: CPU, memory, and queue length

## 🔧 Configuration Guide

### Environment Variables (.env)

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token

# STT/TTS Services
DEEPGRAM_API_KEY=your-deepgram-key
ELEVENLABS_API_KEY=your-elevenlabs-key

# Performance Tuning
MAX_CONCURRENT_AGENTS=100
WORKER_SCALE_FACTOR=10
AUDIO_BUFFER_SIZE=160  # 10ms at 16kHz
```

### LiveKit SIP Configuration

Configure your LiveKit SIP integration:

```json
{
  "name": "PSTN → per-call room optimized",
  "rule": {
    "dispatchRuleIndividual": {
      "roomPrefix": "call-"
    }
  },
  "room_config": {
    "region": "us-central",
    "max_participants": 2,
    "audio": {
      "preset": "speech",
      "codecs": ["opus", "PCMU", "PCMA"]
    }
  }
}
```

## 📈 Performance Optimization

### Latency Optimization

1. **Regional Deployment**: Deploy services in the same region as your users
2. **Audio Settings**: Use optimized codecs and buffer sizes
3. **STT/TTS Configuration**: Enable streaming and optimize for voice
4. **Network**: Ensure low-latency network connectivity

### Scaling Configuration

The system supports horizontal scaling:

```bash
# Scale to different worker counts
./scripts/scale.sh up 5   # Light load (25-50 calls)
./scripts/scale.sh up 10  # Standard load (50-100 calls)
./scripts/scale.sh up 15  # Heavy load (100+ calls)
```

### Resource Requirements

**Per Agent Worker:**
- CPU: 1 core (0.5 reserved)
- Memory: 1GB (512MB reserved)
- Network: Low latency to STT/TTS services

**For 100 Concurrent Calls:**
- Total CPU: 10-15 cores
- Total Memory: 10-15GB
- Redis: 512MB
- Orchestrator: 512MB

## 🧪 Testing and Validation

### Load Testing

```bash
# Comprehensive 100-call test
python tools/loadtest/load_test.py \
  --calls 100 \
  --ramp-up 30 \
  --duration 10 \
  --output results.json

# Performance validation
python tools/loadtest/load_test.py \
  --calls 50 \
  --duration 5 \
  --url http://localhost:8080
```

### Latency Analysis

```bash
# Analyze Twilio call recordings
cd tools/latency
export TWILIO_ACCOUNT_SID=your_sid
export TWILIO_AUTH_TOKEN=your_token
python analyze_recordings.py
```

### Success Criteria

✅ **System passes if:**
- Success rate ≥ 95%
- 95th percentile latency < 600ms
- System remains stable during 10+ minute tests
- No memory leaks or resource exhaustion

## 🔍 Troubleshooting

### Quick Diagnostic Commands

```bash
# System health overview
./scripts/scale.sh status

# Check all container logs
docker-compose logs --tail=50

# Check specific service logs
docker-compose logs orchestrator
docker-compose logs agent-worker-1

# System resource usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# API connectivity tests
curl http://localhost:8080/health
curl http://localhost:8080/stats
```

### Common Issues and Solutions

#### 1. "Permission denied" when running scripts
```bash
# Fix: Make scripts executable
chmod +x scripts/scale.sh
chmod +x tools/loadtest/load_test.py
```

#### 2. "Port already in use" errors
```bash
# Find and kill conflicting processes
sudo lsof -i :8080  # Check port 8080
sudo lsof -i :3000  # Check port 3000
sudo kill -9 <PID>  # Kill the process

# Or use different ports in docker-compose.yml
```

#### 3. API key authentication errors
```bash
# Test each API key individually
curl -H "Authorization: Token $DEEPGRAM_API_KEY" https://api.deepgram.com/v1/projects
curl -H "Authorization: Bearer $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/voices
curl -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID

# Verify .env file is properly formatted (no spaces around =)
cat .env | grep -v '^#' | grep '='
```

#### 4. Docker containers failing to start
```bash
# Check Docker daemon
docker system info

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check container logs
docker-compose logs
```

#### 5. High Latency Issues
```bash
# Check external service latency
ping api.deepgram.com
ping api.elevenlabs.io
curl -w "@curl-format.txt" -s -o /dev/null https://api.deepgram.com/health

# Monitor system resources
docker stats

# Check Redis queue length
docker-compose exec redis redis-cli llen rooms
```

#### 6. Load Test Failures
```bash
# Ensure system is properly scaled
./scripts/scale.sh up 10

# Check system capacity
curl http://localhost:8080/stats | grep -E "(active|queue)"

# Run smaller test first
cd tools/loadtest
python3 load_test.py --calls 5 --duration 1
```

#### 7. Missing Python Dependencies
```bash
# Install missing packages
pip3 install aiohttp asyncio twilio pydub numpy scipy matplotlib pandas prometheus-client

# Verify installations
python3 -c "import aiohttp, asyncio; print('Load test dependencies OK')"
python3 -c "import twilio; print('Twilio SDK OK')"
```

### Getting Help

If you're still having issues:

1. **Check the complete setup guide**: `cat SETUP.md`
2. **Verify all prerequisites**: Docker, Python, API accounts
3. **Check system resources**: Ensure adequate CPU/memory
4. **Review logs**: Look for specific error messages
5. **Test components individually**: API keys, Docker containers, load tests

### Performance Optimization

For better performance:

```bash
# Scale up workers for higher capacity
./scripts/scale.sh up 15

# Use production configuration
docker-compose -f docker-compose.prod.yml up -d

# Monitor during load tests
watch -n 1 'curl -s http://localhost:8080/stats | jq'
```

## 🏗️ Production Deployment

### Docker Compose Production

```yaml
# Override for production
version: "3.9"
services:
  orchestrator:
    deploy:
      replicas: 2  # HA orchestrator
      resources:
        limits:
          cpus: '1.0'
          memory: 1GB
  
  agent-worker:
    deploy:
      replicas: 20  # Scale for production load
      resources:
        limits:
          cpus: '1.0'
          memory: 1GB
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-agent-workers
spec:
  replicas: 20
  selector:
    matchLabels:
      app: voice-agent-worker
  template:
    spec:
      containers:
      - name: agent-worker
        image: voice-agent-worker:latest
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
```

### Health Checks and Monitoring

```yaml
# Health check configuration
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

## 📋 API Reference

### Orchestrator Endpoints

- `GET /health` - System health check
- `GET /stats` - Current system statistics
- `POST /webhooks/livekit` - LiveKit webhook handler
- `POST /manual/dispatch` - Manual agent dispatch for testing
- `GET /metrics` - Prometheus metrics

### Example API Usage

```bash
# Check system health
curl http://localhost:8080/health

# Get current statistics
curl http://localhost:8080/stats

# Manual agent dispatch
curl -X POST "http://localhost:8080/manual/dispatch?room=test-room&participant_identity=test-user"
```

## 🔐 Security Considerations

1. **API Keys**: Store securely using environment variables or secrets management
2. **Network Security**: Use HTTPS/WSS in production
3. **Access Control**: Implement proper authentication for management endpoints
4. **Monitoring**: Enable security monitoring and alerting

## 📞 Twilio Integration

### SIP Trunk Configuration

Example Twilio configuration:

```
SID: TK9861f55f63ff945910f50ba0ba194495
Friendly Name: My voice agent
Domain: voice-agent-cosmos.pstn.twilio.com

SIP URI: sip:2uwnrx411zr.sip.livekit.cloud
Phone Number: +18883522916
```

