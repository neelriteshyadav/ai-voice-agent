# pip install twilio pydub numpy scipy matplotlib
import os, io, csv, numpy as np
from twilio.rest import Client
from pydub import AudioSegment
from scipy.signal import correlate

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
RUN_TAG = os.getenv("RUN_TAG", "loadtest")
OUT_CSV = os.getenv("OUT_CSV", "latency.csv")

def detect_onsets(stereo: AudioSegment, thresh_db=-30.0):
    # returns list of (t_user_start_ms, t_agent_first_ms) pairs
    left = stereo.split_to_mono()[0]  # caller
    right = stereo.split_to_mono()[1] # agent
    step = 10
    wins = []
    def energy_db(seg): return seg.rms if len(seg)>0 else 0

    # naive onset detection: first frame above threshold triggers,
    # response = first agent frame above threshold within 2s window after onset
    pairs = []
    i = 0
    while i < len(left):
        wnd = left[i:i+step]
        if wnd.dBFS > thresh_db:
            t0 = i
            # find agent response
            j = i
            t1 = None
            search_ms = 2000
            while j < min(len(right), i+search_ms):
                if right[j:j+step].dBFS > thresh_db:
                    t1 = j; break
                j += step
            if t1 is not None:
                pairs.append((t0, t1))
                i = j + 500  # skip ahead
            else:
                i += 200
        else:
            i += step
    return pairs

def main():
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    rows = []
    for rec in client.recordings.stream():
        # only dual channel wav/mp3
        uri = f"https://api.twilio.com{rec.uri.replace('.json', '.mp3')}"
        audio_bytes = client.request("GET", uri).content
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        pairs = detect_onsets(audio)
        for (t0, t1) in pairs:
            rows.append({"recording_sid": rec.sid, "rtt_ms": int(t1 - t0)})
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["recording_sid","rtt_ms"])
        writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {OUT_CSV} with {len(rows)} measurements")

if __name__ == "__main__":
    main()
