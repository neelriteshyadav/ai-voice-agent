# Voice Agent System Architecture

## System Overview

This document describes the architecture of a production-grade voice agent system designed to handle 100 concurrent calls with sub-600ms latency.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                    PSTN Network                                  │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────────────────────┐
│                              Twilio SIP Trunk                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Phone Number    │  │ SIP Trunk       │  │ Webhook Handler │                │
│  │ +18883522916    │  │ Configuration   │  │                 │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │ SIP Protocol
┌─────────────────────▼───────────────────────────────────────────────────────────┐
│                            LiveKit Media Server                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ SIP Ingress     │  │ WebRTC Rooms    │  │ Media Router    │                │
│  │ call-* rooms    │  │ Per-call rooms  │  │ Audio Bridge    │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │ Webhook Events
┌─────────────────────▼───────────────────────────────────────────────────────────┐
│                              Orchestrator Layer                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ FastAPI Server  │  │ Load Balancer   │  │ Health Monitor  │                │
│  │ Webhook Handler │  │ Agent Dispatch  │  │ Metrics Export  │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │ Redis Queue
┌─────────────────────▼───────────────────────────────────────────────────────────┐
│                               Agent Workers                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Pipecat Agent 1 │  │ Pipecat Agent 2 │  │ ... Agent N     │                │
│  │ STT + TTS       │  │ STT + TTS       │  │ STT + TTS       │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │ API Calls
┌─────────────────────▼───────────────────────────────────────────────────────────┐
│                            External AI Services                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Deepgram STT    │  │ ElevenLabs TTS  │  │ Optional: LLM   │                │
│  │ Nova-2 Model    │  │ Streaming API   │  │ GPT/Claude      │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Monitoring & Analytics                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Prometheus      │  │ Grafana         │  │ Latency Analysis│                │
│  │ Metrics         │  │ Dashboards      │  │ Twilio Recorder │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. PSTN Integration Layer

**Twilio SIP Trunk**
- Handles inbound PSTN calls from regular phone numbers
- Converts PSTN to SIP protocol
- Routes calls to LiveKit SIP ingress
- Provides call recording and analytics

**Configuration:**
- Phone Number: +18883522916
- SIP URI: sip:2uwnrx411zr.sip.livekit.cloud
- Webhook URL: https://your-orchestrator.com/webhooks/livekit

### 2. Media Processing Layer

**LiveKit Server**
- WebRTC-based media server
- SIP ingress for telephony integration
- Per-call room isolation (call-{id} pattern)
- Audio bridging between PSTN and AI agents

**Key Features:**
- Low-latency audio processing
- Scalable WebRTC infrastructure
- Built-in recording capabilities
- Regional deployment for latency optimization

### 3. Orchestration Layer

**FastAPI Orchestrator**
- Webhook event processing from LiveKit
- Agent lifecycle management
- Load balancing across worker pool
- Health monitoring and metrics

**Core Functions:**
- `POST /webhooks/livekit` - Process participant events
- `GET /health` - System health check
- `GET /stats` - Real-time system statistics
- `POST /manual/dispatch` - Manual agent dispatch for testing

### 4. Agent Processing Layer

**Pipecat Agents**
- Python-based conversational AI agents
- Full-duplex audio with barge-in support
- Optimized for low-latency voice processing
- Horizontal scaling via containerization

**Components per Agent:**
- LiveKit transport for audio streaming
- Deepgram STT service (optimized settings)
- ElevenLabs TTS service (streaming enabled)
- Conversation logic and response generation

### 5. External AI Services

**Deepgram Speech-to-Text**
- Nova-2 model optimized for telephony
- Streaming recognition with interim results
- 16kHz audio optimized for phone calls
- Regional deployment for low latency

**ElevenLabs Text-to-Speech**
- Streaming synthesis for real-time response
- Voice cloning and natural speech
- Optimized for conversational latency
- PCM output for direct audio streaming

### 6. Data & Queue Layer

**Redis**
- Agent job queue (BRPOP pattern)
- Session state management
- Connection pooling for performance
- Persistence for reliability

### 7. Monitoring & Analytics

**Prometheus + Grafana**
- Real-time metrics collection
- Latency histograms and percentiles
- Error rate monitoring
- Resource utilization tracking

**Twilio Analytics**
- Call recording analysis
- True end-to-end latency measurement
- Audio quality assessment
- Call success rates

## Data Flow

### Call Initiation Flow

1. **PSTN Call** → Caller dials +18883522916
2. **Twilio SIP** → Routes to LiveKit SIP ingress
3. **LiveKit Room** → Creates call-{uuid} room
4. **Webhook Event** → `participant_joined` sent to orchestrator
5. **Agent Dispatch** → Orchestrator queues agent job in Redis
6. **Agent Pickup** → Available worker claims job from queue
7. **Audio Bridge** → Agent joins LiveKit room, audio flows

### Conversation Flow

1. **Audio Input** → Caller speech → LiveKit → Agent
2. **STT Processing** → Deepgram converts speech to text
3. **Response Generation** → Agent processes and generates response
4. **TTS Processing** → ElevenLabs converts text to speech
5. **Audio Output** → Speech → Agent → LiveKit → Caller

### Latency Optimization Points

- **Audio Buffers**: 10ms buffers (160 samples at 16kHz)
- **STT Streaming**: Interim results for faster response
- **TTS Streaming**: Chunk-based audio generation
- **Regional Deployment**: Services in same region
- **Connection Pooling**: Persistent connections to external APIs

## Scaling Architecture

### Horizontal Scaling

**Agent Workers**: 
- Stateless containers
- Auto-scaling based on queue length
- Resource limits: 1 CPU, 1GB RAM per worker
- Target: 5-10 calls per worker

**Load Distribution**:
- Redis queue for work distribution
- Multiple orchestrator instances (HA)
- Load balancer for webhook distribution

### Resource Allocation

**For 100 Concurrent Calls:**
```
Component           CPU Cores    Memory     Instances
Agent Workers       10-20        10-20GB    10-20
Orchestrator        1-2          1-2GB      1-2
Redis               1            1GB        1
LiveKit Server      2-4          2-4GB      1
Monitoring          1-2          2GB        3-4
Total               15-30        16-30GB    16-30
```

### Performance Targets

- **Concurrent Calls**: 100 simultaneous
- **End-to-End Latency**: <600ms (95th percentile)
- **Success Rate**: >95%
- **Audio Quality**: >90% clarity
- **System Uptime**: >99.9%

## Deployment Patterns

### Development
```bash
docker-compose up -d  # Basic setup
./scripts/scale.sh up 5  # 5 workers
```

### Production
```bash
docker-compose -f docker-compose.prod.yml up -d  # HA setup
./scripts/scale.sh up 20  # 20 workers
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-agents
spec:
  replicas: 20
  selector:
    matchLabels:
      app: voice-agent
  template:
    spec:
      containers:
      - name: agent
        image: voice-agent:latest
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
```

## Security Considerations

### Network Security
- TLS/WSS for all external connections
- VPC isolation for internal communication
- API key rotation and secrets management

### Access Control
- Webhook signature validation
- Rate limiting on public endpoints
- Monitoring for anomalous behavior

### Data Privacy
- No persistent audio storage (optional recording)
- Encrypted communication channels
- GDPR/compliance considerations

## Monitoring Strategy

### Key Metrics
- `turn_rtt_ms`: End-to-end conversation latency
- `active_calls`: Current concurrent call count
- `connection_errors_total`: Connection failure rate
- `pipeline_errors_total`: Agent processing errors

### Alerting Rules
- Latency P95 > 600ms
- Success rate < 95%
- Queue length > 50
- Worker failure rate > 5%

### Dashboards
- Real-time system overview
- Latency distribution heatmaps
- Error rate trends
- Resource utilization

## Disaster Recovery

### Backup Strategy
- Redis persistence enabled
- Configuration in version control
- Monitoring data retention (30 days)

### Failover Procedures
- Multi-region deployment options
- Automatic container restart
- Circuit breaker patterns for external APIs
- Graceful degradation under load

## Performance Optimization

### Latency Reduction
1. **Regional Deployment**: Co-locate services
2. **Connection Pooling**: Reuse HTTP connections
3. **Audio Optimization**: Minimal buffer sizes
4. **Streaming APIs**: Chunk-based processing

### Throughput Optimization
1. **Horizontal Scaling**: Add more workers
2. **Resource Tuning**: Optimize CPU/memory allocation
3. **Queue Management**: Efficient job distribution
4. **Caching**: Redis for session state

### Cost Optimization
1. **Auto-scaling**: Scale workers based on demand
2. **Regional Selection**: Choose cost-effective regions
3. **API Usage**: Optimize STT/TTS usage patterns
4. **Resource Right-sizing**: Match allocation to usage
