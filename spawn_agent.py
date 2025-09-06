#!/usr/bin/env python3
import os
import asyncio
import datetime
from dotenv import load_dotenv
from livekit import api as lkapi

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner

# non-deprecated LiveKit transport
from pipecat.transports.livekit.transport import LiveKitTransport, LiveKitParams

from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions as DGLiveOptions
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

from pipecat.frames.frames import (
    Frame, TranscriptionFrame, InterimTranscriptionFrame, TTSSpeakFrame
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.audio.interruptions.min_words_interruption_strategy import MinWordsInterruptionStrategy

# ---------- env ----------
load_dotenv()

def need(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

LK_URL    = need("LIVEKIT_URL")                     # wss://<proj>.livekit.cloud or ws://localhost:7880
LK_KEY    = need("LIVEKIT_API_KEY")
LK_SECRET = need("LIVEKIT_API_SECRET")
ROOM      = os.getenv("ROOM_NAME", "demo-room")

DG_KEY    = need("DEEPGRAM_API_KEY")
EL_KEY    = need("ELEVENLABS_API_KEY")
# MUST be a voice_id (not the name). Rachel legacy ID as fallback:
EL_VOICE  = os.getenv("ELEVENLABS_VOICE_ID") or os.getenv("ELEVEN_VOICE_ID") or "21m00Tcm4TlvDq8ikWAM"

def _agent_token(identity: str) -> str:
    grants = lkapi.VideoGrants(room_join=True, room=ROOM, can_publish=True, can_subscribe=True)
    return (
        lkapi.AccessToken(api_key=LK_KEY, api_secret=LK_SECRET)
        .with_identity(identity)
        .with_grants(grants)
        .with_ttl(datetime.timedelta(hours=1))  # Python SDK expects timedelta
        .to_jwt()
    )

# ---- Proper custom processor: init, call super, and ALWAYS forward frames ----
class EchoModifier(FrameProcessor):
    def __init__(self):
        super().__init__()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # allow system handling
        await super().process_frame(frame, direction)

        try:
            if isinstance(frame, InterimTranscriptionFrame):
                text = (frame.text or "").strip()
                if text:
                    print(f"[STT] partial: {text}")

            elif isinstance(frame, TranscriptionFrame):
                text = (frame.text or "").strip()
                if text:
                    print(f"[STT] FINAL: {text}")
                    # speak the echo on finals
                    await self.push_frame(
                        TTSSpeakFrame(text=f"{text}...got it"),
                        FrameDirection.DOWNSTREAM
                    )
        finally:
            # forward original frame so pipeline continues
            await self.push_frame(frame, direction)

async def main():
    transport = LiveKitTransport(
        url=LK_URL,
        token=_agent_token("echo-agent"),
        room_name=ROOM,
        params=LiveKitParams(audio_in_enabled=True, audio_out_enabled=True),
    )

    # Deepgram streaming STT — emit partials + finals
    stt = DeepgramSTTService(
        api_key=DG_KEY,
        live_options=DGLiveOptions(
            model="nova-3-general",
            interim_results=True,
            vad_events=True,  # ensures utterance-end -> final TranscriptionFrame
        ),
    )

    # ElevenLabs WebSocket TTS (voice_id required)
    tts = ElevenLabsTTSService(
        api_key=EL_KEY,
        voice_id=EL_VOICE,
        model="eleven_turbo_v2_5",
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        EchoModifier(),
        tts,
        transport.output(),
    ])

    params = PipelineParams(
        allow_interruptions=True,
        interruption_strategies=[MinWordsInterruptionStrategy(min_words=1)],
    )
    task = PipelineTask(pipeline, params=params)
    runner = PipelineRunner(handle_sigint=False)

    @transport.event_handler("on_connected")
    async def on_connected(_t):
        print("[Agent] connected — warmup TTS")
        await task.queue_frame(TTSSpeakFrame(text="Agent online. Say something and I will echo it... got it."))

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(_t, participant_id):
        print(f"[Agent] first participant: {participant_id} — hello")
        await task.queue_frame(TTSSpeakFrame(text="Hello! I'm ready. Speak and I will echo you."))

    print(f"🤖 Pipecat agent joining room: {ROOM}")
    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(main())
