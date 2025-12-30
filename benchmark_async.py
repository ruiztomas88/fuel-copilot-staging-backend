"""
Performance Benchmark Script
=============================

Tests async migration performance improvements.

Author: Fuel Copilot Team
Date: December 26, 2025
"""

import asyncio
import time
from typing import List

import httpx


async def fetch_endpoint(url: str, session: httpx.AsyncClient) -> float:
    """Fetch endpoint and return response time in ms"""
    start = time.time()
    response = await session.get(url)
    elapsed = (time.time() - start) * 1000
    return elapsed


async def benchmark_endpoint(url: str, num_requests: int = 50, concurrency: int = 10):
    """
    Benchmark endpoint with concurrent requests.

    Args:
        url: Endpoint URL to test
        num_requests: Total number of requests
        concurrency: Number of concurrent requests
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking: {url}")
    print(f"Requests: {num_requests}, Concurrency: {concurrency}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(timeout=30.0) as session:
        tasks: List = []

        for i in range(num_requests):
            tasks.append(fetch_endpoint(url, session))

            # Execute in batches of concurrency
            if len(tasks) >= concurrency:
                response_times = await asyncio.gather(*tasks)
                tasks = []

        # Execute remaining tasks
        if tasks:
            response_times = await asyncio.gather(*tasks)

    # Calculate statistics
    all_times = [t for t in response_times if t is not None]
    avg_time = sum(all_times) / len(all_times)
    min_time = min(all_times)
    max_time = max(all_times)
    p95_time = sorted(all_times)[int(len(all_times) * 0.95)]

    print(f"✅ Results:")
    print(f"   Average: {avg_time:.2f} ms")
    print(f"   Min:     {min_time:.2f} ms")
    print(f"   Max:     {max_time:.2f} ms")
    print(f"   P95:     {p95_time:.2f} ms")
    print(f"   Requests/sec: {1000 / avg_time * concurrency:.2f}")

    return {
        "avg": avg_time,
        "min": min_time,
        "max": max_time,
        "p95": p95_time,
        "rps": 1000 / avg_time * concurrency,
    }


async def main():
    """Run performance benchmarks"""
    base_url = "http://localhost:8001"

    endpoints = [
        "/fuelAnalytics/api/fleet",
        "/fuelAnalytics/api/trucks",
        "/fuelAnalytics/api/status",
    ]

    results = {}

    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            result = await benchmark_endpoint(url, num_requests=50, concurrency=10)
            results[endpoint] = result
        except Exception as e:
            print(f"❌ Error testing {endpoint}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print("📊 PERFORMANCE SUMMARY")
    print(f"{'='*60}\n")

    for endpoint, stats in results.items():
        print(f"{endpoint}:")
        print(f"  {stats['avg']:.2f} ms avg, {stats['rps']:.2f} req/s")


if __name__ == "__main__":
    asyncio.run(main())
