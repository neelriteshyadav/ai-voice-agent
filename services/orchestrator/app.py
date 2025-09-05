import os, asyncio, json, logging, time
from typing import Dict, List
from datetime import timedelta
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
import redis as redis_client
from livekit import api as lkapi
import uvicorn

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
HTTP_PORT = int(os.getenv("ORCH_HTTP_PORT", "8080"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]
LIVEKIT_URL = os.environ["LIVEKIT_URL"]
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "100"))

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics - temporarily disabled to fix startup issues
# TODO: Fix metrics duplication issue
WEBHOOK_REQUESTS = None
AGENT_DISPATCH_TIME = None
ACTIVE_ROOMS = None
DISPATCH_ERRORS = None
ROOM_DURATION = None

# FastAPI app with enhanced configuration
app = FastAPI(
    title="Voice Agent Orchestrator",
    description="Production-grade orchestrator for 100 concurrent voice calls",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Global state
redis = None
room_stats: Dict[str, Dict] = {}  # Track room statistics

@app.on_event("startup")
async def startup():
    """Initialize Redis connection and background tasks"""
    global redis
    redis = redis_client.from_url(REDIS_URL)
    logger.info("Orchestrator started successfully")

    # Start background cleanup task
    asyncio.create_task(cleanup_stale_rooms())

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    if redis:
        redis.close()
    logger.info("Orchestrator shutdown complete")

async def cleanup_stale_rooms():
    """Background task to cleanup stale room statistics"""
    while True:
        try:
            current_time = time.time()
            stale_rooms = []
            
            for room_name, stats in room_stats.items():
                if current_time - stats.get("last_seen", 0) > 3600:  # 1 hour
                    stale_rooms.append(room_name)
            
            for room_name in stale_rooms:
                del room_stats[room_name]
                if ACTIVE_ROOMS:
                    ACTIVE_ROOMS.dec()
                logger.debug(f"Cleaned up stale room: {room_name}")
            
            await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)

@app.get("/health")
async def health_check():
    """Enhanced health check with Redis connectivity"""
    try:
        # Test Redis connection
        redis.ping()
        active_rooms_count = len(room_stats)

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "active_rooms": active_rooms_count,
            "max_concurrent_calls": MAX_CONCURRENT_CALLS,
            "redis_connected": True
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

@app.get("/stats")
async def get_stats():
    """Get current system statistics"""
    try:
        queue_length = redis.llen("rooms")
        active_rooms_count = len(room_stats)
        
        return {
            "active_rooms": active_rooms_count,
            "queue_length": queue_length,
            "max_concurrent_calls": MAX_CONCURRENT_CALLS,
            "room_details": room_stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {e}")

async def dispatch_agent(room: str, participant_identity: str) -> bool:
    """Dispatch an agent to a room with error handling and metrics"""
    dispatch_start = time.time()
    
    try:
        # Check if we're at capacity
        if len(room_stats) >= MAX_CONCURRENT_CALLS:
            logger.warning(f"At capacity ({MAX_CONCURRENT_CALLS}), rejecting room: {room}")
            if DISPATCH_ERRORS:
                DISPATCH_ERRORS.inc()
            return False
        
        # Generate agent token with enhanced grants
        identity = f"agent-{room}"
        token = (lkapi.AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
                .with_identity(identity)
                .with_grants(lkapi.VideoGrants(
                    room_join=True,
                    room=room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True
                ))
                .with_ttl(timedelta(hours=1))
                .to_jwt())
        
        # Prepare agent payload
        payload = {
            "room": room,
            "token": token,
            "identity": identity,
            "participant_identity": participant_identity,
            "timestamp": time.time()
        }
        
        # Dispatch to Redis queue
        redis.lpush("rooms", json.dumps(payload))
        
        # Update room statistics
        room_stats[room] = {
            "start_time": time.time(),
            "last_seen": time.time(),
            "participant_identity": participant_identity,
            "agent_identity": identity
        }
        
        if ACTIVE_ROOMS:
            ACTIVE_ROOMS.inc()
        dispatch_time = (time.time() - dispatch_start) * 1000
        if AGENT_DISPATCH_TIME:
            AGENT_DISPATCH_TIME.observe(dispatch_time)
        
        logger.info(f"Agent dispatched for room: {room}, dispatch_time: {dispatch_time:.2f}ms")
        return True
        
    except Exception as e:
        logger.error(f"Error dispatching agent for room {room}: {e}")
        if DISPATCH_ERRORS:
            DISPATCH_ERRORS.inc()
        return False

@app.post("/webhooks/livekit")
async def livekit_webhook(req: Request, background_tasks: BackgroundTasks):
    """Enhanced LiveKit webhook handler with comprehensive event processing"""
    try:
        body = await req.body()
        event = json.loads(body.decode("utf-8"))
        
        event_type = event.get("event")
        if WEBHOOK_REQUESTS:
            WEBHOOK_REQUESTS.labels(event_type=event_type).inc()
        
        logger.debug(f"Received webhook event: {event_type}")
        
        if event_type == "participant_joined":
            participant = event.get("participant", {})
            room_name = event.get("room", {}).get("name")
            
            if participant.get("kind") == "SIP" and room_name:
                participant_identity = participant.get("identity", "unknown")
                logger.info(f"SIP participant joined room: {room_name}, identity: {participant_identity}")
                
                # Dispatch agent asynchronously
                success = await dispatch_agent(room_name, participant_identity)
                if not success:
                    logger.error(f"Failed to dispatch agent for room: {room_name}")
                    return {"ok": False, "error": "Failed to dispatch agent"}
        
        elif event_type == "participant_disconnected":
            room_name = event.get("room", {}).get("name")
            participant = event.get("participant", {})
            
            if room_name and room_name in room_stats:
                participant_identity = participant.get("identity", "unknown")
                logger.info(f"Participant disconnected from room: {room_name}, identity: {participant_identity}")
                
                # If this was the SIP participant, clean up
                if participant.get("kind") == "SIP":
                    room_duration = time.time() - room_stats[room_name]["start_time"]
                    if ROOM_DURATION:
                        ROOM_DURATION.observe(room_duration)

                    del room_stats[room_name]
                    if ACTIVE_ROOMS:
                        ACTIVE_ROOMS.dec()
                    logger.info(f"Room cleaned up: {room_name}, duration: {room_duration:.2f}s")
        
        elif event_type == "room_finished":
            room_name = event.get("room", {}).get("name")
            if room_name and room_name in room_stats:
                room_duration = time.time() - room_stats[room_name]["start_time"]
                if ROOM_DURATION:
                    ROOM_DURATION.observe(room_duration)

                del room_stats[room_name]
                if ACTIVE_ROOMS:
                    ACTIVE_ROOMS.dec()
                logger.info(f"Room finished: {room_name}, duration: {room_duration:.2f}s")
        
        return {"ok": True, "processed": event_type}
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return {"ok": False, "error": "Invalid JSON"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/manual/dispatch")
async def manual_dispatch(room: str, participant_identity: str = "manual-test"):
    """Manual agent dispatch for testing"""
    success = await dispatch_agent(room, participant_identity)
    if success:
        return {"ok": True, "message": f"Agent dispatched to room: {room}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to dispatch agent")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=HTTP_PORT)
