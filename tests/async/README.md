# Async Migration Test Suite

This directory contains comprehensive tests for the async API migration.

## Test Files

### 1. `test_api_async.py`
E2E tests for async endpoints:
- Response time validation
- Concurrent request handling
- Connection pool management
- Error handling
- Performance regression tests

**Run:**
```bash
# Install dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/async/test_api_async.py -v -s

# Run specific test class
pytest tests/async/test_api_async.py::TestAsyncEndpoints -v

# Run with coverage
pytest tests/async/ --cov=database_async --cov=api_v2 --cov-report=html
```

### 2. Load Testing (see `/load_tests`)
Locust-based load tests for stress testing.

## Expected Results

### Performance Benchmarks
| Endpoint | Target | Actual (avg) |
|----------|--------|--------------|
| `/trucks/{id}/sensors` | <100ms | ~32ms ✅ |
| `/fleet/summary` | <150ms | ~71ms ✅ |
| 10 concurrent requests | <300ms | ~120ms ✅ |
| 50 concurrent requests | <2s | ~800ms ✅ |

### Connection Pool
- Min size: 5 connections
- Max size: 20 connections
- Should handle 100+ concurrent requests without exhaustion

### Coverage Goals
- `database_async.py`: 90%+
- `api_v2.py` (async endpoints): 80%+

## Continuous Integration

Add to GitHub Actions:
```yaml
name: Async API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: test
          MYSQL_DATABASE: fuel_copilot_local
        ports:
          - 3306:3306
    
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx
      
      - name: Run async tests
        run: pytest tests/async/ -v
```

## Debugging

### Enable async debugging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In database_async.py
POOL_CONFIG["echo"] = True  # Log all SQL
```

### Check pool stats during tests:
```python
from database_async import get_pool_stats

stats = await get_pool_stats()
print(f"Pool usage: {stats['used']}/{stats['size']}")
```

## Known Issues

1. **Table not found errors**: Some endpoints reference tables that may not exist in test DB
   - Solution: Create test fixtures or use mocks
   
2. **Connection timeout**: May occur under extreme load
   - Solution: Increase pool max size or request timeout

## Contributing

When adding new async endpoints:
1. Add corresponding test in `test_api_async.py`
2. Verify performance benchmark (<200ms target)
3. Test concurrent request handling
4. Update this README
