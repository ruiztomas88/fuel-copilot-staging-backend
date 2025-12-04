"""
Audit Log Module v3.12.21
Database-backed audit trail for security and compliance

Addresses audit item #32: Audit log for changes

Features:
- Log all API requests with user, action, and result
- Track configuration changes
- Security event logging
- Query and export audit data
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from contextlib import contextmanager
from functools import wraps

import pymysql
from pymysql.cursors import DictCursor
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================
def _get_db_config() -> Dict:
    """Get database configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "fuel_admin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup."""
    conn = None
    try:
        conn = pymysql.connect(**_get_db_config())
        yield conn
    finally:
        if conn:
            conn.close()


# =============================================================================
# AUDIT LOG ACTIONS
# =============================================================================
class AuditAction:
    """Standard audit action types."""

    # Auth
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    PASSWORD_CHANGE = "auth.password.change"

    # User Management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ACTIVATE = "user.activate"
    USER_DEACTIVATE = "user.deactivate"

    # API Keys
    APIKEY_CREATE = "apikey.create"
    APIKEY_REVOKE = "apikey.revoke"
    APIKEY_DELETE = "apikey.delete"

    # Carrier Management
    CARRIER_CREATE = "carrier.create"
    CARRIER_UPDATE = "carrier.update"
    CARRIER_DELETE = "carrier.delete"

    # Data Access
    DATA_EXPORT = "data.export"
    DATA_READ = "data.read"
    REPORT_GENERATE = "report.generate"

    # Configuration
    CONFIG_CHANGE = "config.change"
    SETTINGS_UPDATE = "settings.update"

    # Alerts
    ALERT_CREATE = "alert.create"
    ALERT_ACKNOWLEDGE = "alert.acknowledge"
    ALERT_RESOLVE = "alert.resolve"

    # Security
    RATE_LIMIT_EXCEEDED = "security.rate_limit"
    UNAUTHORIZED_ACCESS = "security.unauthorized"
    SUSPICIOUS_ACTIVITY = "security.suspicious"


# =============================================================================
# AUDIT ENTRY DATA CLASS
# =============================================================================
@dataclass
class AuditEntry:
    """Audit log entry."""

    id: int
    timestamp_utc: datetime
    user_id: Optional[str]
    username: Optional[str]
    user_role: Optional[str]
    carrier_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    method: Optional[str]
    path: Optional[str]
    query_params: Optional[str]
    request_body: Optional[str]
    status_code: Optional[int]
    response_time_ms: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_message: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "timestamp": self.timestamp_utc.isoformat() if self.timestamp_utc else None,
            "user_id": self.user_id,
            "username": self.username,
            "user_role": self.user_role,
            "carrier_id": self.carrier_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "ip_address": self.ip_address,
            "success": self.success,
            "error_message": self.error_message,
        }


# =============================================================================
# AUDIT LOGGER
# =============================================================================
class AuditLogger:
    """
    Database-backed audit logging.

    Logs all security-relevant events to the audit_log table.
    """

    # Paths to exclude from automatic logging
    EXCLUDED_PATHS = {
        "/fuelAnalytics/api/docs",
        "/fuelAnalytics/api/redoc",
        "/fuelAnalytics/api/openapi.json",
        "/metrics",
        "/health",
        "/favicon.ico",
    }

    # Sensitive fields to redact from request body
    SENSITIVE_FIELDS = {"password", "token", "api_key", "secret", "credential"}

    def __init__(self):
        pass

    def log(
        self,
        action: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        user_role: Optional[str] = None,
        carrier_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        query_params: Optional[Dict] = None,
        request_body: Optional[Dict] = None,
        status_code: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> Optional[int]:
        """
        Log an audit event.

        Returns:
            Audit log entry ID or None on error.
        """
        # Redact sensitive fields
        if request_body:
            request_body = self._redact_sensitive(request_body)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO audit_log (
                            timestamp_utc, user_id, username, user_role, carrier_id,
                            action, resource_type, resource_id,
                            method, path, query_params, request_body,
                            status_code, response_time_ms,
                            ip_address, user_agent,
                            success, error_message
                        )
                        VALUES (
                            NOW(), %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s
                        )
                        """,
                        (
                            user_id,
                            username,
                            user_role,
                            carrier_id,
                            action,
                            resource_type,
                            resource_id,
                            method,
                            path,
                            json.dumps(query_params) if query_params else None,
                            json.dumps(request_body) if request_body else None,
                            status_code,
                            response_time_ms,
                            ip_address,
                            user_agent,
                            success,
                            error_message,
                        ),
                    )
                    return cursor.lastrowid

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            return None

    def _redact_sensitive(self, data: Dict) -> Dict:
        """Redact sensitive fields from data."""
        redacted = {}
        for key, value in data.items():
            if any(s in key.lower() for s in self.SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive(value)
            else:
                redacted[key] = value
        return redacted

    def log_request(
        self,
        request: Request,
        response: Response,
        user_info: Optional[Dict] = None,
        response_time_ms: int = 0,
    ) -> None:
        """Log an HTTP request/response."""
        path = request.url.path

        # Skip excluded paths
        if path in self.EXCLUDED_PATHS:
            return

        # Skip static files
        if path.startswith("/static"):
            return

        # Determine action based on method and path
        action = self._infer_action(request.method, path)

        # Extract user info
        user_id = None
        username = None
        user_role = None
        carrier_id = None

        if user_info:
            user_id = user_info.get("id") or user_info.get("user_id")
            username = user_info.get("username")
            user_role = user_info.get("role")
            carrier_id = user_info.get("carrier_id")

        # Get client IP
        ip_address = request.client.host if request.client else None
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()

        # Log the entry
        self.log(
            action=action,
            user_id=user_id,
            username=username,
            user_role=user_role,
            carrier_id=carrier_id,
            resource_type=self._infer_resource_type(path),
            resource_id=self._extract_resource_id(path),
            method=request.method,
            path=path,
            query_params=dict(request.query_params),
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            ip_address=ip_address,
            user_agent=request.headers.get("User-Agent"),
            success=200 <= response.status_code < 400,
        )

    def _infer_action(self, method: str, path: str) -> str:
        """Infer action type from HTTP method and path."""
        method = method.upper()

        # Auth endpoints
        if "/auth/login" in path:
            return AuditAction.LOGIN_SUCCESS if method == "POST" else "auth.view"
        if "/auth/logout" in path:
            return AuditAction.LOGOUT
        if "/auth/refresh" in path:
            return AuditAction.TOKEN_REFRESH

        # User management
        if "/users" in path or "/admin/users" in path:
            if method == "POST":
                return AuditAction.USER_CREATE
            elif method == "PUT" or method == "PATCH":
                return AuditAction.USER_UPDATE
            elif method == "DELETE":
                return AuditAction.USER_DELETE
            return AuditAction.DATA_READ

        # API keys
        if "/api-keys" in path:
            if method == "POST":
                return AuditAction.APIKEY_CREATE
            elif method == "DELETE":
                return AuditAction.APIKEY_DELETE
            return AuditAction.DATA_READ

        # Export
        if "/export" in path or "/download" in path:
            return AuditAction.DATA_EXPORT

        # Reports
        if "/report" in path:
            return AuditAction.REPORT_GENERATE

        # Settings/Config
        if "/settings" in path or "/config" in path:
            if method in ("POST", "PUT", "PATCH"):
                return AuditAction.CONFIG_CHANGE
            return AuditAction.DATA_READ

        # Alerts
        if "/alerts" in path:
            if method == "POST":
                return AuditAction.ALERT_CREATE
            elif method == "PUT" or method == "PATCH":
                return AuditAction.ALERT_ACKNOWLEDGE
            return AuditAction.DATA_READ

        # Default
        if method == "GET":
            return AuditAction.DATA_READ
        elif method in ("POST", "PUT", "PATCH", "DELETE"):
            return f"data.{method.lower()}"

        return f"api.{method.lower()}"

    def _infer_resource_type(self, path: str) -> Optional[str]:
        """Infer resource type from path."""
        parts = path.strip("/").split("/")

        # Skip api prefix
        if parts and parts[0] == "fuelAnalytics":
            parts = parts[1:]
        if parts and parts[0] == "api":
            parts = parts[1:]

        if not parts:
            return None

        # Return first meaningful part
        resource = parts[0]

        # Normalize plurals
        if resource.endswith("s") and len(resource) > 3:
            resource = resource[:-1]

        return resource

    def _extract_resource_id(self, path: str) -> Optional[str]:
        """Extract resource ID from path if present."""
        parts = path.strip("/").split("/")

        # Look for ID patterns (typically after resource name)
        for i, part in enumerate(parts):
            # Check if it looks like an ID (numeric or truck ID like XX1234)
            if part.isdigit():
                return part
            if len(part) <= 10 and any(c.isdigit() for c in part):
                return part

        return None

    # =========================================================================
    # QUERY METHODS
    # =========================================================================
    def query(
        self,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        carrier_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Query audit log entries."""
        where_clauses = []
        params = []

        if action:
            where_clauses.append("action = %s")
            params.append(action)

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)

        if carrier_id:
            where_clauses.append("carrier_id = %s")
            params.append(carrier_id)

        if resource_type:
            where_clauses.append("resource_type = %s")
            params.append(resource_type)

        if start_date:
            where_clauses.append("timestamp_utc >= %s")
            params.append(start_date)

        if end_date:
            where_clauses.append("timestamp_utc <= %s")
            params.append(end_date)

        if success_only is not None:
            where_clauses.append("success = %s")
            params.append(1 if success_only else 0)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        params.extend([limit, offset])

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT id, timestamp_utc, user_id, username, user_role,
                               carrier_id, action, resource_type, resource_id,
                               method, path, status_code, response_time_ms,
                               ip_address, success, error_message
                        FROM audit_log
                        {where_sql}
                        ORDER BY timestamp_utc DESC
                        LIMIT %s OFFSET %s
                        """,
                        params,
                    )
                    return list(cursor.fetchall())

        except Exception as e:
            logger.error(f"Error querying audit log: {e}")
            return []

    def get_summary(
        self,
        carrier_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get audit log summary statistics."""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Base where clause
                    where = "WHERE timestamp_utc >= %s"
                    params = [start_date]

                    if carrier_id and carrier_id != "*":
                        where += " AND carrier_id = %s"
                        params.append(carrier_id)

                    # Total events
                    cursor.execute(
                        f"SELECT COUNT(*) as total FROM audit_log {where}", params
                    )
                    total = cursor.fetchone()["total"]

                    # Events by action
                    cursor.execute(
                        f"""
                        SELECT action, COUNT(*) as count
                        FROM audit_log
                        {where}
                        GROUP BY action
                        ORDER BY count DESC
                        LIMIT 10
                        """,
                        params,
                    )
                    by_action = list(cursor.fetchall())

                    # Failed events
                    cursor.execute(
                        f"""
                        SELECT COUNT(*) as failed
                        FROM audit_log
                        {where} AND success = 0
                        """,
                        params,
                    )
                    failed = cursor.fetchone()["failed"]

                    # Unique users
                    cursor.execute(
                        f"""
                        SELECT COUNT(DISTINCT user_id) as unique_users
                        FROM audit_log
                        {where} AND user_id IS NOT NULL
                        """,
                        params,
                    )
                    unique_users = cursor.fetchone()["unique_users"]

                    # Recent security events
                    cursor.execute(
                        f"""
                        SELECT action, COUNT(*) as count
                        FROM audit_log
                        {where} AND action LIKE 'security.%'
                        GROUP BY action
                        """,
                        params,
                    )
                    security_events = list(cursor.fetchall())

                    return {
                        "period_days": days,
                        "total_events": total,
                        "failed_events": failed,
                        "success_rate": (
                            round((1 - failed / total) * 100, 2) if total > 0 else 100
                        ),
                        "unique_users": unique_users,
                        "top_actions": by_action,
                        "security_events": security_events,
                    }

        except Exception as e:
            logger.error(f"Error getting audit summary: {e}")
            return {"error": str(e)}


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create AuditLogger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# =============================================================================
# FASTAPI MIDDLEWARE
# =============================================================================
class AuditMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic request auditing.

    Logs all requests with timing and user information.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        # Get user info from request state (set by auth middleware)
        user_info = getattr(request.state, "user", None)
        if user_info and hasattr(user_info, "__dict__"):
            user_info = user_info.__dict__

        # Log request (async to not block response)
        try:
            audit_logger = get_audit_logger()
            audit_logger.log_request(
                request=request,
                response=response,
                user_info=user_info,
                response_time_ms=response_time_ms,
            )
        except Exception as e:
            logger.error(f"Audit logging error: {e}")

        return response


# =============================================================================
# DECORATOR FOR EXPLICIT AUDITING
# =============================================================================
def audit_action(action: str, resource_type: Optional[str] = None):
    """
    Decorator for explicitly auditing function calls.

    Usage:
        @audit_action(AuditAction.CONFIG_CHANGE, "settings")
        async def update_settings(settings: Dict, current_user: User):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            audit = get_audit_logger()

            # Extract user from kwargs if present
            user_info = kwargs.get("current_user")
            if user_info and hasattr(user_info, "__dict__"):
                user_info = user_info.__dict__

            try:
                result = await func(*args, **kwargs)

                # Log success
                audit.log(
                    action=action,
                    resource_type=resource_type,
                    user_id=user_info.get("id") if user_info else None,
                    username=user_info.get("username") if user_info else None,
                    user_role=user_info.get("role") if user_info else None,
                    carrier_id=user_info.get("carrier_id") if user_info else None,
                    success=True,
                )

                return result

            except Exception as e:
                # Log failure
                audit.log(
                    action=action,
                    resource_type=resource_type,
                    user_id=user_info.get("id") if user_info else None,
                    username=user_info.get("username") if user_info else None,
                    success=False,
                    error_message=str(e),
                )
                raise

        return wrapper

    return decorator
