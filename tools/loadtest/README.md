# Load Testing for Voice Agent System

This directory contains comprehensive load testing tools to validate the voice agent system can handle 100 concurrent calls with <600ms end-to-end latency.

## Prerequisites

Before running load tests, ensure you have:
- ✅ Voice agent system running (`cd ../.. && ./scripts/scale.sh status`)
- ✅ Python 3.8+ installed (`python3 --version`)
- ✅ System scaled to at least 10 workers (`./scripts/scale.sh up 10`)

## Quick Start

### 1. Install Dependencies
```bash
# Install load testing requirements
pip3 install -r requirements.txt

# Verify installation
python3 -c "import aiohttp, asyncio; print('✅ Dependencies installed successfully')"
```

### 2. Start the Voice Agent System
```bash
# Navigate to project root
cd ../..

# Start system with 10 workers (recommended for 100 calls)
./scripts/scale.sh up 10

# Verify system is healthy
./scripts/scale.sh status
# Should show: ✓ Orchestrator: Healthy
```

### 3. Run Load Tests
```bash
# Return to load test directory
cd tools/loadtest

# Quick development test (10 calls, 2 minutes)
python3 load_test.py --calls 10 --duration 2 --ramp-up 5

# Production scale test (100 concurrent calls)
python3 load_test.py --calls 100 --duration 5 --ramp-up 30 --output results.json
```

### 4. Analyze Results
```bash
# View detailed results
cat results.json | python3 -m json.tool

# Quick pass/fail check
python3 -c "
import json
try:
    with open('results.json') as f:
        data = json.load(f)
        success_rate = data.get('test_summary', {}).get('success_rate_percent', 0)
        latency_ok = data.get('test_summary', {}).get('latency_target_met', False)
        print(f'Success Rate: {success_rate}% (Target: ≥95%)')
        print(f'Latency Target Met: {latency_ok} (Target: <600ms)')
        if success_rate >= 95 and latency_ok:
            print('🎉 LOAD TEST PASSED!')
        else:
            print('❌ Load test failed - check system scaling')
except FileNotFoundError:
    print('❌ No results.json found - run a test first')
"
```

## Load Test Script (load_test.py)

Comprehensive load testing script that simulates concurrent voice calls and measures performance.

### Features

- **Concurrent Call Simulation**: Simulates up to 100 concurrent calls
- **Gradual Ramp-up**: Gradually increases load over specified time period
- **Latency Measurement**: Measures end-to-end dispatch latency
- **Health Monitoring**: Continuous monitoring of system health during test
- **Comprehensive Reporting**: Detailed performance analysis and recommendations

### Usage

```bash
# Basic test with 100 calls
python load_test.py --calls 100

# Custom configuration
python load_test.py \
  --calls 50 \
  --ramp-up 20 \
  --duration 5 \
  --url http://localhost:8080 \
  --output results.json

# Quick test for development
python load_test.py --calls 10 --duration 2
```

### Parameters

- `--calls`: Number of concurrent calls to simulate (default: 100)
- `--ramp-up`: Ramp-up time in seconds (default: 30)
- `--duration`: Test duration in minutes (default: 10)
- `--url`: Orchestrator URL (default: http://localhost:8080)
- `--max-concurrent`: Maximum concurrent calls (default: 100)
- `--output`: Output file for JSON results

### Success Criteria

The test passes if:
- Success rate ≥ 95%
- 95th percentile latency < 600ms
- System remains stable throughout test

### Example Output

```json
{
  "test_summary": {
    "total_calls": 100,
    "successful_calls": 98,
    "failed_calls": 2,
    "success_rate_percent": 98.0,
    "latency_target_met": true
  },
  "dispatch_latency_ms": {
    "mean": 245.3,
    "median": 230.1,
    "p95": 456.7,
    "p99": 523.2
  },
  "performance_assessment": {
    "latency_target": "< 600ms (95th percentile)",
    "target_achieved": true,
    "concurrent_calls_supported": 98
  }
}
```

## Telephony Analysis (analyze_recordings.py)

Analyzes actual Twilio call recordings to measure true end-to-end latency from caller speech to agent response.

### Features

- **Audio Analysis**: Processes stereo recordings (caller on left, agent on right)
- **Onset Detection**: Detects speech start times using energy thresholds
- **Latency Calculation**: Measures time between caller speech and agent response
- **CSV Export**: Exports measurements for further analysis

### Usage

```bash
# Set environment variables
export TWILIO_ACCOUNT_SID=your_sid
export TWILIO_AUTH_TOKEN=your_token

# Run analysis
python analyze_recordings.py
```

### Environment Variables

- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
- `RUN_TAG`: Tag to filter recordings (default: "loadtest")
- `OUT_CSV`: Output CSV file (default: "latency.csv")

## Performance Benchmarks

### Target Performance

- **Concurrent Calls**: 100 simultaneous active calls
- **End-to-End Latency**: <600ms (95th percentile)
- **Success Rate**: >95%
- **System Stability**: No degradation over 10+ minute tests

### Typical Results

With optimized configuration:
- **50th percentile**: ~200-250ms
- **95th percentile**: ~400-500ms
- **99th percentile**: ~550-600ms
- **Success rate**: 98-99%

## Troubleshooting Load Tests

### Before Running Tests

**System Health Check:**
```bash
# Ensure system is ready for load testing
cd ../..
./scripts/scale.sh status

# Should show all green checkmarks:
# ✓ Orchestrator: Healthy
# ✓ Redis: Healthy
# ✓ Prometheus: Healthy
# ✓ Grafana: Healthy

# Check worker count
./scripts/scale.sh status | grep "agent-worker"
# Should show at least 10 workers running
```

**Dependency Verification:**
```bash
cd tools/loadtest
# Test Python dependencies
python3 -c "import aiohttp, asyncio; print('Dependencies OK')"

# Test system connectivity
curl http://localhost:8080/health
curl http://localhost:8080/stats
```

### Common Load Test Issues

#### 1. High Latency (>600ms)
```bash
# Check external service latency
ping api.deepgram.com
ping api.elevenlabs.io

# Monitor system during test (run in separate terminal)
watch -n 1 'curl -s http://localhost:8080/stats | python3 -m json.tool'

# Check resource usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Solutions:
# - Scale up workers: ./scripts/scale.sh up 15
# - Check network connectivity
# - Verify API keys are working
```

#### 2. Low Success Rate (<95%)
```bash
# Check for errors in logs
docker-compose logs orchestrator | tail -50
docker-compose logs agent-worker-1 | tail -50

# Check Redis queue length
docker-compose exec redis redis-cli llen rooms

# Check system capacity
curl http://localhost:8080/stats | grep -E "(active|queue|error)"

# Solutions:
# - Scale up workers: ./scripts/scale.sh up 15
# - Verify all API keys are valid
# - Check for rate limiting on external APIs
# - Ensure adequate system resources (CPU/memory)
```

#### 3. Connection Errors
```bash
# Test orchestrator connectivity
curl -v http://localhost:8080/health

# Check if orchestrator is running
docker-compose ps orchestrator

# Restart if needed
docker-compose restart orchestrator

# Check firewall/port issues
sudo lsof -i :8080
```

#### 4. Python/Dependency Errors
```bash
# Reinstall dependencies
pip3 install --upgrade -r requirements.txt

# Check Python version
python3 --version  # Should be 3.8+

# Test imports individually
python3 -c "import aiohttp; print('aiohttp OK')"
python3 -c "import asyncio; print('asyncio OK')"
```

### Monitoring During Tests

**Real-time Monitoring:**
```bash
# Terminal 1: Run the load test
python3 load_test.py --calls 100 --duration 5 --output results.json

# Terminal 2: Monitor system stats
watch -n 1 'curl -s http://localhost:8080/stats | python3 -m json.tool'

# Terminal 3: Monitor container resources
watch -n 2 'docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"'
```

**Key Metrics to Watch:**
- **Active Calls**: Should ramp up to target (e.g., 100)
- **Queue Length**: Should remain low (< 10)
- **Success Rate**: Should stay above 95%
- **CPU Usage**: Should be < 80% per container
- **Memory Usage**: Should be stable (no leaks)

### Performance Tuning

**For Better Results:**
```bash
# Scale up workers before testing
./scripts/scale.sh up 15  # More workers for higher capacity

# Use production configuration
docker-compose -f docker-compose.prod.yml up -d

# Optimize load test parameters
python3 load_test.py \
  --calls 100 \
  --ramp-up 60 \    # Slower ramp-up
  --duration 10 \   # Longer test
  --max-concurrent 100
```

**System Resource Optimization:**
```bash
# Check available resources
free -h  # Memory
nproc    # CPU cores
df -h    # Disk space

# For high-load testing, ensure:
# - 16GB+ RAM
# - 8+ CPU cores
# - Fast SSD storage
# - Stable network connection
```

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
- name: Load Test
  run: |
    docker-compose up -d
    sleep 30
    python tools/loadtest/load_test.py --calls 50 --duration 3
```
