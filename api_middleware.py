"""
API Middleware Module for Fuel Copilot v4.0.0

Production-ready middleware for:
- Rate limiting (with role-based limits, Redis support)
- Request validation
- Error handling
- Security headers

Usage:
    from api_middleware import setup_middleware
    setup_middleware(app)
"""

import os
import time
import logging
from typing import Callable, Optional, Dict
from functools import wraps
from collections import defaultdict
import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def is_testing_mode() -> bool:
    """🆕 v4.1: Check if we're in testing mode (rate limiting disabled).

    Note: Set SKIP_RATE_LIMIT=1 to disable rate limiting.
    This is different from TESTING which is for general test mode.
    """
    return os.getenv("SKIP_RATE_LIMIT", "").lower() in ("1", "true", "yes")


# Redis configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_RATE_LIMIT_ENABLED = os.environ.get("REDIS_RATE_LIMIT", "true").lower() == "true"


# ===========================================
# 🆕 v3.12.21: ROLE-BASED RATE LIMITS
# ===========================================

# Rate limits by user role
RATE_LIMITS_BY_ROLE: Dict[str, Dict[str, int]] = {
    "super_admin": {
        "requests_per_minute": 300,
        "requests_per_second": 30,
        "burst_size": 50,
    },
    "admin": {
        "requests_per_minute": 180,
        "requests_per_second": 20,
        "burst_size": 30,
    },
    "viewer": {
        "requests_per_minute": 60,
        "requests_per_second": 10,
        "burst_size": 15,
    },
    "anonymous": {
        "requests_per_minute": 30,
        "requests_per_second": 5,
        "burst_size": 10,
    },
}


# ===========================================
# RATE LIMITER
# ===========================================


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    For production, consider using Redis-based rate limiting.

    Usage:
        limiter = RateLimiter(requests_per_minute=60)

        @app.get("/api/fleet")
        async def get_fleet(request: Request):
            limiter.check(request)
            ...
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_second: int = 10,
        burst_size: int = 20,
    ):
        self.rpm = requests_per_minute
        self.rps = requests_per_second
        self.burst = burst_size

        # Track requests per client
        self._requests: dict = defaultdict(list)
        self._lock = asyncio.Lock()
        # 🆕 v3.12.21: Track user roles for role-based limits
        self._user_roles: dict = {}

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request"""
        # Check for forwarded IP (behind proxy)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check for real IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _get_user_role(self, request: Request) -> str:
        """
        🆕 v3.12.21: Get user role from request for role-based rate limiting.
        """
        try:
            # Check if user info is attached to request state
            if (
                hasattr(request, "state")
                and hasattr(request.state, "user")
                and request.state.user
            ):
                return getattr(request.state.user, "role", "viewer")

            # Check authorization header for JWT
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                # In production, decode JWT to get role
                # For now, return "viewer" as default authenticated user
                return "viewer"
        except Exception:
            pass

        return "anonymous"

    def _get_limits_for_role(self, role: str) -> tuple:
        """Get rate limits for a specific role."""
        limits = RATE_LIMITS_BY_ROLE.get(role, RATE_LIMITS_BY_ROLE["anonymous"])
        return (
            limits["requests_per_minute"],
            limits["requests_per_second"],
            limits["burst_size"],
        )

    async def check(self, request: Request, role: str = None) -> None:
        """
        Check if request is within rate limits.
        Raises HTTPException(429) if rate limited.

        🆕 v3.12.21: Now supports role-based limits.
        🆕 v4.1: Disabled in TESTING_MODE
        """
        # Skip rate limiting in test mode
        if is_testing_mode():
            return

        client_id = self._get_client_id(request)
        user_role = role or self._get_user_role(request)
        rpm, rps, burst = self._get_limits_for_role(user_role)

        now = time.time()

        async with self._lock:
            # Clean old requests (older than 1 minute)
            self._requests[client_id] = [
                ts for ts in self._requests[client_id] if now - ts < 60
            ]

            requests = self._requests[client_id]

            # Check per-minute limit (role-based)
            if len(requests) >= rpm:
                retry_after = 60 - (now - requests[0])
                logger.warning(
                    f"Rate limit exceeded for {client_id} (role: {user_role})",
                    extra={
                        "client_id": client_id,
                        "requests_count": len(requests),
                        "limit": rpm,
                        "role": user_role,
                    },
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": f"{rpm} requests per minute",
                        "retry_after": int(retry_after),
                        "role": user_role,
                    },
                    headers={"Retry-After": str(int(retry_after))},
                )

            # Check per-second limit (burst protection, role-based)
            recent_requests = [ts for ts in requests if now - ts < 1]
            if len(recent_requests) >= rps:
                logger.warning(
                    f"Burst limit exceeded for {client_id} (role: {user_role})",
                    extra={
                        "client_id": client_id,
                        "recent_requests": len(recent_requests),
                        "limit": rps,
                        "role": user_role,
                    },
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Too many requests",
                        "limit": f"{rps} requests per second",
                        "retry_after": 1,
                        "role": user_role,
                    },
                    headers={"Retry-After": "1"},
                )

            # Record this request
            self._requests[client_id].append(now)

    def get_remaining(self, request: Request, role: str = None) -> dict:
        """Get remaining rate limit info for client (role-aware)"""
        client_id = self._get_client_id(request)
        user_role = role or self._get_user_role(request)
        rpm, _, _ = self._get_limits_for_role(user_role)
        now = time.time()
        requests = [ts for ts in self._requests.get(client_id, []) if now - ts < 60]

        return {
            "limit": rpm,
            "remaining": max(0, rpm - len(requests)),
            "reset": int(now) + 60,
            "role": user_role,
        }


# ===========================================
# 🆕 v4.0: REDIS-BASED DISTRIBUTED RATE LIMITER
# ===========================================


class RedisRateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.

    Works correctly across multiple server instances for horizontal scaling.
    Falls back to in-memory limiter if Redis is unavailable.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_second: int = 10,
        burst_size: int = 20,
        redis_url: str = REDIS_URL,
    ):
        self.rpm = requests_per_minute
        self.rps = requests_per_second
        self.burst = burst_size
        self._redis_url = redis_url
        self._redis = None
        self._connected = False
        self._fallback = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_second=requests_per_second,
            burst_size=burst_size,
        )

    async def connect(self) -> bool:
        """Connect to Redis"""
        if not REDIS_RATE_LIMIT_ENABLED:
            logger.info("Redis rate limiting disabled, using in-memory")
            return False

        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            await self._redis.ping()
            self._connected = True
            logger.info(f"✅ Redis rate limiter connected")
            return True
        except ImportError:
            logger.warning("redis package not installed, using in-memory rate limiter")
            return False
        except Exception as e:
            logger.warning(f"Redis rate limiter connection failed: {e}")
            return False

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"

    def _get_user_role(self, request: Request) -> str:
        """Get user role from request"""
        try:
            if hasattr(request, "state") and hasattr(request.state, "user"):
                return getattr(request.state.user, "role", "viewer")
            if request.headers.get("authorization", "").startswith("Bearer "):
                return "viewer"
        except Exception:
            pass
        return "anonymous"

    def _get_limits_for_role(self, role: str) -> tuple:
        """Get rate limits for role"""
        limits = RATE_LIMITS_BY_ROLE.get(role, RATE_LIMITS_BY_ROLE["anonymous"])
        return (
            limits["requests_per_minute"],
            limits["requests_per_second"],
            limits["burst_size"],
        )

    async def check(self, request: Request, role: str = None) -> None:
        """Check rate limit using Redis sliding window"""
        if is_testing_mode():
            return

        # Fallback to in-memory if not connected
        if not self._connected:
            await self._fallback.check(request, role)
            return

        client_id = self._get_client_id(request)
        user_role = role or self._get_user_role(request)
        rpm, rps, _ = self._get_limits_for_role(user_role)

        now = time.time()
        minute_key = f"rl:rpm:{client_id}"
        second_key = f"rl:rps:{client_id}"

        try:
            # Use Redis pipeline for atomicity
            pipe = self._redis.pipeline()

            # Remove old entries and count current for minute window
            pipe.zremrangebyscore(minute_key, 0, now - 60)
            pipe.zcard(minute_key)

            # Remove old entries and count current for second window
            pipe.zremrangebyscore(second_key, 0, now - 1)
            pipe.zcard(second_key)

            results = await pipe.execute()
            minute_count = results[1]
            second_count = results[3]

            # Check per-minute limit
            if minute_count >= rpm:
                retry_after = 60
                logger.warning(
                    f"Rate limit exceeded for {client_id} (role: {user_role}, backend: redis)"
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": f"{rpm} requests per minute",
                        "retry_after": retry_after,
                        "role": user_role,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            # Check per-second limit
            if second_count >= rps:
                logger.warning(
                    f"Burst limit exceeded for {client_id} (role: {user_role}, backend: redis)"
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Too many requests",
                        "limit": f"{rps} requests per second",
                        "retry_after": 1,
                        "role": user_role,
                    },
                    headers={"Retry-After": "1"},
                )

            # Record this request
            pipe = self._redis.pipeline()
            pipe.zadd(minute_key, {str(now): now})
            pipe.expire(minute_key, 61)
            pipe.zadd(second_key, {str(now): now})
            pipe.expire(second_key, 2)
            await pipe.execute()

        except HTTPException:
            raise
        except Exception as e:
            # On Redis error, fall back to in-memory
            logger.warning(f"Redis rate limit error, falling back: {e}")
            await self._fallback.check(request, role)

    def get_remaining(self, request: Request, role: str = None) -> dict:
        """Get remaining rate limit info"""
        # Use fallback for simplicity (stats are approximate anyway)
        return self._fallback.get_remaining(request, role)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    🆕 v4.0: Now supports Redis-based distributed rate limiting.

    Usage:
        app.add_middleware(RateLimitMiddleware, limiter=RateLimiter())
    """

    def __init__(self, app, limiter: RateLimiter = None):
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

        # Paths to exclude from rate limiting
        self.excluded_paths = {
            "/health",
            "/metrics",
            "/api/health",
            "/docs",
            "/openapi.json",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Check rate limit
        try:
            await self.limiter.check(request)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content=e.detail,
                headers=e.headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        rate_info = self.limiter.get_remaining(request)
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])

        return response


# ===========================================
# SECURITY HEADERS
# ===========================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        # Remove server header
        if "server" in response.headers:
            del response.headers["server"]

        return response


# ===========================================
# ERROR HANDLING
# ===========================================


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling with structured error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            raise  # Let FastAPI handle HTTPException
        except Exception as e:
            logger.exception(
                "Unhandled exception",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(e),
                },
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": request.url.path,
                },
            )


# ===========================================
# REQUEST TIMING
# ===========================================


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Add request timing to response headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        return response


# ===========================================
# SETUP FUNCTION
# ===========================================


def setup_middleware(
    app: FastAPI,
    rate_limit_rpm: int = 120,
    rate_limit_rps: int = 20,
    enable_rate_limit: bool = True,
    enable_security_headers: bool = True,
    enable_error_handling: bool = True,
    enable_timing: bool = True,
    use_redis_rate_limit: bool = True,
) -> None:
    """
    Setup all middleware for the application.

    Args:
        app: FastAPI application instance
        rate_limit_rpm: Requests per minute limit
        rate_limit_rps: Requests per second limit
        enable_rate_limit: Enable rate limiting
        enable_security_headers: Add security headers
        enable_error_handling: Global error handling
        enable_timing: Add timing headers
        use_redis_rate_limit: Use Redis for distributed rate limiting (v4.0)
    """

    # Order matters! Last added = first executed

    if enable_timing:
        app.add_middleware(TimingMiddleware)
        logger.info("✅ Timing middleware enabled")

    if enable_error_handling:
        app.add_middleware(ErrorHandlingMiddleware)
        logger.info("✅ Error handling middleware enabled")

    if enable_security_headers:
        app.add_middleware(SecurityHeadersMiddleware)
        logger.info("✅ Security headers middleware enabled")

    if enable_rate_limit:
        if use_redis_rate_limit and REDIS_RATE_LIMIT_ENABLED:
            # Try Redis-based rate limiter for distributed setup
            limiter = RedisRateLimiter(
                requests_per_minute=rate_limit_rpm,
                requests_per_second=rate_limit_rps,
            )
            # Note: Connection happens async, will fallback if fails
            logger.info(
                f"✅ Rate limiting enabled (Redis): {rate_limit_rpm} rpm, {rate_limit_rps} rps"
            )
        else:
            # Use in-memory rate limiter
            limiter = RateLimiter(
                requests_per_minute=rate_limit_rpm,
                requests_per_second=rate_limit_rps,
            )
            logger.info(
                f"✅ Rate limiting enabled (memory): {rate_limit_rpm} rpm, {rate_limit_rps} rps"
            )
        app.add_middleware(RateLimitMiddleware, limiter=limiter)


# ===========================================
# DECORATORS
# ===========================================


def rate_limit(
    requests_per_minute: int = 60,
    requests_per_second: int = 10,
):
    """
    Decorator for endpoint-specific rate limiting.

    Usage:
        @app.get("/api/expensive")
        @rate_limit(requests_per_minute=10)
        async def expensive_endpoint():
            ...
    """
    limiter = RateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_second=requests_per_second,
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            await limiter.check(request)
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


# ===========================================
# EXAMPLE USAGE
# ===========================================

if __name__ == "__main__":
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI(title="Middleware Demo")

    # Setup middleware
    setup_middleware(app)

    @app.get("/")
    async def root():
        return {"message": "Hello World"}

    @app.get("/api/test")
    async def test():
        return {"status": "ok"}

    uvicorn.run(app, host="0.0.0.0", port=8001)
