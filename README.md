# LiveKit × Pipecat – Minimal Duplex Voice Demo

A tiny project I built to prove that **LiveKit** can route realtime media while **Pipecat** runs the agent. The agent echoes what I say with a suffix (“…got it”), supports barge-in, and the browser auto-logs **mouth→ear** latency.

Mic → LiveKit → Pipecat (STT → logic → TTS) → LiveKit → Speaker

---

## What’s in the repo

- `spawn_agent.py` — Pipecat agent that joins a LiveKit room (Deepgram STT → “…got it” → ElevenLabs TTS).
- `client.html` + `latency_probe.js` — simple LiveKit web client with **automatic** mouth→ear latency logging.
- `token_server.py` — tiny HTTP server that mints LiveKit tokens.
- `docker-compose.yml` — optional local LiveKit node (I often use LiveKit Cloud instead).
- `run_demo.sh`, `setup_livekit.sh`, `requirements-agent.txt` — helpers.

---

## Requirements

- **Python 3.11+**
- Static file serving for the client (e.g., `python -m http.server`)
- Accounts/keys:
  - LiveKit (Cloud or local)
  - Deepgram — `DEEPGRAM_API_KEY`
  - ElevenLabs — `ELEVENLABS_API_KEY` (and a **voice id**)

---

## Setup

Create `.env` in the project root:

```bash
LIVEKIT_URL=wss://<your-project>.livekit.cloud   # or ws://localhost:7880 for local
LIVEKIT_API_KEY=lk_...
LIVEKIT_API_SECRET=...
ROOM_NAME=demo-room

DEEPGRAM_API_KEY=dg_...

ELEVENLABS_API_KEY=el_...
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM          # example; use your real voice_id
# optional: low-latency TTS model
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
```
Install & run the agent:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-agent.txt
python spawn_agent.py

Run the token server (separate shell):
source .venv/bin/activate
python token_server.py   # http://127.0.0.1:8787

Serve the client:
python -m http.server 8000
# open http://localhost:8000/client.html
# Click: Connect → Enable Audio
