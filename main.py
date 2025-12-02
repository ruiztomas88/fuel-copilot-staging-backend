"""
FastAPI Backend for Fuel Copilot Dashboard
Azure VM Deployment Version

Run with: uvicorn main:app --host 0.0.0.0 --port 8000

All routes prefixed with /fuelanalytics for reverse proxy
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from routers import (
    fleet,
    trucks,
    efficiency,
    alerts,
    kpis,
    analytics,
    auth,
    refuels,
    admin,
)

# ============================================================================
# LIFESPAN
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("🚀 Fuel Copilot API starting on Azure VM...")
    print(
        f"📊 Environment: {'DEBUG' if os.getenv('DEBUG', 'false').lower() == 'true' else 'PRODUCTION'}"
    )
    yield
    print("👋 Shutting down Fuel Copilot API")


# ============================================================================
# APP CONFIGURATION
# ============================================================================

# API prefix for reverse proxy
API_PREFIX = "/fuelanalytics"

app = FastAPI(
    title="Fuel Copilot API",
    description="Fleet fuel monitoring and analytics API",
    version="3.10.8",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = os.getenv(
    "CORS_ORIGINS", "https://fleetbooster.net,http://localhost:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# INCLUDE ROUTERS WITH PREFIX
# ============================================================================

app.include_router(
    auth.router, prefix=f"{API_PREFIX}/api/auth", tags=["Authentication"]
)
app.include_router(fleet.router, prefix=f"{API_PREFIX}/api", tags=["Fleet"])
app.include_router(trucks.router, prefix=f"{API_PREFIX}/api", tags=["Trucks"])
app.include_router(efficiency.router, prefix=f"{API_PREFIX}/api", tags=["Efficiency"])
app.include_router(alerts.router, prefix=f"{API_PREFIX}/api", tags=["Alerts"])
app.include_router(kpis.router, prefix=f"{API_PREFIX}/api", tags=["KPIs"])
app.include_router(refuels.router, prefix=f"{API_PREFIX}/api", tags=["Refuels"])
app.include_router(
    analytics.router, prefix=f"{API_PREFIX}/api/analytics", tags=["Analytics"]
)
app.include_router(admin.router, prefix=f"{API_PREFIX}/api/admin", tags=["Admin"])


# ============================================================================
# ROOT ENDPOINTS
# ============================================================================


@app.get(f"{API_PREFIX}/")
async def root():
    """API root - returns version info"""
    return {
        "name": "Fuel Copilot API",
        "version": "3.10.8",
        "status": "running",
        "docs": f"{API_PREFIX}/docs",
    }


@app.get(f"{API_PREFIX}/health")
async def health_check():
    """Health check for load balancer"""
    return {"status": "healthy"}


@app.get(f"{API_PREFIX}/api/status")
async def api_status():
    """Quick API status check"""
    return {
        "status": "healthy",
        "version": "3.10.8",
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    uvicorn.run("main:app", host=host, port=port, reload=debug, log_level="info")
