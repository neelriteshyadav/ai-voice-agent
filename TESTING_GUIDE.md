# Complete Testing and Validation Guide

This guide provides step-by-step instructions for testing and validating the voice agent system, from basic health checks to full-scale load testing.

## Testing Overview

The voice agent system has multiple testing layers:

1. **System Health Tests** - Verify all components are running
2. **API Integration Tests** - Validate external service connectivity  
3. **Load Tests** - Simulate concurrent calls and measure performance
4. **Real Phone Call Tests** - End-to-end validation with actual calls
5. **Latency Analysis** - Measure true end-to-end response times

## Prerequisites

Before testing, ensure:
- ✅ System is running: `./scripts/scale.sh status`
- ✅ All API keys configured in `.env`
- ✅ Python dependencies installed: see [INSTALL_DEPENDENCIES.md](INSTALL_DEPENDENCIES.md)
- ✅ At least 10 agent workers running for load tests

## 1. System Health Tests

### Basic Health Check
```bash
# Quick system status
./scripts/scale.sh status

# Should show all green checkmarks:
# ✓ Orchestrator: Healthy
# ✓ Redis: Healthy
# ✓ Prometheus: Healthy  
# ✓ Grafana: Healthy
```

### Detailed Health Validation
```bash
# Test each service individually
curl http://localhost:8080/health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health

# Check system statistics
curl http://localhost:8080/stats | python3 -m json.tool

# Verify container status
docker-compose ps

# Check container logs for errors
docker-compose logs --tail=20 orchestrator
docker-compose logs --tail=20 agent-worker-1
```

### Expected Results
- All health endpoints return 200 OK
- No critical errors in logs
- All containers show "Up" status
- System stats show reasonable values

## 2. API Integration Tests

### Test External Service Connectivity
```bash
# Test Deepgram API
curl -H "Authorization: Token $DEEPGRAM_API_KEY" \
     "https://api.deepgram.com/v1/projects" \
     && echo "✅ Deepgram API OK" || echo "❌ Deepgram API Failed"

# Test ElevenLabs API
curl -H "Authorization: Bearer $ELEVENLABS_API_KEY" \
     "https://api.elevenlabs.io/v1/voices" \
     && echo "✅ ElevenLabs API OK" || echo "❌ ElevenLabs API Failed"

# Test Twilio API
curl -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN \
     "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID" \
     && echo "✅ Twilio API OK" || echo "❌ Twilio API Failed"

# Test LiveKit API (if accessible)
# Note: LiveKit API testing depends on your setup
```

### Manual Agent Dispatch Test
```bash
# Test agent dispatch functionality
test_room="test-$(date +%s)"
curl -X POST "http://localhost:8080/manual/dispatch?room=$test_room&participant_identity=test-user"

# Check if agent was dispatched
sleep 2
curl http://localhost:8080/stats | grep -i active

# Expected: Should show 1 active room/call
```

## 3. Load Testing

### 3.1 Small Scale Tests (Development)

**Quick 5-call test:**
```bash
cd tools/loadtest

# Verify dependencies
python3 -c "import aiohttp, asyncio; print('Dependencies OK')"

# Run small test
python3 load_test.py --calls 5 --duration 1 --ramp-up 2

# Expected results:
# - Success rate: 100%
# - All calls complete within 30 seconds
# - No errors in output
```

**Medium 25-call test:**
```bash
# Scale up system first
cd ../..
./scripts/scale.sh up 10
cd tools/loadtest

# Run medium test with output file
python3 load_test.py --calls 25 --duration 3 --ramp-up 10 --output medium_test.json

# Check results
cat medium_test.json | python3 -m json.tool

# Validate results
python3 -c "
import json
with open('medium_test.json') as f:
    data = json.load(f)
    success_rate = data.get('test_summary', {}).get('success_rate_percent', 0)
    print(f'Success Rate: {success_rate}%')
    if success_rate >= 95:
        print('✅ Medium test PASSED')
    else:
        print('❌ Medium test FAILED - check system capacity')
"
```

### 3.2 Full Scale Load Test (100 Concurrent Calls)

**Preparation:**
```bash
# Ensure system is properly scaled
./scripts/scale.sh up 10

# Monitor system resources (run in separate terminal)
watch -n 2 'curl -s http://localhost:8080/stats | python3 -m json.tool'
```

**Run Full Load Test:**
```bash
cd tools/loadtest

# Full production load test
python3 load_test.py \
  --calls 100 \
  --duration 5 \
  --ramp-up 30 \
  --output full_load_test.json

# This will take approximately 8-10 minutes total:
# - 30 seconds ramp-up
# - 5 minutes sustained load  
# - 2-3 minutes wind-down
```

**Monitor During Test:**
```bash
# Terminal 2: System monitoring
watch -n 1 'curl -s http://localhost:8080/stats | python3 -m json.tool'

# Terminal 3: Resource monitoring  
watch -n 2 'docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"'

# Key metrics to watch:
# - Active calls should reach ~100
# - Success rate should stay >95%
# - CPU usage should be <80% per container
# - Memory should be stable (no leaks)
```

**Analyze Results:**
```bash
# View detailed results
cat full_load_test.json | python3 -m json.tool

# Quick pass/fail assessment
python3 -c "
import json
with open('full_load_test.json') as f:
    data = json.load(f)
    summary = data.get('test_summary', {})
    success_rate = summary.get('success_rate_percent', 0)
    latency_ok = summary.get('latency_target_met', False)
    
    print('=== LOAD TEST RESULTS ===')
    print(f'Total Calls: {summary.get(\"total_calls\", 0)}')
    print(f'Successful: {summary.get(\"successful_calls\", 0)}')
    print(f'Failed: {summary.get(\"failed_calls\", 0)}')
    print(f'Success Rate: {success_rate}% (Target: ≥95%)')
    print(f'Latency Target Met: {latency_ok} (Target: <600ms)')
    
    if success_rate >= 95 and latency_ok:
        print('🎉 LOAD TEST PASSED!')
        print('System is ready for production use.')
    else:
        print('❌ LOAD TEST FAILED')
        if success_rate < 95:
            print('- Scale up workers or check API limits')
        if not latency_ok:
            print('- Optimize network connectivity or service configuration')
"
```

### Expected Load Test Results

**Passing Results:**
- Success rate: ≥95%
- 95th percentile latency: <600ms
- Mean latency: 200-300ms
- No system crashes or memory leaks
- Stable performance throughout test duration

**If Tests Fail:**
```bash
# Common solutions:
# 1. Scale up workers
./scripts/scale.sh up 15

# 2. Check API rate limits
docker-compose logs orchestrator | grep -i "rate\|limit\|error"

# 3. Verify system resources
docker stats

# 4. Check external service latency
ping api.deepgram.com
ping api.elevenlabs.io
```

## 4. Real Phone Call Testing

### 4.1 Configure Twilio Webhook

**For Local Testing (using ngrok):**
```bash
# Install ngrok
npm install -g ngrok
# or download from https://ngrok.com/

# Expose local orchestrator
ngrok http 8080

# Copy the ngrok URL (e.g., https://abc123.ngrok.io)
# Configure in Twilio Console:
# Phone Numbers → Your Number → Voice Configuration
# Webhook URL: https://abc123.ngrok.io/webhooks/livekit
```

**For Production:**
```bash
# Use your actual domain
# Webhook URL: https://your-domain.com/webhooks/livekit
```

### 4.2 Test Phone Calls

**Make Test Calls:**
1. Call your Twilio phone number
2. You should hear the AI agent respond
3. Test conversation and barge-in functionality
4. Try interrupting the agent mid-sentence

**Expected Behavior:**
- Call connects within 2-3 seconds
- Agent responds with greeting
- Agent handles interruptions smoothly
- Low latency conversation flow
- Call quality is clear

### 4.3 Monitor Call Quality

```bash
# Monitor active calls during phone test
curl http://localhost:8080/stats

# Check for errors
docker-compose logs orchestrator | tail -20
docker-compose logs agent-worker-1 | tail -20

# View Grafana dashboards for real-time metrics
open http://localhost:3000
```

## 5. Latency Analysis

### 5.1 Analyze Call Recordings

**Prerequisites:**
```bash
# Set Twilio credentials
export TWILIO_ACCOUNT_SID=your_account_sid
export TWILIO_AUTH_TOKEN=your_auth_token

# Verify credentials
curl -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN \
     "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID"
```

**Run Analysis:**
```bash
cd tools/latency

# Analyze recent call recordings
python3 analyze_recordings.py

# View results
cat latency.csv

# Expected output: CSV with turn-by-turn latency measurements
```

### 5.2 Interpret Latency Results

**Good Results:**
- Mean latency: <300ms
- 95th percentile: <600ms  
- Most turns: <500ms
- Few outliers >1000ms

**If Latency is High:**
```bash
# Check external service response times
curl -w "@curl-format.txt" -s -o /dev/null https://api.deepgram.com/health
curl -w "@curl-format.txt" -s -o /dev/null https://api.elevenlabs.io/v1/voices

# Check system resources
docker stats

# Review agent logs for processing delays
docker-compose logs agent-worker-1 | grep -i latency
```

## 6. Comprehensive Validation Checklist

### Pre-Test Checklist
- [ ] Docker and Docker Compose installed
- [ ] Python 3.8+ installed  
- [ ] All API accounts created and keys configured
- [ ] `.env` file properly configured
- [ ] Python dependencies installed
- [ ] System started with adequate workers (10+)

### System Health Validation
- [ ] All containers running (`docker-compose ps`)
- [ ] Health endpoints return 200 (`curl http://localhost:8080/health`)
- [ ] No critical errors in logs
- [ ] Monitoring dashboards accessible
- [ ] Redis operational (`docker-compose exec redis redis-cli ping`)

### Load Test Validation
- [ ] Small test (5 calls) passes with 100% success
- [ ] Medium test (25 calls) passes with >95% success  
- [ ] Full load test (100 calls) passes with >95% success
- [ ] 95th percentile latency <600ms
- [ ] No memory leaks during extended testing
- [ ] System stable throughout test duration

### Integration Test Validation
- [ ] Manual agent dispatch works
- [ ] All external APIs respond correctly
- [ ] Phone calls connect successfully
- [ ] AI agent responds appropriately
- [ ] Barge-in functionality works
- [ ] Call recordings generated and analyzable

### Performance Validation
- [ ] Mean latency <300ms
- [ ] 95th percentile latency <600ms
- [ ] Success rate >95% consistently
- [ ] System handles target concurrent load
- [ ] Resource usage within acceptable limits
- [ ] No degradation over extended periods

## Troubleshooting Common Test Failures

### Load Test Failures
```bash
# Check system scaling
./scripts/scale.sh status

# Verify API connectivity  
curl http://localhost:8080/health

# Check for API rate limiting
docker-compose logs orchestrator | grep -i rate

# Monitor resources
docker stats
```

### Phone Call Issues
```bash
# Verify Twilio webhook configuration
curl -X POST "http://localhost:8080/webhooks/livekit" \
     -H "Content-Type: application/json" \
     -d '{"test": true}'

# Check LiveKit SIP configuration
# Review Twilio trunk settings
```

### High Latency Issues
```bash
# Test external service latency
ping api.deepgram.com
ping api.elevenlabs.io

# Check system resources
docker stats

# Review processing logs
docker-compose logs agent-worker-1 | grep -i processing
```

## Continuous Testing

### Automated Testing Script
```bash
#!/bin/bash
# save as test_system.sh

echo "Running comprehensive system tests..."

# 1. Health check
./scripts/scale.sh test || exit 1

# 2. Small load test
cd tools/loadtest
python3 load_test.py --calls 10 --duration 1 || exit 1

# 3. API connectivity
curl -f http://localhost:8080/health || exit 1

echo "All tests passed! System is healthy."
```

### CI/CD Integration
```yaml
# Example GitHub Actions workflow
- name: Test Voice Agent System
  run: |
    docker-compose up -d
    sleep 30
    ./scripts/scale.sh test
    cd tools/loadtest
    python3 load_test.py --calls 25 --duration 2
```

The system is considered production-ready when all tests pass consistently with the target performance metrics.
