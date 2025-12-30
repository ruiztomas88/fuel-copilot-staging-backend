"""
API fixtures for testing
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Test client for API testing"""
    # Import main app
    from main import app

    return TestClient(app)


@pytest.fixture
def mock_database():
    """Mock database for API tests"""
    with patch("database.get_connection") as mock:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        mock.return_value = mock_conn
        yield mock


@pytest.fixture
def auth_headers():
    """Authentication headers for API tests"""
    return {"X-API-Key": "test-api-key-12345"}
