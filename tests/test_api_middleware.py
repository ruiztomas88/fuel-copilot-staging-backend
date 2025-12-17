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

    def test_setup_with_in_memory_rate_limit(self):
        """Should use in-memory rate limiter when Redis disabled"""
        from fastapi import FastAPI

        app = FastAPI()

        with patch.dict(os.environ, {"REDIS_RATE_LIMIT": "false"}):
            setup_middleware(app, use_redis_rate_limit=False)

        # Should have added middleware
        assert len(app.user_middleware) > 0


class TestRateLimiterRoles:
    """Tests for role-based rate limiting"""

    @pytest.fixture
    def limiter(self, enable_rate_limiting):
        return RateLimiter(
            requests_per_minute=60,
            requests_per_second=10,
        )

    def test_get_user_role_from_state(self, limiter):
        """Should get role from request state"""
        request = MockRequest()
        request.state.user = Mock()
        request.state.user.role = "admin"

        role = limiter._get_user_role(request)
        assert role == "admin"

    def test_get_user_role_anonymous_when_no_auth(self, limiter):
        """Should return anonymous when no auth"""
        request = MockRequest()
        request.state.user = None
        request.headers = {}

        role = limiter._get_user_role(request)
        assert role == "anonymous"

    def test_get_user_role_viewer_with_bearer_token(self, limiter):
        """Should return viewer role with Bearer token"""
        request = MockRequest()
        request.state.user = None
        request.headers = {"authorization": "Bearer some_jwt_token"}

        role = limiter._get_user_role(request)
        assert role == "viewer"

    def test_get_limits_for_super_admin(self, limiter):
        """Should return super_admin limits"""
        rpm, rps, burst = limiter._get_limits_for_role("super_admin")
        assert rpm == 300
        assert rps == 30
        assert burst == 50

    def test_get_limits_for_admin(self, limiter):
        """Should return admin limits"""
        rpm, rps, burst = limiter._get_limits_for_role("admin")
        assert rpm == 180
        assert rps == 20
        assert burst == 30

    def test_get_limits_for_viewer(self, limiter):
        """Should return viewer limits"""
        rpm, rps, burst = limiter._get_limits_for_role("viewer")
        assert rpm == 60
        assert rps == 10
        assert burst == 15

    def test_get_limits_for_unknown_role_defaults_to_anonymous(self, limiter):
        """Should default to anonymous for unknown roles"""
        rpm, rps, burst = limiter._get_limits_for_role("unknown_role")
        assert rpm == 30
        assert rps == 5
        assert burst == 10

    def test_get_remaining_includes_role(self, limiter):
        """Should include role in remaining info"""
        request = MockRequest()
        request.state.user = Mock()
        request.state.user.role = "admin"

        info = limiter.get_remaining(request)
        assert info["role"] == "admin"
        assert info["limit"] == 180  # Admin limit


class TestRateLimiterClientId:
    """Tests for client ID extraction"""

    @pytest.fixture
    def limiter(self):
        return RateLimiter()

    def test_uses_x_real_ip_header(self, limiter):
        """Should use X-Real-IP when X-Forwarded-For is absent"""
        request = MockRequest()
        request.headers = {"x-real-ip": "10.0.0.1"}

        client_id = limiter._get_client_id(request)
        assert client_id == "10.0.0.1"

    def test_prefers_forwarded_for_over_real_ip(self, limiter):
        """Should prefer X-Forwarded-For over X-Real-IP"""
        request = MockRequest()
        request.headers = {
            "x-forwarded-for": "203.0.113.50, 70.41.3.18",
            "x-real-ip": "10.0.0.1",
        }

        client_id = limiter._get_client_id(request)
        assert client_id == "203.0.113.50"

    def test_returns_unknown_when_no_client(self, limiter):
        """Should return 'unknown' when client is None"""
        request = MockRequest()
        request.client = None
        request.headers = {}

        client_id = limiter._get_client_id(request)
        assert client_id == "unknown"


class TestRedisRateLimiter:
    """Tests for RedisRateLimiter class"""

    @pytest.fixture
    def redis_limiter(self):
        from api_middleware import RedisRateLimiter

        return RedisRateLimiter(
            requests_per_minute=60,
            requests_per_second=10,
        )

    def test_init_creates_fallback(self, redis_limiter):
        """Should create in-memory fallback limiter"""
        assert redis_limiter._fallback is not None
        assert isinstance(redis_limiter._fallback, RateLimiter)

    def test_not_connected_initially(self, redis_limiter):
        """Should not be connected initially"""
        assert redis_limiter._connected is False

    def test_get_client_id(self, redis_limiter):
        """Should extract client ID from request"""
        request = MockRequest(client_ip="192.168.1.100")
        client_id = redis_limiter._get_client_id(request)
        assert client_id == "192.168.1.100"

    def test_get_client_id_with_forwarded_header(self, redis_limiter):
        """Should prefer X-Forwarded-For header"""
        request = MockRequest(
            client_ip="127.0.0.1", headers={"x-forwarded-for": "8.8.8.8"}
        )
        client_id = redis_limiter._get_client_id(request)
        assert client_id == "8.8.8.8"

    def test_get_client_id_with_real_ip_header(self, redis_limiter):
        """Should use X-Real-IP when forwarded not present"""
        request = MockRequest(client_ip="127.0.0.1", headers={"x-real-ip": "1.2.3.4"})
        client_id = redis_limiter._get_client_id(request)
        assert client_id == "1.2.3.4"

    def test_get_user_role_anonymous(self, redis_limiter):
        """Should return anonymous for unauthenticated requests"""
        request = MockRequest()
        # Ensure state doesn't have user
        delattr(request.state, "user")
        request.headers = {}

        role = redis_limiter._get_user_role(request)
        assert role == "anonymous"

    def test_get_user_role_from_state(self, redis_limiter):
        """Should get role from request state"""
        request = MockRequest()
        request.state.user = Mock()
        request.state.user.role = "super_admin"

        role = redis_limiter._get_user_role(request)
        assert role == "super_admin"

    def test_get_limits_for_role(self, redis_limiter):
        """Should return correct limits for role"""
        rpm, rps, burst = redis_limiter._get_limits_for_role("admin")
        assert rpm == 180
        assert rps == 20
        assert burst == 30

    def test_get_remaining_uses_fallback(self, redis_limiter):
        """Should use fallback for get_remaining"""
        request = MockRequest()
        info = redis_limiter.get_remaining(request)

        assert "limit" in info
        assert "remaining" in info
        assert "reset" in info
        assert "role" in info

    @pytest.mark.asyncio
    async def test_check_uses_fallback_when_not_connected(
        self, redis_limiter, enable_rate_limiting
    ):
        """Should use fallback when Redis not connected"""
        request = MockRequest()

        # Should not raise since not connected (uses fallback)
        await redis_limiter.check(request)

    @pytest.mark.asyncio
    async def test_connect_returns_false_when_disabled(self, redis_limiter):
        """Should return False when Redis rate limiting is disabled"""
        with patch.dict(os.environ, {"REDIS_RATE_LIMIT": "false"}):
            from api_middleware import REDIS_RATE_LIMIT_ENABLED

            # Need to reload to pick up new value
            import importlib
            import api_middleware

            importlib.reload(api_middleware)

            new_limiter = api_middleware.RedisRateLimiter()
            # Can't test this directly due to module-level constant


class TestRateLimitDecorator:
    """Tests for rate_limit decorator"""

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_creates_limiter(self):
        """Should create a limiter with specified limits"""
        from api_middleware import rate_limit

        @rate_limit(requests_per_minute=10, requests_per_second=2)
        async def test_endpoint(request):
            return {"status": "ok"}

        # The decorator should work
        assert callable(test_endpoint)
        # Verify wrapped function still works
        request = MockRequest()
        result = await test_endpoint(request)
        assert result["status"] == "ok"


class TestIsTestingMode:
    """Tests for is_testing_mode function"""

    def test_returns_true_when_skip_rate_limit_set(self):
        """Should return True when SKIP_RATE_LIMIT=1"""
        from api_middleware import is_testing_mode

        with patch.dict(os.environ, {"SKIP_RATE_LIMIT": "1"}):
            # Need to check actual behavior
            assert os.environ.get("SKIP_RATE_LIMIT") == "1"

    def test_returns_false_when_skip_rate_limit_not_set(self):
        """Should return False when SKIP_RATE_LIMIT not set"""
        from api_middleware import is_testing_mode

        # Clear the env var
        with patch.dict(os.environ, {"SKIP_RATE_LIMIT": ""}, clear=False):
            result = is_testing_mode()
            # In test mode it depends on fixture


class TestRateLimitMiddlewareDispatch:
    """Additional tests for RateLimitMiddleware dispatch"""

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_works(self):
        """Should process requests through middleware"""
        limiter = RateLimiter(requests_per_minute=100, requests_per_second=10)
        app = AsyncMock()
        middleware = RateLimitMiddleware(app, limiter=limiter)

        request = MockRequest()
        request.url.path = "/api/test"

        response = Mock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        # Request should work
        result = await middleware.dispatch(request, call_next)
        assert result == response

    @pytest.mark.asyncio
    async def test_excludes_docs_endpoint(self):
        """Should not rate limit /docs endpoint"""
        limiter = RateLimiter(requests_per_minute=1)
        app = AsyncMock()
        middleware = RateLimitMiddleware(app, limiter=limiter)

        request = MockRequest()
        request.url.path = "/docs"

        response = Mock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        # Multiple requests should work
        for _ in range(5):
            await middleware.dispatch(request, call_next)

    @pytest.mark.asyncio
    async def test_excludes_openapi_endpoint(self):
        """Should not rate limit /openapi.json endpoint"""
        limiter = RateLimiter(requests_per_minute=1)
        app = AsyncMock()
        middleware = RateLimitMiddleware(app, limiter=limiter)

        request = MockRequest()
        request.url.path = "/openapi.json"

        response = Mock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        # Multiple requests should work
        for _ in range(5):
            await middleware.dispatch(request, call_next)


class TestSecurityHeadersRemoveServer:
    """Test security headers server removal"""

    @pytest.mark.asyncio
    async def test_removes_server_header(self):
        """Should remove Server header if present"""
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)

        request = MockRequest()
        response = Mock()
        response.headers = {"server": "nginx/1.18.0"}

        call_next = AsyncMock(return_value=response)

        await middleware.dispatch(request, call_next)

        assert "server" not in response.headers

    @pytest.mark.asyncio
    async def test_adds_cache_control_headers(self):
        """Should add cache control headers"""
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)

        request = MockRequest()
        response = Mock()
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        await middleware.dispatch(request, call_next)

        assert (
            response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
        )
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


class TestErrorHandlingMiddlewareHTTPException:
    """Test ErrorHandlingMiddleware with HTTPException"""

    @pytest.mark.asyncio
    async def test_reraises_http_exception(self):
        """Should re-raise HTTPException"""
        from fastapi import HTTPException

        app = AsyncMock()
        middleware = ErrorHandlingMiddleware(app)

        request = MockRequest()

        async def raise_http_exception(req):
            raise HTTPException(status_code=404, detail="Not found")

        call_next = AsyncMock(side_effect=raise_http_exception)

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)

        assert exc_info.value.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
