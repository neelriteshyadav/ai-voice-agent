# token_server.py
#!/usr/bin/env python3
import os, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from livekit import api as lkapi

load_dotenv()

app = Flask(__name__)
CORS(app)

def need(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

LIVEKIT_URL  = need("LIVEKIT_URL")   # e.g. wss://<project>.livekit.cloud  or  ws://localhost:7880
API_KEY      = need("LIVEKIT_API_KEY")
API_SECRET   = need("LIVEKIT_API_SECRET")
DEFAULT_ROOM = os.getenv("ROOM_NAME", "demo-room")

@app.get("/token")
def token():
    try:
        room = request.args.get("room", DEFAULT_ROOM)
        identity = request.args.get("identity", "user")
        grants = lkapi.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True)
        jwt = (lkapi.AccessToken(api_key=API_KEY, api_secret=API_SECRET)
               .with_identity(identity)
               .with_grants(grants)
               .with_ttl(datetime.timedelta(hours=1))  # ✅ Python SDK expects timedelta
               .to_jwt())
        return jsonify({"url": LIVEKIT_URL, "token": jwt, "room": room}), 200
    except Exception as e:
        app.logger.exception("token error")
        return jsonify({"error": str(e)}), 500

@app.get("/healthz")
def healthz():
    return {"ok": True, "url": LIVEKIT_URL}, 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8787, debug=False)
