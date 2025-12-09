"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                   CRITICAL STARTUP TESTS                                       ║
║              Tests that MUST pass before any deploy                            ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  These tests verify:                                                           ║
║  1. App can import without crashing                                            ║
║  2. No duplicate endpoints                                                     ║
║  3. All routers load without DB connections                                    ║
║  4. Critical endpoints respond                                                 ║
║  5. Auth system initializes                                                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Run with: pytest tests/test_critical_startup.py -v
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAppStartup:
    """Tests that verify the app can start without errors"""

    def test_main_imports_without_error(self):
        """Critical: main.py must import without crashing"""
        try:
            import main

            assert hasattr(main, "app"), "main.py must have 'app' FastAPI instance"
        except Exception as e:
            pytest.fail(f"main.py failed to import: {e}")

    def test_app_has_routes(self):
        """App must have routes defined"""
        from main import app

        routes = [route.path for route in app.routes]
        assert len(routes) > 10, f"App should have many routes, found {len(routes)}"

    def test_no_duplicate_endpoints(self):
        """No endpoint should be registered twice"""
        from main import app

        seen = []
        duplicates = set()

        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    key = (route.path, method)
                    if key in seen:
                        duplicates.add(key)
                    seen.append(key)

        assert len(duplicates) == 0, f"Found duplicate endpoints: {duplicates}"


class TestCriticalImports:
    """Tests that critical modules can be imported"""

    def test_auth_imports(self):
        """Auth module must import"""
        try:
            import auth

            assert hasattr(auth, "get_current_user") or hasattr(auth, "verify_token")
        except Exception as e:
            pytest.fail(f"auth.py failed to import: {e}")

    def test_database_imports(self):
        """Database module must import"""
        try:
            import database
        except Exception as e:
            pytest.fail(f"database.py failed to import: {e}")

    def test_models_imports(self):
        """Models module must import"""
        try:
            import models
        except Exception as e:
            pytest.fail(f"models.py failed to import: {e}")

    def test_config_imports(self):
        """Config module must import"""
        try:
            import config
        except Exception as e:
            pytest.fail(f"config.py failed to import: {e}")


class TestRoutersPackage:
    """Tests that the routers package loads correctly"""

    def test_routers_package_imports(self):
        """Routers __init__.py must import without error"""
        try:
            import routers
        except Exception as e:
            pytest.fail(f"routers package failed to import: {e}")

    def test_include_all_routers_callable(self):
        """include_all_routers function must exist and be callable"""
        from routers import include_all_routers

        assert callable(include_all_routers)


class TestCriticalEndpoints:
    """Tests that critical endpoints exist and respond"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)

    def test_health_endpoint_exists(self, client):
        """Health endpoint must respond"""
        response = client.get("/fuelAnalytics/api/health")
        assert response.status_code in [
            200,
            401,
            403,
        ], f"Health endpoint returned {response.status_code}"

    def test_status_endpoint_exists(self, client):
        """Status endpoint must respond"""
        response = client.get("/fuelAnalytics/api/status")
        assert response.status_code in [
            200,
            401,
            403,
        ], f"Status endpoint returned {response.status_code}"

    def test_login_endpoint_exists(self, client):
        """Login endpoint must exist"""
        # Check route exists
        routes = [r.path for r in client.app.routes]
        login_routes = [
            r for r in routes if "login" in r.lower() or "token" in r.lower()
        ]
        assert len(login_routes) > 0, "No login/token endpoint found"


class TestNoBreakingChanges:
    """Tests that verify we haven't broken existing functionality"""

    def test_api_prefix_correct(self):
        """All API routes should use correct prefix"""
        from main import app

        api_routes = [
            route.path
            for route in app.routes
            if hasattr(route, "path") and "/api" in route.path
        ]

        for route in api_routes:
            # Skip OpenAPI routes
            if route.startswith("/openapi") or route.startswith("/docs"):
                continue
            # All API routes should use fuelAnalytics prefix
            if not route.startswith("/fuelAnalytics/api"):
                pytest.fail(f"Route {route} doesn't use /fuelAnalytics/api prefix")

    def test_cors_middleware_present(self):
        """CORS middleware should be configured"""
        from main import app

        middleware_names = [type(m).__name__ for m in app.user_middleware]
        # CORSMiddleware is added via add_middleware, check app.middleware_stack
        has_cors = any("CORS" in str(m) for m in app.user_middleware)
        # This test is informational - CORS is critical for frontend
        if not has_cors:
            import warnings

            warnings.warn("CORS middleware may not be configured")


class TestDatabaseConnections:
    """Tests that database connections don't crash the app"""

    def test_database_manager_exists(self):
        """DatabaseManager class must exist"""
        from database import DatabaseManager
        
        assert DatabaseManager is not None

    def test_database_manager_instantiates(self):
        """DatabaseManager must instantiate without crashing"""
        from database import DatabaseManager
        
        # Should be able to create instance
        dm = DatabaseManager()
        assert dm is not None

    def test_db_pool_importable(self):
        """Database pool must be importable"""
        try:
            import database_pool
        except ImportError:
            # Optional module
            pass
        except Exception as e:
            pytest.fail(f"database_pool.py crashed on import: {e}")
class TestEstimatorCore:
    """Tests for the fuel estimator core functionality"""

    def test_estimator_imports(self):
        """Estimator must import"""
        try:
            from estimator import FuelEstimator
        except Exception as e:
            pytest.fail(f"estimator.py failed to import: {e}")

    def test_estimator_instantiates(self):
        """Estimator must instantiate without DB"""
        from estimator import FuelEstimator
        
        # Should be able to create instance without crashing
        # FuelEstimator requires truck_id, capacity_liters, and config
        test_config = {
            "min_fuel_rate": 0.5,
            "max_fuel_rate": 40.0,
            "idle_consumption_lph": 2.0,
            "max_gap_minutes": 30,
        }
        est = FuelEstimator(
            truck_id="TEST-001",
            capacity_liters=500.0,
            config=test_config
        )
        assert est is not None
class TestURLConsistency:
    """Tests that all URLs use consistent casing"""

    def test_api_routes_use_camelcase(self):
        """API routes should use fuelAnalytics (camelCase) not fuelanalytics"""
        from main import app

        for route in app.routes:
            if hasattr(route, "path"):
                path = route.path
                if "fuelanalytics" in path.lower():
                    # Verify it's camelCase
                    assert (
                        "fuelAnalytics" in path
                    ), f"Route {path} should use 'fuelAnalytics' (camelCase)"
