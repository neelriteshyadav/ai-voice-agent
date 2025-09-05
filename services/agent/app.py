import os, asyncio, json, time
import aioredis
from prometheus_client import start_http_server, Histogram, Counter

from pipecat.transports.livekit import LiveKitTransport
from pipecat.services.stt.deepgram import DeepgramSTTService
from pipecat.services.tts.elevenlabs import ElevenLabsTTSService
from pipecat.audio.interruptions.min_words_interruption_strategy import MinWordsInterruptionStrategy
from pipecat.pipeline import Pipeline, PipelineParams

REDIS = os.getenv("REDIS_URL", "redis://redis:6379")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9300"))
LIVEKIT_URL = os.environ["LIVEKIT_URL"]

TURN_RTT = Histogram("turn_rtt_ms", "User speech → first TTS sample back to caller (ms)",
                     buckets=(50,100,150,200,250,300,400,500,600,800,1000))
TURNS = Counter("turns_total", "Turns processed")

async def run_worker():
    r = await aioredis.from_url(REDIS)
    start_http_server(METRICS_PORT)
    while True:
        job = await r.brpop("rooms")
        _, payload = job
        data = json.loads(payload)
        room, token = data["room"], data["token"]

        stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"], interim_results=True,
                                 model=os.getenv("DEEPGRAM_MODEL", "nova-2-general-telephone"))
        tts = ElevenLabsTTSService(api_key=os.environ["ELEVENLABS_API_KEY"],
                                   voice_id=os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
                                   streaming=True, speed=float(os.getenv("ELEVENLABS_SPEED", "1.05")))

        params = PipelineParams(interruption_strategies=[MinWordsInterruptionStrategy(min_words=2)])

        lk = LiveKitTransport(url=LIVEKIT_URL, token=token)
        pipeline = Pipeline(transport=lk, stt=stt, tts=tts, params=params)

        @pipeline.on("stt_partial")
        async def on_partial(text, ts_ms=None):
            if not pipeline.ctx.get("turn_active"):
                pipeline.ctx["turn_active"] = True
                pipeline.ctx["t_start_ms"] = ts_ms or int(time.time()*1000)

        @pipeline.on("tts_first_chunk")
        async def on_tts_first_chunk(_chunk):
            if pipeline.ctx.get("turn_active"):
                t0 = pipeline.ctx.get("t_start_ms", int(time.time()*1000))
                rtt = int(time.time()*1000) - t0
                TURN_RTT.observe(rtt)
                TURNS.inc()
                pipeline.ctx["turn_active"] = False

        @pipeline.on("user_final")
        async def on_user_final(text):
            reply = f"You said: {text}. Noted."
            await pipeline.say(reply)

        try:
            await pipeline.start()
        finally:
            await pipeline.stop()

if __name__ == "__main__":
    asyncio.run(run_worker())
