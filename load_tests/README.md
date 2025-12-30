# Load Testing Guide

Performance testing for async API endpoints using Locust.

## Installation

```bash
pip install locust
```

## Quick Start

1. **Start the backend server:**
```bash
cd /path/to/Fuel-Analytics-Backend
python main.py
```

2. **Run load test:**
```bash
locust -f load_tests/api_load_test.py --host=http://localhost:8000
```

3. **Open Locust UI:**
Visit `http://localhost:8089` in your browser

4. **Configure test:**
   - Number of users: 100 (concurrent users)
   - Spawn rate: 10 (users added per second)
   - Click "Start swarming"

## Test Scenarios

### 1. Normal Load (Baseline)
```bash
locust -f load_tests/api_load_test.py \
    --host=http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 5m \
    --headless
```

**Expected Results:**
- 95th percentile: <200ms
- Median: <100ms
- Failure rate: 0%

### 2. High Load (Peak Traffic)
```bash
locust -f load_tests/api_load_test.py \
    --host=http://localhost:8000 \
    --users 200 \
    --spawn-rate 20 \
    --run-time 10m \
    --headless
```

**Expected Results:**
- 95th percentile: <500ms
- Median: <150ms
- Failure rate: <1%

### 3. Stress Test (Find Breaking Point)
```bash
locust -f load_tests/api_load_test.py \
    --host=http://localhost:8000 \
    --users 500 \
    --spawn-rate 50 \
    --run-time 15m \
    --headless
```

**Goal:** Find max sustainable load before failure rate exceeds 5%

### 4. Spike Test (Sudden Traffic Surge)
```bash
locust -f load_tests/api_load_test.py \
    --host=http://localhost:8000 \
    --users 1000 \
    --spawn-rate 100 \
    --run-time 2m \
    --headless
```

**Goal:** Verify connection pool handles sudden spikes

### 5. Endurance Test (Sustained Load)
```bash
locust -f load_tests/api_load_test.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 60m \
    --headless
```

**Goal:** Detect memory leaks, connection pool exhaustion over time

## Monitoring During Tests

### 1. Database Pool Stats
```bash
# In another terminal, monitor pool usage
watch -n 1 'curl -s http://localhost:8000/health | jq .pool_stats'
```

### 2. System Resources
```bash
# Monitor CPU/Memory
top -pid $(pgrep -f "python main.py")
```

### 3. MySQL Connections
```bash
mysql -uroot -e "SHOW STATUS LIKE 'Threads_connected'"
```

## Interpreting Results

### Response Time Targets
| Percentile | Target | Good | Warning | Critical |
|------------|--------|------|---------|----------|
| 50th (median) | <100ms | <150ms | <300ms | >500ms |
| 95th | <200ms | <300ms | <500ms | >1s |
| 99th | <500ms | <800ms | <2s | >5s |

### Throughput Targets
| Metric | Target | Good | Warning |
|--------|--------|------|---------|
| RPS (req/sec) | >200 | >150 | <100 |
| Concurrent users | >100 | >50 | <25 |
| Failure rate | <1% | <5% | >10% |

### Connection Pool Health
```
Good:
- free: 3-10 (pool not exhausted, not over-provisioned)
- used: 5-15 (steady usage)

Warning:
- free: 0 (exhausted - increase maxsize)
- used: 18-20 (near limit)

Critical:
- free: 0 for >30s (increase pool or reduce load)
- used == maxsize for extended period
```

## Troubleshooting

### High Response Times
1. Check pool exhaustion: `free=0`
   - **Fix:** Increase `maxsize` in `database_async.py`
   
2. Check database CPU
   - **Fix:** Optimize slow queries, add indexes

3. Check Python CPU
   - **Fix:** Add more workers (Gunicorn with multiple processes)

### Connection Errors
1. "Too many connections"
   - **Fix:** Reduce pool size or connection lifetime
   
2. "Connection timeout"
   - **Fix:** Increase pool size or reduce request timeout

### Memory Growth
1. Connection pool leak
   - **Fix:** Ensure proper pool cleanup on shutdown
   
2. Request handler leak
   - **Fix:** Check for unclosed resources in endpoints

## Best Practices

1. **Always run baseline first** - Establish performance baseline
2. **Gradual load increase** - Don't spike immediately to max
3. **Monitor continuously** - Watch pool stats, system resources
4. **Run multiple iterations** - Results should be consistent
5. **Test different endpoints** - Some may be slower than others
6. **Document results** - Keep history for regression tracking

## Integration with CI/CD

```yaml
# GitHub Actions example
- name: Load Test
  run: |
    python main.py &
    sleep 10
    locust -f load_tests/api_load_test.py \
      --host=http://localhost:8000 \
      --users 100 \
      --spawn-rate 10 \
      --run-time 2m \
      --headless \
      --only-summary
```

## Next Steps

After load testing:
1. ✅ Document baseline performance
2. ✅ Set up monitoring/alerts for production
3. ✅ Configure auto-scaling based on load
4. ✅ Implement rate limiting if needed
5. ✅ Plan capacity for expected growth
