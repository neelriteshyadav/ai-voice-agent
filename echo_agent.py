#!/usr/bin/env python3
"""
LiveKit Echo Agent with Full Audio Processing
Receives audio via webhook, processes with Deepgram, responds with ElevenLabs
"""

import os
import sys
import json
import base64
import hmac
import hashlib
import time
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

# Load environment variables
try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    print("python-dotenv not installed")

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://voice-agent-n8jybxzt.livekit.cloud")
ROOM_NAME = os.getenv("ROOM_NAME", "demo-room")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "APISHb2wKcAvdSA")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "i3wNZXk1X4mfZocgM0YJkXJ8vtNEd8dDkb7f4bHjzrj")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "9f9a12c209719b48aeef06a6f9ee561b47af2a49")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "sk_d94bf9918e4765e81f65b77f7fe78154d6db43d35234de67")

def generate_jwt_token():
    """Generate JWT token for LiveKit authentication"""
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }

    payload = {
        "iss": LIVEKIT_API_KEY,
        "sub": "echo-agent",
        "exp": int(time.time()) + 3600,
        "nbf": int(time.time()),
        "video": {
            "roomJoin": True,
            "room": ROOM_NAME,
            "canPublish": True,
            "canSubscribe": True
        }
    }

    # Base64URL encode header and payload
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')

    # Create signature
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(LIVEKIT_API_SECRET.encode(), message.encode(), hashlib.sha256)
    signature_b64 = base64.urlsafe_b64encode(signature.digest()).decode().rstrip('=')

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def process_with_deepgram(audio_data_b64):
    """Process audio data with Deepgram API"""
    try:
        print("🎤 Processing audio with Deepgram...")

        if not audio_data_b64:
            print("⚠️ No audio data provided, using default transcript")
            return "Hello world"

        # For debugging - save the audio data to a file
        try:
            with open('/tmp/debug_audio.webm', 'wb') as f:
                f.write(audio_data)
            print(f"💾 Saved debug audio file: {len(audio_data)} bytes")
        except Exception as e:
            print(f"⚠️ Could not save debug audio: {e}")

        # Decode base64 audio data
        try:
            audio_data = base64.b64decode(audio_data_b64)
            print(f"📦 Decoded audio data: {len(audio_data)} bytes")
        except Exception as e:
            print(f"❌ Failed to decode base64 audio: {e}")
            return "Sorry, I couldn't understand that."

        # First try sending audio directly to Deepgram (WebM or MP3)
        print(f"🎵 Processing audio: {len(audio_data)} bytes")

        # Save the raw audio file for inspection
        try:
            debug_file = '/Users/neelyadav/Downloads/voice-agent-100calls/received_audio.raw'
            with open(debug_file, 'wb') as f:
                f.write(audio_data)
            print(f"💾 Saved raw audio file: {len(audio_data)} bytes to {debug_file}")
        except Exception as e:
            print(f"⚠️ Could not save audio file: {e}")
            # Try current directory
            try:
                with open('received_audio.raw', 'wb') as f:
                    f.write(audio_data)
                print(f"💾 Saved raw audio file to current directory: {len(audio_data)} bytes")
            except Exception as e2:
                print(f"⚠️ Could not save to current directory either: {e2}")

        try:
            with open('agent_debug.log', 'a') as f:
                f.write(f"🎵 Processing audio: {len(audio_data)} bytes\n")
        except:
            pass  # Ignore debug log failures

        # Try WebM first, if it fails, we can add conversion as fallback
        converted_audio = None
        try:
            from pydub import AudioSegment
            import io

            print(f"🎵 Attempting WebM to WAV conversion for fallback")
            with open('/tmp/agent_debug.log', 'a') as f:
                f.write("🎵 Attempting WebM to WAV conversion for fallback\n")

            # Load WebM audio
            print(f"🎵 Loading audio data: {len(audio_data)} bytes")
            with open('/tmp/agent_debug.log', 'a') as f:
                f.write(f"🎵 Loading audio data: {len(audio_data)} bytes\n")

            webm_audio = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
            print(f"🎵 Loaded WebM audio: {len(webm_audio)} ms duration")
            with open('/tmp/agent_debug.log', 'a') as f:
                f.write(f"🎵 Loaded WebM audio: {len(webm_audio)} ms duration\n")

            # Convert to WAV
            wav_buffer = io.BytesIO()
            webm_audio.export(wav_buffer, format="wav")
            converted_audio = wav_buffer.getvalue()

            print(f"🔄 Converted WebM to WAV: {len(converted_audio)} bytes")
            with open('/tmp/agent_debug.log', 'a') as f:
                f.write(f"🔄 Converted WebM to WAV: {len(converted_audio)} bytes\n")
        except Exception as e:
            print(f"⚠️ Failed to convert audio format: {e}")
            import traceback
            print(f"⚠️ Full traceback: {traceback.format_exc()}")
            with open('/tmp/agent_debug.log', 'a') as f:
                f.write(f"⚠️ Failed to convert audio format: {e}\n")
                f.write(f"⚠️ Full traceback: {traceback.format_exc()}\n")
            # Continue with original WebM format if conversion fails

        # Deepgram API endpoint
        url = "https://api.deepgram.com/v1/listen"

        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "audio/webm"  # Default to webm, but will be updated if MP3
        }

        # Try WebM first
        print(f"🎯 Trying WebM format first...")
        with open('/tmp/agent_debug.log', 'a') as f:
            f.write("🎯 Trying WebM format first...\n")

        response = requests.post(url, headers=headers, data=audio_data, params={
            "model": "nova-2",
            "language": "en",
            "punctuate": "true",
            "smart_format": "true",
            "detect_language": "true"
        })

        print(f"🔍 WebM response status: {response.status_code}")
        with open('/tmp/agent_debug.log', 'a') as f:
            f.write(f"🔍 WebM response status: {response.status_code}\n")

        # If WebM fails and we have converted audio, try WAV
        if response.status_code != 200 and converted_audio:
            print(f"🔄 WebM failed, trying WAV format...")
            headers["Content-Type"] = "audio/wav"
            response = requests.post(url, headers=headers, data=converted_audio, params={
                "model": "nova-2",
                "language": "en",
                "punctuate": "true",
                "smart_format": "true",
                "detect_language": "true"
            })
            print(f"🔍 WAV response status: {response.status_code}")

        print(f"🔍 Final response headers: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print(f"🔍 Deepgram raw response: {result}")

            transcript = result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")

            if transcript:
                print(f"📝 Transcribed: {transcript}")
                return transcript.strip()
            else:
                print("⚠️ No transcript found in Deepgram response")
                print(f"⚠️ Full response: {result}")
                return "Sorry, I couldn't understand that."
        else:
            print(f"❌ Deepgram API error: {response.status_code}")
            print(f"❌ Response text: {response.text}")
            return "Sorry, I couldn't understand that."

    except Exception as e:
        print(f"❌ Deepgram processing failed: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return "Sorry, I couldn't understand that."

def generate_with_elevenlabs(text):
    """Generate speech with ElevenLabs API"""
    try:
        print(f"🔊 Generating speech for: {text}")

        # ElevenLabs API endpoint
        url = f"https://api.elevenlabs.io/v1/text-to-speech/XW70ikSsadUbinwLMZ5w"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }

        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            print(f"✅ ElevenLabs audio generated successfully: {len(response.content)} bytes")
            return response.content  # Return audio data
        else:
            print(f"❌ ElevenLabs API error: {response.status_code}")
            print(f"Response text: {response.text}")
            return None

    except Exception as e:
        print(f"❌ ElevenLabs generation failed: {e}")
        return None

def create_flask_app():
    """Create Flask app with webhook endpoints"""
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "livekit": "configured",
                "deepgram": "ready" if DEEPGRAM_API_KEY else "missing",
                "elevenlabs": "ready" if ELEVENLABS_API_KEY else "missing"
            }
        })

    @app.route('/webhook/audio', methods=['POST'])
    def handle_audio():
        """Handle incoming audio data from LiveKit"""
        try:
            print("🎤 Received audio webhook")

            # Get the audio data from the request
            data = request.get_json()
            audio_data_b64 = data.get('audio_data', '')

            if audio_data_b64:
                print(f"📦 Received audio data: {len(audio_data_b64)} characters")

                # Step 1: Process with Deepgram (simulated for now)
                transcript = process_with_deepgram(audio_data_b64)
            else:
                # Fallback to simulation if no audio data
                print("⚠️ No audio data received, using simulation")
                transcript = process_with_deepgram(None)

            # Step 2: Generate echo response with more personality
            responses = [
                f"{transcript}...got it!",
                f"I heard: {transcript}. Cool!",
                f"You said: {transcript}. Understood!",
                f"Message received: {transcript}. Thanks!",
                f"Processing: {transcript}...confirmed!"
            ]
            import random
            response_text = random.choice(responses)
            print(f"🤖 Response: {response_text}")

            # Step 3: Generate audio with ElevenLabs
            audio_data = generate_with_elevenlabs(response_text)
            print(f"🎵 Audio data from ElevenLabs: {audio_data is not None}, size: {len(audio_data) if audio_data else 0}")

            if audio_data:
                # Convert audio data to base64 for client playback
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                print(f"📤 Audio response ready to send to client: {len(audio_data)} bytes -> {len(audio_b64)} b64 chars")

                # For debugging - temporarily disable large audio response
                return jsonify({
                    "status": "processed",
                    "transcript": transcript,
                    "response": response_text,
                    "audio_size": len(audio_data),
                    "audio_data": "",  # Temporarily empty to test
                    "timestamp": datetime.now().isoformat()
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "message": "Audio generation failed",
                    "timestamp": datetime.now().isoformat()
                }), 500

        except Exception as e:
            print(f"❌ Webhook processing error: {e}")
            return jsonify({
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500

    @app.route('/test/echo', methods=['POST'])
    def test_echo():
        """Test endpoint for manual testing"""
        try:
            data = request.get_json()
            text = data.get('text', 'Hello world')

            print(f"🧪 Test echo for: {text}")

            # Process the text with varied responses
            responses = [
                f"{text}...got it!",
                f"I heard: {text}. Cool!",
                f"You said: {text}. Understood!",
                f"Message received: {text}. Thanks!",
                f"Processing: {text}...confirmed!"
            ]
            import random
            response_text = random.choice(responses)

            # Generate audio
            audio_data = generate_with_elevenlabs(response_text)

            return jsonify({
                "original": text,
                "response": response_text,
                "audio_generated": audio_data is not None,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app

def main():
    """Main function"""
    print("🎤 LiveKit Echo Agent with Audio Processing")
    print("=" * 60)

    print("🔧 Configuration:")
    print(f"   LiveKit URL: {LIVEKIT_URL}")
    print(f"   Room: {ROOM_NAME}")
    print(f"   Deepgram: {'✅' if DEEPGRAM_API_KEY else '❌'}")
    print(f"   ElevenLabs: {'✅' if ELEVENLABS_API_KEY else '❌'}")
    print()

    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        print("❌ Missing LiveKit API credentials!")
        return

    # Generate test token
    try:
        token = generate_jwt_token()
        print("✅ JWT Token generated successfully!")
        print(f"Token length: {len(token)}")
        print()

    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        return

    # Start Flask app
    print("🌐 Starting webhook server...")
    print("📡 Available endpoints:")
    print("   GET  /health          - Health check")
    print("   POST /webhook/audio   - Audio processing webhook")
    print("   POST /test/echo       - Test echo endpoint")
    print()

    app = create_flask_app()
    print("🎉 Agent is ready! Listening on port 5000")
    print("📝 To test: curl -X POST http://localhost:5000/test/echo -H 'Content-Type: application/json' -d '{\"text\":\"Hello\"}'")

    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == "__main__":
    main()
