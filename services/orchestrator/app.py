import os, asyncio, json
from fastapi import FastAPI, Request
import aioredis
from livekit import api as lkapi
import uvicorn

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
HTTP_PORT = int(os.getenv("ORCH_HTTP_PORT", "8080"))

app = FastAPI()
redis = None

@app.on_event("startup")
async def startup():
    global redis
    redis = await aioredis.from_url(REDIS_URL)

@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.post("/webhooks/livekit")
async def livekit_webhook(req: Request):
    body = await req.body()
    try:
        event = json.loads(body.decode("utf-8"))
    except Exception:
        return {"ok": False, "err": "invalid json"}
    etype = event.get("event")
    participant = event.get("participant", {})
    if etype == "participant_joined" and participant.get("kind") == "SIP":
        room = event["room"]["name"]
        identity = f"agent-{room}"
        token = lkapi.AccessToken() \            .with_identity(identity) \            .with_grants(lkapi.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True)) \            .with_ttl(seconds=3600).to_jwt()
        payload = {"room": room, "token": token, "identity": identity}
        await redis.lpush("rooms", json.dumps(payload))
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=HTTP_PORT)
