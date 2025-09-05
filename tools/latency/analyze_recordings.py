# pip install twilio pydub numpy scipy matplotlib pandas prometheus-client
import os, io, csv, numpy as np, json, time, logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from twilio.rest import Client
from pydub import AudioSegment
from scipy.signal import correlate
import pandas as pd
import matplotlib.pyplot as plt
from prometheus_client import CollectorRegistry, Histogram, Counter, Gauge, push_to_gateway

# Configuration
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
RUN_TAG = os.getenv("RUN_TAG", "loadtest")
OUT_CSV = os.getenv("OUT_CSV", "latency.csv")
PROMETHEUS_GATEWAY = os.getenv("PROMETHEUS_GATEWAY", "http://localhost:9091")
ANALYSIS_WINDOW_HOURS = int(os.getenv("ANALYSIS_WINDOW_HOURS", "24"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class LatencyMeasurement:
    """Single latency measurement from audio analysis"""
    recording_sid: str
    call_sid: str
    timestamp: datetime
    user_onset_ms: int
    agent_response_ms: int
    rtt_ms: int
    confidence_score: float
    audio_quality_score: float

class EnhancedAudioAnalyzer:
    """Enhanced audio analyzer with improved onset detection and quality metrics"""
    
    def __init__(self, thresh_db=-30.0, min_speech_duration=100, max_response_window=3000):
        self.thresh_db = thresh_db
        self.min_speech_duration = min_speech_duration
        self.max_response_window = max_response_window
    
    def calculate_audio_quality_score(self, segment: AudioSegment) -> float:
        """Calculate audio quality score based on SNR and other factors"""
        try:
            # Simple quality metric based on RMS and dynamic range
            rms = segment.rms
            max_amplitude = segment.max
            
            if max_amplitude == 0:
                return 0.0
            
            # Dynamic range ratio
            dynamic_range = max_amplitude / (rms + 1)
            
            # Normalize to 0-1 scale
            quality_score = min(1.0, dynamic_range / 1000.0)
            return quality_score
        except:
            return 0.5  # Default moderate quality
    
    def detect_speech_onsets(self, stereo: AudioSegment) -> List[Tuple[int, int, float, float]]:
        """
        Enhanced onset detection with confidence scoring
        Returns: [(user_onset_ms, agent_response_ms, confidence, quality_score), ...]
        """
        if stereo.channels != 2:
            logger.warning("Audio is not stereo, attempting to process anyway")
            return []
        
        left = stereo.split_to_mono()[0]   # caller
        right = stereo.split_to_mono()[1]  # agent
        
        step = 10  # 10ms windows
        pairs = []
        i = 0
        
        while i < len(left):
            # Check for user speech onset
            user_window = left[i:i+step]
            
            if len(user_window) == 0:
                break
                
            if user_window.dBFS > self.thresh_db:
                # Verify this is sustained speech
                sustained_duration = 0
                j = i
                while j < len(left) and j < i + self.min_speech_duration:
                    test_window = left[j:j+step]
                    if len(test_window) > 0 and test_window.dBFS > self.thresh_db:
                        sustained_duration += step
                    j += step
                
                if sustained_duration >= self.min_speech_duration:
                    user_onset = i
                    
                    # Look for agent response within window
                    search_start = i + self.min_speech_duration  # Don't look too early
                    search_end = min(len(right), i + self.max_response_window)
                    
                    agent_response = None
                    best_confidence = 0.0
                    
                    for k in range(search_start, search_end, step):
                        agent_window = right[k:k+step]
                        if len(agent_window) > 0 and agent_window.dBFS > self.thresh_db:
                            # Check for sustained agent speech
                            agent_sustained = 0
                            for l in range(k, min(len(right), k + self.min_speech_duration), step):
                                agent_test = right[l:l+step]
                                if len(agent_test) > 0 and agent_test.dBFS > self.thresh_db:
                                    agent_sustained += step
                            
                            if agent_sustained >= self.min_speech_duration:
                                # Calculate confidence based on signal strength
                                confidence = min(1.0, (agent_window.dBFS - self.thresh_db) / -self.thresh_db)
                                if confidence > best_confidence:
                                    best_confidence = confidence
                                    agent_response = k
                                break
                    
                    if agent_response is not None:
                        # Calculate quality scores
                        user_segment = left[user_onset:user_onset + 1000]  # 1 second sample
                        agent_segment = right[agent_response:agent_response + 1000]
                        
                        user_quality = self.calculate_audio_quality_score(user_segment)
                        agent_quality = self.calculate_audio_quality_score(agent_segment)
                        avg_quality = (user_quality + agent_quality) / 2
                        
                        pairs.append((user_onset, agent_response, best_confidence, avg_quality))
                        
                        # Skip ahead to avoid overlapping detections
                        i = agent_response + 1000
                    else:
                        i += 500  # Skip ahead if no response found
                else:
                    i += step
            else:
                i += step
        
        return pairs

def detect_onsets(stereo: AudioSegment, thresh_db=-30.0):
    """Legacy function for backwards compatibility"""
    analyzer = EnhancedAudioAnalyzer(thresh_db=thresh_db)
    enhanced_pairs = analyzer.detect_speech_onsets(stereo)
    # Convert to legacy format
    return [(user_onset, agent_response) for user_onset, agent_response, _, _ in enhanced_pairs]

class LatencyAnalysisEngine:
    """Enhanced latency analysis with real-time metrics and reporting"""
    
    def __init__(self, twilio_client: Client):
        self.client = twilio_client
        self.analyzer = EnhancedAudioAnalyzer()
        self.measurements: List[LatencyMeasurement] = []
        
        # Prometheus metrics
        self.registry = CollectorRegistry()
        self.latency_histogram = Histogram(
            'voice_agent_end_to_end_latency_ms',
            'End-to-end latency from user speech to agent response',
            buckets=[50, 100, 200, 300, 400, 500, 600, 800, 1000, 1500, 2000],
            registry=self.registry
        )
        self.quality_gauge = Gauge(
            'voice_agent_audio_quality_score',
            'Audio quality score (0-1)',
            registry=self.registry
        )
        self.analysis_counter = Counter(
            'voice_agent_recordings_analyzed_total',
            'Total recordings analyzed',
            registry=self.registry
        )
    
    def get_recent_recordings(self, hours_back: int = 24) -> List:
        """Get recordings from the specified time window"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        recordings = []
        try:
            for recording in self.client.recordings.stream(
                date_created_after=cutoff_time,
                limit=1000  # Reasonable limit
            ):
                recordings.append(recording)
        except Exception as e:
            logger.error(f"Error fetching recordings: {e}")
        
        logger.info(f"Found {len(recordings)} recordings in the last {hours_back} hours")
        return recordings
    
    def analyze_recording(self, recording) -> List[LatencyMeasurement]:
        """Analyze a single recording for latency measurements"""
        measurements = []
        
        try:
            # Download audio
            uri = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
            audio_response = self.client.request("GET", uri)
            
            if audio_response.status_code != 200:
                logger.warning(f"Failed to download recording {recording.sid}")
                return measurements
            
            # Process audio
            audio = AudioSegment.from_file(io.BytesIO(audio_response.content), format="mp3")
            
            # Enhanced onset detection
            pairs = self.analyzer.detect_speech_onsets(audio)
            
            for user_onset, agent_response, confidence, quality in pairs:
                rtt_ms = int(agent_response - user_onset)
                
                # Filter out unrealistic measurements
                if 50 <= rtt_ms <= 5000 and confidence > 0.3:
                    measurement = LatencyMeasurement(
                        recording_sid=recording.sid,
                        call_sid=getattr(recording, 'call_sid', 'unknown'),
                        timestamp=recording.date_created,
                        user_onset_ms=user_onset,
                        agent_response_ms=agent_response,
                        rtt_ms=rtt_ms,
                        confidence_score=confidence,
                        audio_quality_score=quality
                    )
                    measurements.append(measurement)
                    
                    # Update metrics
                    self.latency_histogram.observe(rtt_ms)
                    self.quality_gauge.set(quality)
            
            self.analysis_counter.inc()
            
        except Exception as e:
            logger.error(f"Error analyzing recording {recording.sid}: {e}")
        
        return measurements
    
    def run_analysis(self, hours_back: int = 24) -> Dict:
        """Run complete analysis and generate report"""
        logger.info("Starting latency analysis...")
        
        # Get recent recordings
        recordings = self.get_recent_recordings(hours_back)
        
        if not recordings:
            logger.warning("No recordings found to analyze")
            return {"error": "No recordings found"}
        
        # Analyze each recording
        all_measurements = []
        for i, recording in enumerate(recordings):
            if i % 10 == 0:
                logger.info(f"Analyzing recording {i+1}/{len(recordings)}")
            
            measurements = self.analyze_recording(recording)
            all_measurements.extend(measurements)
        
        self.measurements = all_measurements
        
        # Generate report
        report = self.generate_report()
        
        # Push metrics to Prometheus (if gateway available)
        try:
            if PROMETHEUS_GATEWAY and PROMETHEUS_GATEWAY != "http://localhost:9091":
                push_to_gateway(PROMETHEUS_GATEWAY, job='latency_analysis', registry=self.registry)
        except Exception as e:
            logger.warning(f"Failed to push metrics to Prometheus: {e}")
        
        return report
    
    def generate_report(self) -> Dict:
        """Generate comprehensive latency analysis report"""
        if not self.measurements:
            return {"error": "No measurements available"}
        
        # Convert to DataFrame for easier analysis
        data = []
        for m in self.measurements:
            data.append({
                'recording_sid': m.recording_sid,
                'call_sid': m.call_sid,
                'timestamp': m.timestamp,
                'rtt_ms': m.rtt_ms,
                'confidence': m.confidence_score,
                'quality': m.audio_quality_score
            })
        
        df = pd.DataFrame(data)
        
        # Basic statistics
        rtt_stats = df['rtt_ms'].describe(percentiles=[0.5, 0.95, 0.99])
        
        # Quality analysis
        high_quality_mask = df['quality'] > 0.7
        high_confidence_mask = df['confidence'] > 0.7
        
        high_quality_rtt = df[high_quality_mask]['rtt_ms'].describe(percentiles=[0.5, 0.95, 0.99]) if high_quality_mask.any() else None
        high_confidence_rtt = df[high_confidence_mask]['rtt_ms'].describe(percentiles=[0.5, 0.95, 0.99]) if high_confidence_mask.any() else None
        
        # Performance assessment
        target_met = rtt_stats['95%'] < 600 if '95%' in rtt_stats else False
        
        # Time-based analysis
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        hourly_stats = df.groupby('hour')['rtt_ms'].agg(['mean', 'count']).to_dict()
        
        report = {
            "analysis_summary": {
                "total_measurements": len(self.measurements),
                "total_recordings": len(df['recording_sid'].unique()),
                "analysis_period_hours": ANALYSIS_WINDOW_HOURS,
                "timestamp": datetime.now().isoformat()
            },
            "latency_statistics": {
                "all_measurements": {
                    "count": int(rtt_stats['count']),
                    "mean_ms": round(rtt_stats['mean'], 1),
                    "median_ms": round(rtt_stats['50%'], 1),
                    "p95_ms": round(rtt_stats['95%'], 1),
                    "p99_ms": round(rtt_stats['99%'], 1),
                    "min_ms": round(rtt_stats['min'], 1),
                    "max_ms": round(rtt_stats['max'], 1)
                },
                "high_quality_only": high_quality_rtt.to_dict() if high_quality_rtt is not None else None,
                "high_confidence_only": high_confidence_rtt.to_dict() if high_confidence_rtt is not None else None
            },
            "quality_metrics": {
                "average_audio_quality": round(df['quality'].mean(), 3),
                "average_confidence": round(df['confidence'].mean(), 3),
                "high_quality_percentage": round((high_quality_mask.sum() / len(df)) * 100, 1),
                "high_confidence_percentage": round((high_confidence_mask.sum() / len(df)) * 100, 1)
            },
            "performance_assessment": {
                "latency_target": "< 600ms (95th percentile)",
                "target_achieved": target_met,
                "p95_latency_ms": round(rtt_stats['95%'], 1) if '95%' in rtt_stats else None,
                "grade": "PASS" if target_met else "FAIL"
            },
            "temporal_analysis": {
                "hourly_patterns": hourly_stats
            }
        }
        
        return report
    
    def save_results(self, filename: str = None):
        """Save detailed results to CSV"""
        if not self.measurements:
            logger.warning("No measurements to save")
            return
        
        filename = filename or OUT_CSV
        
        with open(filename, 'w', newline='') as f:
            fieldnames = [
                'recording_sid', 'call_sid', 'timestamp', 
                'user_onset_ms', 'agent_response_ms', 'rtt_ms',
                'confidence_score', 'audio_quality_score'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for m in self.measurements:
                writer.writerow({
                    'recording_sid': m.recording_sid,
                    'call_sid': m.call_sid,
                    'timestamp': m.timestamp.isoformat(),
                    'user_onset_ms': m.user_onset_ms,
                    'agent_response_ms': m.agent_response_ms,
                    'rtt_ms': m.rtt_ms,
                    'confidence_score': m.confidence_score,
                    'audio_quality_score': m.audio_quality_score
                })
        
        logger.info(f"Saved {len(self.measurements)} measurements to {filename}")
    
    def generate_plots(self, output_dir: str = "."):
        """Generate visualization plots"""
        if not self.measurements:
            logger.warning("No measurements to plot")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'rtt_ms': m.rtt_ms,
                'confidence': m.confidence_score,
                'quality': m.audio_quality_score,
                'timestamp': m.timestamp
            }
            for m in self.measurements
        ])
        
        # Latency distribution
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 2, 1)
        plt.hist(df['rtt_ms'], bins=50, alpha=0.7, edgecolor='black')
        plt.axvline(600, color='red', linestyle='--', label='Target (600ms)')
        plt.axvline(df['rtt_ms'].quantile(0.95), color='orange', linestyle='--', label='95th percentile')
        plt.xlabel('Latency (ms)')
        plt.ylabel('Frequency')
        plt.title('Latency Distribution')
        plt.legend()
        
        # Quality vs Latency
        plt.subplot(2, 2, 2)
        plt.scatter(df['quality'], df['rtt_ms'], alpha=0.6)
        plt.xlabel('Audio Quality Score')
        plt.ylabel('Latency (ms)')
        plt.title('Quality vs Latency')
        
        # Confidence vs Latency
        plt.subplot(2, 2, 3)
        plt.scatter(df['confidence'], df['rtt_ms'], alpha=0.6)
        plt.xlabel('Confidence Score')
        plt.ylabel('Latency (ms)')
        plt.title('Confidence vs Latency')
        
        # Time series
        plt.subplot(2, 2, 4)
        df_sorted = df.sort_values('timestamp')
        plt.plot(df_sorted['timestamp'], df_sorted['rtt_ms'], alpha=0.7)
        plt.axhline(600, color='red', linestyle='--', label='Target')
        plt.xlabel('Time')
        plt.ylabel('Latency (ms)')
        plt.title('Latency Over Time')
        plt.xticks(rotation=45)
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/latency_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Saved plots to {output_dir}/latency_analysis.png")

def main():
    """Main function with enhanced analysis"""
    if not ACCOUNT_SID or not AUTH_TOKEN:
        logger.error("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables are required")
        return
    
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    engine = LatencyAnalysisEngine(client)
    
    # Run analysis
    report = engine.run_analysis(hours_back=ANALYSIS_WINDOW_HOURS)
    
    # Print report
    print("\n" + "="*60)
    print("VOICE AGENT LATENCY ANALYSIS REPORT")
    print("="*60)
    print(json.dumps(report, indent=2))
    
    # Save results
    engine.save_results()
    
    # Generate plots
    try:
        engine.generate_plots()
    except Exception as e:
        logger.warning(f"Failed to generate plots: {e}")
    
    # Print summary
    if 'latency_statistics' in report:
        stats = report['latency_statistics']['all_measurements']
        assessment = report['performance_assessment']
        
        print(f"\n📊 SUMMARY:")
        print(f"   Measurements: {stats['count']}")
        print(f"   Mean latency: {stats['mean_ms']}ms")
        print(f"   95th percentile: {stats['p95_ms']}ms")
        print(f"   Target achieved: {assessment['target_achieved']}")
        print(f"   Grade: {assessment['grade']}")

# Legacy main function for backwards compatibility
def legacy_main():
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
