#!/bin/bash
###############################################################################
# START STAGING - Fuel Copilot Backend Local
###############################################################################

set -e

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
LOG_DIR="$BACKEND_DIR/logs"
VENV="$BACKEND_DIR/venv/bin/activate"

echo "🚀 Starting Fuel Copilot Staging Environment..."

# Create logs directory
mkdir -p "$LOG_DIR"

# Kill existing processes
pkill -f wialon_sync_enhanced || true
pkill -f "uvicorn main:app" || true
sleep 2

cd "$BACKEND_DIR"
source "$VENV"

# Start Wialon Sync
echo "📡 Starting Wialon Sync..."
nohup python wialon_sync_enhanced.py > "$LOG_DIR/wialon_sync.log" 2>&1 &
WIALON_PID=$!
echo "   ✅ Wialon Sync started (PID: $WIALON_PID)"

# Wait for initial sync
sleep 5

# Start FastAPI
echo "🌐 Starting FastAPI..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!
echo "   ✅ FastAPI started (PID: $API_PID)"

# Start Frontend
echo "🎨 Starting Frontend..."
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend
pm2 delete fuel-frontend 2>/dev/null || true
pm2 start npm --name "fuel-frontend" -- run dev
echo "   ✅ Frontend started with PM2"

echo ""
echo "✅ STAGING ENVIRONMENT READY!"
echo "   🌐 Frontend: http://localhost:3000"
echo "   🔌 API: http://localhost:8000"
echo "   💾 Database: fuel_copilot_local"
echo "   📡 Wialon Sync: Active"
echo ""
echo "Logs:"
echo "   - Wialon: tail -f $LOG_DIR/wialon_sync.log"
echo "   - API: tail -f $LOG_DIR/api.log"
echo "   - Frontend: pm2 logs fuel-frontend"
echo ""
echo "Gestión Frontend:"
echo "   - Ver logs: pm2 logs fuel-frontend"
echo "   - Restart: pm2 restart fuel-frontend"
echo "   - Stop: pm2 stop fuel-frontend"
