#!/usr/bin/env python3
"""
Comprehensive Load Testing Script for Voice Agent System
Simulates 100 concurrent calls with latency measurement
"""

import asyncio
import aiohttp
import json
import time
import logging
import argparse
import statistics
from typing import List, Dict, Tuple
from dataclasses import dataclass
import random
import string

@dataclass
class CallResult:
    """Result of a single call simulation"""
    call_id: str
    success: bool
    dispatch_time: float
    total_duration: float
    error_message: str = ""

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    target_calls: int = 100
    ramp_up_seconds: int = 30
    test_duration_minutes: int = 10
    orchestrator_url: str = "http://localhost:8080"
    max_concurrent: int = 100

class VoiceAgentLoadTester:
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[CallResult] = []
        self.active_calls: Dict[str, float] = {}
        self.session: aiohttp.ClientSession = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def generate_call_id(self) -> str:
        """Generate unique call ID"""
        timestamp = str(int(time.time() * 1000))
        random_suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
        return f"load-test-{timestamp}-{random_suffix}"
    
    async def check_system_health(self) -> bool:
        """Check if the system is healthy before starting tests"""
        try:
            async with self.session.get(f"{self.config.orchestrator_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    self.logger.info(f"System health check passed: {health_data}")
                    return True
                else:
                    self.logger.error(f"Health check failed with status: {response.status}")
                    return False
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def get_system_stats(self) -> Dict:
        """Get current system statistics"""
        try:
            async with self.session.get(f"{self.config.orchestrator_url}/stats") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Stats request failed with status: {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def simulate_call(self, call_id: str) -> CallResult:
        """Simulate a single voice call"""
        start_time = time.time()

        try:
            # Step 1: Dispatch agent to room with retry logic for capacity issues
            dispatch_start = time.time()
            max_retries = 5
            retry_delay = 2.0

            for attempt in range(max_retries):
                dispatch_data = {
                    "room": f"call-{call_id}",
                    "participant_identity": f"caller-{call_id}"
                }

                async with self.session.post(
                    f"{self.config.orchestrator_url}/manual/dispatch",
                    params=dispatch_data
                ) as response:
                    dispatch_time = time.time() - dispatch_start

                    if response.status == 200:
                        # Success - break out of retry loop
                        break

                    error_text = await response.text()

                    # Check if this is a capacity-related failure that we should retry
                    if response.status == 500 and "Failed to dispatch agent" in error_text:
                        if attempt < max_retries - 1:  # Don't wait after last attempt
                            self.logger.debug(f"Capacity limit hit for {call_id}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2.0  # Exponential backoff
                            continue

                    # Either non-capacity error or max retries reached
                    return CallResult(
                        call_id=call_id,
                        success=False,
                        dispatch_time=dispatch_time,
                        total_duration=time.time() - start_time,
                        error_message=f"Dispatch failed: {response.status} - {error_text}"
                    )
            
            # Step 2: Simulate call duration (random between 30-180 seconds for realistic load)
            call_duration = random.uniform(30, 180)
            
            # Track active call
            self.active_calls[call_id] = start_time
            
            # Simulate the call duration
            await asyncio.sleep(call_duration)
            
            # Step 3: Call completed successfully
            total_duration = time.time() - start_time
            
            # Remove from active calls
            if call_id in self.active_calls:
                del self.active_calls[call_id]
            
            return CallResult(
                call_id=call_id,
                success=True,
                dispatch_time=dispatch_time,
                total_duration=total_duration
            )
            
        except asyncio.TimeoutError:
            return CallResult(
                call_id=call_id,
                success=False,
                dispatch_time=time.time() - dispatch_start if 'dispatch_start' in locals() else 0,
                total_duration=time.time() - start_time,
                error_message="Timeout"
            )
        except Exception as e:
            return CallResult(
                call_id=call_id,
                success=False,
                dispatch_time=time.time() - dispatch_start if 'dispatch_start' in locals() else 0,
                total_duration=time.time() - start_time,
                error_message=str(e)
            )
        finally:
            # Ensure cleanup
            if call_id in self.active_calls:
                del self.active_calls[call_id]
    
    async def ramp_up_calls(self, semaphore: asyncio.Semaphore) -> List[asyncio.Task]:
        """Gradually ramp up calls over the specified period"""
        tasks = []
        calls_per_second = self.config.target_calls / self.config.ramp_up_seconds
        
        self.logger.info(f"Ramping up {self.config.target_calls} calls over {self.config.ramp_up_seconds} seconds")
        self.logger.info(f"Rate: {calls_per_second:.2f} calls/second")
        
        for i in range(self.config.target_calls):
            call_id = self.generate_call_id()
            
            # Create task with semaphore to limit concurrency
            async def call_with_semaphore(cid):
                async with semaphore:
                    return await self.simulate_call(cid)
            
            task = asyncio.create_task(call_with_semaphore(call_id))
            tasks.append(task)
            
            # Wait between calls for ramp-up
            if i < self.config.target_calls - 1:  # Don't wait after the last call
                wait_time = self.config.ramp_up_seconds / self.config.target_calls
                await asyncio.sleep(wait_time)
                
                # Log progress
                if (i + 1) % 10 == 0:
                    active_count = len(self.active_calls)
                    self.logger.info(f"Dispatched {i + 1}/{self.config.target_calls} calls, {active_count} active")
        
        return tasks
    
    async def monitor_progress(self, tasks: List[asyncio.Task]):
        """Monitor test progress and log statistics"""
        start_time = time.time()
        test_duration = self.config.test_duration_minutes * 60
        
        while time.time() - start_time < test_duration:
            completed_tasks = sum(1 for task in tasks if task.done())
            active_calls = len(self.active_calls)
            
            # Get system stats
            stats = await self.get_system_stats()
            
            self.logger.info(
                f"Progress: {completed_tasks}/{len(tasks)} completed, "
                f"{active_calls} active calls, "
                f"System: {stats.get('active_rooms', 'N/A')} rooms, "
                f"Queue: {stats.get('queue_length', 'N/A')}"
            )
            
            await asyncio.sleep(10)  # Log every 10 seconds
    
    async def run_load_test(self) -> Dict:
        """Run the complete load test"""
        self.logger.info(f"Starting load test with {self.config.target_calls} concurrent calls")
        
        # Check system health
        if not await self.check_system_health():
            raise Exception("System health check failed")
        
        # Create semaphore to limit concurrent calls
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        # Start the test
        test_start = time.time()
        
        # Ramp up calls
        tasks = await self.ramp_up_calls(semaphore)
        
        # Monitor progress
        monitor_task = asyncio.create_task(self.monitor_progress(tasks))
        
        # Wait for all calls to complete or timeout
        try:
            self.logger.info("Waiting for all calls to complete...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Cancel monitoring
            monitor_task.cancel()
            
            # Process results
            for result in results:
                if isinstance(result, CallResult):
                    self.results.append(result)
                elif isinstance(result, Exception):
                    self.logger.error(f"Task failed with exception: {result}")
                    # Create a failed result
                    self.results.append(CallResult(
                        call_id="unknown",
                        success=False,
                        dispatch_time=0,
                        total_duration=0,
                        error_message=str(result)
                    ))
            
        except Exception as e:
            self.logger.error(f"Load test failed: {e}")
            monitor_task.cancel()
            raise
        
        test_duration = time.time() - test_start
        
        # Generate report
        return self.generate_report(test_duration)
    
    def generate_report(self, test_duration: float) -> Dict:
        """Generate comprehensive test report"""
        if not self.results:
            return {"error": "No results to analyze"}
        
        # Basic statistics
        total_calls = len(self.results)
        successful_calls = sum(1 for r in self.results if r.success)
        failed_calls = total_calls - successful_calls
        success_rate = (successful_calls / total_calls) * 100 if total_calls > 0 else 0
        
        # Timing statistics for successful calls
        successful_results = [r for r in self.results if r.success]
        
        if successful_results:
            dispatch_times = [r.dispatch_time * 1000 for r in successful_results]  # Convert to ms
            call_durations = [r.total_duration for r in successful_results]
            
            dispatch_stats = {
                "mean": statistics.mean(dispatch_times),
                "median": statistics.median(dispatch_times),
                "p95": statistics.quantiles(dispatch_times, n=20)[18] if len(dispatch_times) >= 20 else max(dispatch_times),
                "p99": statistics.quantiles(dispatch_times, n=100)[98] if len(dispatch_times) >= 100 else max(dispatch_times),
                "min": min(dispatch_times),
                "max": max(dispatch_times)
            }
            
            duration_stats = {
                "mean": statistics.mean(call_durations),
                "median": statistics.median(call_durations),
                "min": min(call_durations),
                "max": max(call_durations)
            }
        else:
            dispatch_stats = {"error": "No successful calls to analyze"}
            duration_stats = {"error": "No successful calls to analyze"}
        
        # Error analysis
        error_counts = {}
        for result in self.results:
            if not result.success and result.error_message:
                error_type = result.error_message.split(':')[0]  # Get error type
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        # Performance assessment
        latency_target_met = False
        if successful_results and dispatch_stats != {"error": "No successful calls to analyze"}:
            # Check if 95th percentile is under 600ms (our target)
            latency_target_met = dispatch_stats["p95"] < 600
        
        report = {
            "test_summary": {
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": failed_calls,
                "success_rate_percent": round(success_rate, 2),
                "test_duration_seconds": round(test_duration, 2),
                "target_calls": self.config.target_calls,
                "latency_target_met": latency_target_met
            },
            "dispatch_latency_ms": dispatch_stats,
            "call_duration_seconds": duration_stats,
            "error_analysis": error_counts,
            "performance_assessment": {
                "latency_target": "< 600ms (95th percentile)",
                "target_achieved": latency_target_met,
                "concurrent_calls_supported": successful_calls,
                "max_concurrent_target": self.config.target_calls
            }
        }
        
        return report

async def main():
    parser = argparse.ArgumentParser(description="Load test the voice agent system")
    parser.add_argument("--calls", type=int, default=100, help="Number of concurrent calls to simulate")
    parser.add_argument("--ramp-up", type=int, default=30, help="Ramp-up time in seconds")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in minutes")
    parser.add_argument("--url", default="http://localhost:8080", help="Orchestrator URL")
    parser.add_argument("--max-concurrent", type=int, default=100, help="Maximum concurrent calls")
    parser.add_argument("--output", help="Output file for results (JSON)")
    
    args = parser.parse_args()
    
    config = LoadTestConfig(
        target_calls=args.calls,
        ramp_up_seconds=args.ramp_up,
        test_duration_minutes=args.duration,
        orchestrator_url=args.url,
        max_concurrent=args.max_concurrent
    )
    
    async with VoiceAgentLoadTester(config) as tester:
        try:
            report = await tester.run_load_test()
            
            # Print report
            print("\n" + "="*60)
            print("VOICE AGENT LOAD TEST REPORT")
            print("="*60)
            print(json.dumps(report, indent=2))
            
            # Save to file if specified
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(report, f, indent=2)
                print(f"\nReport saved to: {args.output}")
            
            # Exit with appropriate code
            success_rate = report.get("test_summary", {}).get("success_rate_percent", 0)
            latency_target_met = report.get("test_summary", {}).get("latency_target_met", False)
            
            if success_rate >= 95 and latency_target_met:
                print("\n✅ LOAD TEST PASSED - System meets requirements!")
                return 0
            else:
                print(f"\n❌ LOAD TEST FAILED - Success rate: {success_rate}%, Latency target met: {latency_target_met}")
                return 1
                
        except Exception as e:
            print(f"\n❌ LOAD TEST ERROR: {e}")
            return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
