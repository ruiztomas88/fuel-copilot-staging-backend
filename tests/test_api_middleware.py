"""
Tests for API Middleware Module
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_middleware import (
    RateLimiter,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    ErrorHandlingMiddleware,
    TimingMiddleware,
    setup_middleware,
)


class MockRequest:
    """Mock FastAPI Request object"""

    def __init__(self, client_ip: str = "127.0.0.1", headers: dict = None):
        self.client = Mock()
        self.client.host = client_ip
        self.headers = headers or {}
        self.url = Mock()
        self.url.path = "/api/test"
        self.method = "GET"
        # 🆕 v3.12.21: Add state mock for role-based rate limiting
        self.state = Mock()
        self.state.user = None


class TestRateLimiter:
    """Tests for RateLimiter class"""

    @pytest.fixture
    def limiter(self, enable_rate_limiting):
        """Rate limiter fixture - requires rate limiting to be enabled."""
        # 🆕 v3.12.21: Use anonymous limits (30 rpm) for testing
        return RateLimiter(
            requests_per_minute=30,  # Matches anonymous role
            requests_per_second=5,  # Higher to avoid burst limit in tests
        )

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self, limiter):
        """Should allow requests under the limit"""
        request = MockRequest()

        # Should not raise (with small delay to avoid burst)
        for _ in range(3):
            await limiter.check(request)
            await asyncio.sleep(0.3)  # Avoid burst limit

    @pytest.mark.asyncio
    async def test_blocks_requests_over_rpm_limit(self, limiter):
        """Should block requests over per-minute limit"""
        from fastapi import HTTPException

        request = MockRequest()

        # Make 30 requests (at anonymous limit) with delays
        for _ in range(30):
            await limiter.check(request)
            await asyncio.sleep(0.25)  # Avoid burst limit (5 rps = 0.2s min)

        # 31st request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check(request)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_blocks_burst_requests(self, limiter):
        """Should block burst requests (per-second limit)"""
        from fastapi import HTTPException

        # Using default limiter - anonymous role has 5 rps burst limit
        request = MockRequest()

        # Make 5 rapid requests (anonymous burst limit)
        for _ in range(5):
            await limiter.check(request, role="anonymous")

        # 6th rapid request should be blocked by burst limit
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check(request, role="anonymous")

        assert exc_info.value.status_code == 429
        assert "per second" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_different_clients_separate_limits(self, limiter):
        """Different clients should have separate limits"""
        request1 = MockRequest(client_ip="192.168.1.1")
        request2 = MockRequest(client_ip="192.168.1.2")

        # Max out client 1 (with delays) - 30 requests for anonymous
        for _ in range(30):
            await limiter.check(request1)
            await asyncio.sleep(0.25)  # Avoid burst limit (5 rps = 0.2s min)

        # Client 2 should still be allowed
        await limiter.check(request2)  # Should not raise

    @pytest.mark.asyncio
    async def test_uses_forwarded_ip(self, limiter):
        """Should use X-Forwarded-For header when present"""
        request = MockRequest(
            client_ip="127.0.0.1", headers={"x-forwarded-for": "203.0.113.50"}
        )

        client_id = limiter._get_client_id(request)
        assert client_id == "203.0.113.50"

    def test_get_remaining_returns_correct_info(self, limiter):
        """Should return correct remaining requests info"""
        request = MockRequest()

        info = limiter.get_remaining(request)

        assert "limit" in info
        assert "remaining" in info
        assert "reset" in info
        assert "role" in info
        assert info["limit"] == 30  # Anonymous role limit
        assert info["remaining"] == 30
        assert info["role"] == "anonymous"


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware"""

    @pytest.mark.asyncio
    async def test_excludes_health_endpoint(self):
        """Should not rate limit health endpoints"""
        limiter = RateLimiter(requests_per_minute=1)

        app = AsyncMock()
        middleware = RateLimitMiddleware(app, limiter=limiter)

        request = MockRequest()
        request.url.path = "/health"

        # Should not be rate limited even with limit=1
        for _ in range(5):
            call_next = AsyncMock(return_value=Mock(headers={}))
            await middleware.dispatch(request, call_next)

    @pytest.mark.asyncio
    async def test_adds_rate_limit_headers(self):
        """Should add rate limit headers to response"""
        limiter = RateLimiter(requests_per_minute=100)

        app = AsyncMock()
        middleware = RateLimitMiddleware(app, limiter=limiter)

        request = MockRequest()
        response = Mock()
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        await middleware.dispatch(request, call_next)

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware"""

    @pytest.mark.asyncio
    async def test_adds_security_headers(self):
        """Should add security headers to response"""
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)

        request = MockRequest()
        response = Mock()
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        await middleware.dispatch(request, call_next)

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"


class TestTimingMiddleware:
    """Tests for TimingMiddleware"""

    @pytest.mark.asyncio
    async def test_adds_timing_header(self):
        """Should add X-Process-Time header"""
        app = AsyncMock()
        middleware = TimingMiddleware(app)

        request = MockRequest()
        response = Mock()
        response.headers = {}

        async def slow_handler(req):
            await asyncio.sleep(0.01)
            return response

        call_next = AsyncMock(side_effect=slow_handler)

        result = await middleware.dispatch(request, call_next)

        assert "X-Process-Time" in result.headers
        # Should be at least 10ms
        time_str = result.headers["X-Process-Time"]
        time_ms = float(time_str.replace("ms", ""))
        assert time_ms >= 10


class TestErrorHandlingMiddleware:
    """Tests for ErrorHandlingMiddleware"""

    @pytest.mark.asyncio
    async def test_passes_through_normal_responses(self):
        """Should pass through normal responses unchanged"""
        app = AsyncMock()
        middleware = ErrorHandlingMiddleware(app)

        request = MockRequest()
        expected_response = Mock()

        call_next = AsyncMock(return_value=expected_response)

        result = await middleware.dispatch(request, call_next)

        assert result == expected_response

    @pytest.mark.asyncio
    async def test_handles_unhandled_exceptions(self):
        """Should return 500 for unhandled exceptions"""
        from fastapi.responses import JSONResponse

        app = AsyncMock()
        middleware = ErrorHandlingMiddleware(app)

        request = MockRequest()

        async def failing_handler(req):
            raise RuntimeError("Unexpected error")

        call_next = AsyncMock(side_effect=failing_handler)

        result = await middleware.dispatch(request, call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


class TestSetupMiddleware:
    """Tests for setup_middleware function"""

    def test_adds_all_middleware(self):
        """Should add all middleware to app"""
        from fastapi import FastAPI

        app = FastAPI()
        initial_middleware_count = len(app.user_middleware)

        setup_middleware(app)

        # Should have added 4 middleware
        assert len(app.user_middleware) == initial_middleware_count + 4

    def test_can_disable_middleware(self):
        """Should respect disable flags"""
        from fastapi import FastAPI

        app = FastAPI()
        initial_middleware_count = len(app.user_middleware)

        setup_middleware(
            app,
            enable_rate_limit=False,
            enable_security_headers=False,
            enable_error_handling=False,
            enable_timing=False,
        )

        # Should not have added any middleware
        assert len(app.user_middleware) == initial_middleware_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
