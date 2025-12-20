"""
Tests for Authentication Module (v3.12.21)
Phase 5: Additional test coverage

Tests the actual functions in auth.py
"""

from datetime import datetime, timedelta, timezone

import pytest


class TestPasswordHashing:
    """Test password hashing functions"""

    def test_hash_password(self):
        """Should hash password and verify correctly"""
        from auth import hash_password, verify_password

        password = "test_password_123"
        hashed = hash_password(password)

        # Hash should not be plain text
        assert hashed != password
        # Should be able to verify
        assert verify_password(password, hashed) is True
        # Wrong password should not verify
        assert verify_password("wrong_password", hashed) is False

    def test_hash_password_produces_unique_hashes(self):
        """bcrypt produces different hashes each time (different salts)"""
        from auth import hash_password, verify_password

        password = "test_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different (different salts)
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestAuthentication:
    """Test user authentication"""

    def test_authenticate_valid_user(self):
        """Should authenticate valid user"""
        from auth import authenticate_user

        # Using known test user from USERS_DB
        user = authenticate_user("admin", "FuelAdmin2025!")

        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "super_admin"

    def test_authenticate_invalid_password(self):
        """Should reject invalid password"""
        from auth import authenticate_user

        user = authenticate_user("admin", "wrong_password")
        assert user is None

    def test_authenticate_unknown_user(self):
        """Should reject unknown user"""
        from auth import authenticate_user

        user = authenticate_user("unknown_user", "password")
        assert user is None


class TestJWTTokens:
    """Test JWT token operations"""

    def test_create_access_token(self):
        """Should create valid JWT token"""
        from auth import create_access_token

        user_data = {
            "username": "testuser",
            "carrier_id": "test_carrier",
            "role": "viewer",
            "name": "Test User",
        }
        token = create_access_token(user_data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long

    def test_get_carrier_filter_super_admin(self):
        """Should return None for super admin (sees all carriers)"""
        from datetime import datetime, timedelta, timezone

        from auth import TokenData, get_carrier_filter

        user = TokenData(
            username="admin",
            carrier_id="*",
            role="super_admin",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        carrier_filter = get_carrier_filter(user)
        assert carrier_filter is None

    def test_get_carrier_filter_carrier_admin(self):
        """Should return carrier_id for carrier admin"""
        from datetime import datetime, timedelta, timezone

        from auth import TokenData, get_carrier_filter

        user = TokenData(
            username="carrier_admin",
            carrier_id="CARRIER123",
            role="carrier_admin",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        carrier_filter = get_carrier_filter(user)
        assert carrier_filter == "CARRIER123"

    def test_get_carrier_filter_no_auth(self):
        """Should return None when no auth (public endpoints)"""
        from auth import get_carrier_filter

        carrier_filter = get_carrier_filter(None)
        assert carrier_filter is None

    def test_filter_by_carrier(self):
        """Should filter data by carrier_id"""
        from auth import filter_by_carrier

        data = [
            {"id": 1, "carrier_id": "CARRIER_A"},
            {"id": 2, "carrier_id": "CARRIER_B"},
            {"id": 3, "carrier_id": "CARRIER_A"},
        ]

        filtered = filter_by_carrier(data, "CARRIER_A")
        assert len(filtered) == 2
        assert all(item["carrier_id"] == "CARRIER_A" for item in filtered)

    def test_filter_by_carrier_no_filter(self):
        """Should return all data when carrier_id is None"""
        from auth import filter_by_carrier

        data = [
            {"id": 1, "carrier_id": "CARRIER_A"},
            {"id": 2, "carrier_id": "CARRIER_B"},
        ]

        filtered = filter_by_carrier(data, None)
        assert len(filtered) == 2

    def test_create_access_token_with_expiry(self):
        """Should create token with custom expiry"""
        from auth import create_access_token, decode_token

        user_data = {
            "username": "testuser",
            "carrier_id": "test_carrier",
            "role": "admin",
            "name": "Test Admin",
        }
        expires = timedelta(hours=1)
        token = create_access_token(user_data, expires_delta=expires)

        token_data = decode_token(token)
        assert token_data is not None
        # Token should expire in about 1 hour
        time_diff = token_data.exp - datetime.now(timezone.utc)
        assert 3500 < time_diff.total_seconds() < 3700

    def test_decode_valid_token(self):
        """Should decode valid token correctly"""
        from auth import create_access_token, decode_token

        user_data = {
            "username": "testuser",
            "carrier_id": "test_carrier",
            "role": "carrier_admin",
            "name": "Test Admin",
        }
        token = create_access_token(user_data)
        decoded = decode_token(token)

        assert decoded is not None
        assert decoded.username == "testuser"
        assert decoded.carrier_id == "test_carrier"
        assert decoded.role == "carrier_admin"

    def test_decode_expired_token(self):
        """Should reject expired token"""
        from auth import create_access_token, decode_token

        user_data = {
            "username": "testuser",
            "carrier_id": "test_carrier",
            "role": "viewer",
            "name": "Test User",
        }
        # Create token that's already expired
        token = create_access_token(user_data, expires_delta=timedelta(seconds=-1))
        decoded = decode_token(token)

        assert decoded is None  # Expired tokens should not decode

    def test_decode_invalid_token(self):
        """Should reject invalid token"""
        from auth import decode_token

        decoded = decode_token("not.a.valid.token")
        assert decoded is None


class TestUserRoles:
    """Test user roles and permissions"""

    def test_users_db_structure(self):
        """Should have properly structured users"""
        from auth import USERS_DB

        assert "admin" in USERS_DB
        assert "skylord" in USERS_DB

        admin = USERS_DB["admin"]
        assert admin["role"] == "super_admin"
        assert admin["carrier_id"] == "*"  # Wildcard for all carriers

    def test_carrier_admin_role(self):
        """Carrier admin should have limited carrier access"""
        from auth import USERS_DB

        skylord = USERS_DB["skylord"]
        assert skylord["role"] == "carrier_admin"
        assert skylord["carrier_id"] == "skylord"  # Limited to one carrier

    def test_viewer_role(self):
        """Viewer should have read-only access"""
        from auth import USERS_DB

        viewer = USERS_DB["skylord_viewer"]
        assert viewer["role"] == "viewer"
        assert viewer["carrier_id"] == "skylord"


class TestSecurityConfig:
    """Test security configuration"""

    def test_algorithm_is_hs256(self):
        """Should use HS256 algorithm"""
        from auth import ALGORITHM

        assert ALGORITHM == "HS256"

    def test_token_expiration_is_7_days(self):
        """Should have 7-day token expiration"""
        from auth import ACCESS_TOKEN_EXPIRE_HOURS

        assert ACCESS_TOKEN_EXPIRE_HOURS == 168  # 7 days in hours

    def test_secret_key_exists(self):
        """Should have a secret key set"""
        from auth import SECRET_KEY

        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 20  # Should be a reasonably long key
