#!/bin/bash
###############################################################################
# STOP STAGING - Fuel Copilot Backend Local
###############################################################################

echo "🛑 Stopping Fuel Copilot Staging Environment..."

# Kill processes
pkill -f wialon_sync_enhanced && echo "   ✅ Wialon Sync stopped" || echo "   ℹ️  Wialon Sync not running"
pkill -f "uvicorn main:app" && echo "   ✅ FastAPI stopped" || echo "   ℹ️  FastAPI not running"
pm2 stop fuel-frontend 2>/dev/null && echo "   ✅ Frontend stopped" || echo "   ℹ️  Frontend not running"

sleep 2

echo ""
echo "✅ All services stopped!"
