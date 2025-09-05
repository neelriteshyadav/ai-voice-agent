import os, asyncio, json, time, logging, signal, sys
import aioredis
from prometheus_client import start_http_server, Histogram, Counter, Gauge
from contextlib import asynccontextmanager

from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.audio.interruptions.min_words_interruption_strategy import MinWordsInterruptionStrategy
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams

# Configuration
REDIS = os.getenv("REDIS_URL", "redis://redis:6379")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9300"))
LIVEKIT_URL = os.environ["LIVEKIT_URL"]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "100"))
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))
CONNECTION_POOL_SIZE = int(os.getenv("CONNECTION_POOL_SIZE", "20"))

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
TURN_RTT = Histogram("turn_rtt_ms", "User speech → first TTS sample back to caller (ms)",
                     buckets=(50,100,150,200,250,300,400,500,600,800,1000,1500,2000))
TURNS = Counter("turns_total", "Turns processed")
ACTIVE_CALLS = Gauge("active_calls", "Currently active calls")
PROCESSING_TIME = Histogram("processing_time_ms", "Time to process user input (ms)")
CONNECTION_ERRORS = Counter("connection_errors_total", "Connection errors")
PIPELINE_ERRORS = Counter("pipeline_errors_total", "Pipeline errors")

class OptimizedAgent:
    def __init__(self):
        self.stt_service = None
        self.tts_service = None
        self.redis = None
        self.active_pipelines = {}
        
    async def initialize(self):
        """Initialize reusable services for better performance"""
        self.redis = await aioredis.create_redis_pool(REDIS, maxsize=CONNECTION_POOL_SIZE)
        
        # Pre-initialize STT service with optimized settings
        self.stt_service = DeepgramSTTService(
            api_key=os.environ["DEEPGRAM_API_KEY"],
            interim_results=True,
            model=os.getenv("DEEPGRAM_MODEL", "nova-2-general-telephone"),
            language=os.getenv("DEEPGRAM_LANGUAGE", "en-US"),
            smart_format=True,
            diarize=False,  # Disable for lower latency
            punctuate=False,  # Disable for lower latency
            utterance_end_ms=1000,  # Faster end detection
            vad_turnoff=250  # Faster VAD turnoff
        )
        
        # Pre-initialize TTS service with optimized settings
        self.tts_service = ElevenLabsTTSService(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
            streaming=True,
            speed=float(os.getenv("ELEVENLABS_SPEED", "1.05")),
            stability=float(os.getenv("ELEVENLABS_STABILITY", "0.5")),
            similarity_boost=float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75")),
            optimize_streaming_latency=4,  # Maximum optimization
            output_format="pcm_16000"  # Direct PCM for lower latency
        )
        
        logger.info("Agent services initialized successfully")
    
    async def handle_call(self, room_data):
        """Handle a single call with optimized pipeline"""
        room = room_data["room"]
        token = room_data["token"]
        call_start_time = time.time()
        
        ACTIVE_CALLS.inc()
        logger.info(f"Starting agent for room: {room}")
        
        try:
            # Create optimized pipeline parameters
            pipeline_params = PipelineParams(
                interruption_strategies=[MinWordsInterruptionStrategy(min_words=1)],  # More responsive
                audio_buffer_size=int(os.getenv("AUDIO_BUFFER_SIZE", "160")),  # 10ms buffer
                enable_metrics=True,
                enable_usage_metrics=True
            )

            # Create transport with optimized settings
            transport_params = LiveKitParams(
                audio_in_sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "16000")),
                audio_in_channels=1,
                audio_in_enabled=True,
                audio_out_enabled=True
            )
            lk = LiveKitTransport(
                url=LIVEKIT_URL,
                token=token,
                room_name=room,
                params=transport_params
            )

            pipeline = Pipeline(
                transport=lk,
                stt=self.stt_service,
                tts=self.tts_service,
                params=pipeline_params
            )
            
            # Store pipeline reference
            self.active_pipelines[room] = pipeline
            
            # Enhanced event handlers with better latency tracking
            @pipeline.on("stt_partial")
            async def on_partial(text, ts_ms=None):
                if text and len(text.strip()) > 0:
                    if not pipeline.ctx.get("turn_active"):
                        pipeline.ctx["turn_active"] = True
                        pipeline.ctx["t_start_ms"] = ts_ms or int(time.time() * 1000)
                        pipeline.ctx["processing_start"] = time.time()
                        logger.debug(f"Turn started in {room}: {text[:50]}...")
            
            @pipeline.on("tts_first_chunk")
            async def on_tts_first_chunk(_chunk):
                if pipeline.ctx.get("turn_active"):
                    t0 = pipeline.ctx.get("t_start_ms", int(time.time() * 1000))
                    rtt = int(time.time() * 1000) - t0
                    TURN_RTT.observe(rtt)
                    TURNS.inc()
                    pipeline.ctx["turn_active"] = False
                    
                    # Track processing time separately
                    if pipeline.ctx.get("processing_start"):
                        processing_time = (time.time() - pipeline.ctx["processing_start"]) * 1000
                        PROCESSING_TIME.observe(processing_time)
                    
                    logger.debug(f"Turn completed in {room}: RTT={rtt}ms")
            
            @pipeline.on("user_final")
            async def on_user_final(text):
                if text and len(text.strip()) > 0:
                    logger.debug(f"User said in {room}: {text}")
                    # Optimized response generation
                    reply = self.generate_response(text)
                    await pipeline.say(reply)
            
            @pipeline.on("error")
            async def on_error(error):
                logger.error(f"Pipeline error in {room}: {error}")
                PIPELINE_ERRORS.inc()
            
            # Start the pipeline with timeout
            await asyncio.wait_for(pipeline.start(), timeout=AGENT_TIMEOUT)
            
        except asyncio.TimeoutError:
            logger.warning(f"Agent timeout for room: {room}")
        except Exception as e:
            logger.error(f"Error in agent for room {room}: {e}")
            CONNECTION_ERRORS.inc()
        finally:
            # Cleanup
            if room in self.active_pipelines:
                try:
                    await self.active_pipelines[room].stop()
                except:
                    pass
                del self.active_pipelines[room]
            
            ACTIVE_CALLS.dec()
            call_duration = time.time() - call_start_time
            logger.info(f"Agent finished for room: {room}, duration: {call_duration:.2f}s")
    
    def generate_response(self, user_text):
        """Generate optimized response for lower latency"""
        # Simple echo with minimal processing for lowest latency
        if len(user_text.strip()) < 5:
            return "I'm listening."
        return f"You said: {user_text}. How can I help you further?"

# Global agent instance
agent = OptimizedAgent()

async def run_worker():
    """Main worker loop with enhanced error handling and monitoring"""
    global agent
    
    # Initialize services
    await agent.initialize()
    start_http_server(METRICS_PORT)
    
    logger.info(f"Agent worker started, listening for jobs on Redis: {REDIS}")
    
    # Graceful shutdown handler
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, cleaning up...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while True:
        try:
            # Wait for job with timeout to allow periodic health checks
            job = await asyncio.wait_for(
                agent.redis.brpop("rooms", timeout=30), 
                timeout=35
            )
            
            if job:
                _, payload = job
                data = json.loads(payload)
                logger.debug(f"Received job: {data}")
                
                # Handle call asynchronously to allow concurrent processing
                asyncio.create_task(agent.handle_call(data))
            
        except asyncio.TimeoutError:
            # Periodic health check
            active_count = len(agent.active_pipelines)
            logger.debug(f"Health check: {active_count} active calls")
            continue
            
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            CONNECTION_ERRORS.inc()
            await asyncio.sleep(1)  # Brief pause before retry

if __name__ == "__main__":
    asyncio.run(run_worker())
