"""
Pytest Configuration for Fuel Copilot Tests
v4.1: Sets SKIP_RATE_LIMIT to disable rate limiting during tests

IMPORTANT: This must be the FIRST file imported by pytest.
The os.environ must be set BEFORE any test imports happen.
"""

import os

# CRITICAL: Set this BEFORE any other imports
os.environ["SKIP_RATE_LIMIT"] = "1"

import asyncio

import pytest

# Import all fixtures
from tests.fixtures.api_fixtures import *  # noqa
from tests.fixtures.database_fixtures import *  # noqa
from tests.fixtures.truck_fixtures import *  # noqa


# Event loop configuration for async tests
@pytest.fixture(scope="function")
def event_loop():
    """Create a new event loop for each test function"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    """Called after command line options have been parsed and all plugins loaded."""
    os.environ["SKIP_RATE_LIMIT"] = "1"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before any tests run."""
    os.environ["SKIP_RATE_LIMIT"] = "1"
    yield
    # Cleanup after all tests
    os.environ.pop("SKIP_RATE_LIMIT", None)


@pytest.fixture
def test_client():
    """Provide a test client for API tests."""
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)


@pytest.fixture
def enable_rate_limiting():
    """Fixture to temporarily enable rate limiting for specific tests."""
    original = os.environ.get("SKIP_RATE_LIMIT")
    os.environ.pop("SKIP_RATE_LIMIT", None)
    yield
    if original:
        os.environ["SKIP_RATE_LIMIT"] = original
    else:
        os.environ["SKIP_RATE_LIMIT"] = "1"
