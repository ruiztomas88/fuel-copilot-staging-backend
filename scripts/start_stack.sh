#!/bin/bash
# start_stack.sh - Start the complete Fuel Analytics stack
# Usage: ./start_stack.sh

echo "🚀 Starting Fuel Analytics Stack..."
echo ""

# 1. Backend API
echo "📦 1/3 Starting Backend API..."
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
DEV_MODE=false nohup /opt/anaconda3/bin/python main.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "    ✅ Backend started (PID: $BACKEND_PID)"
sleep 3

# 2. Wialon Sync Service
echo "📦 2/3 Starting Wialon Sync..."
nohup /opt/anaconda3/bin/python wialon_sync_enhanced.py > logs/wialon.log 2>&1 &
WIALON_PID=$!
echo "    ✅ Wialon started (PID: $WIALON_PID)"
sleep 2

# 3. Frontend
echo "📦 3/3 Starting Frontend..."
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend
nohup npm run dev > /dev/null 2>&1 &
FRONTEND_PID=$!
echo "    ✅ Frontend started (PID: $FRONTEND_PID)"
sleep 3

echo ""
echo "✅ Stack started successfully!"
echo ""
echo "📊 Services:"
echo "  Backend:  http://localhost:8000 (PID: $BACKEND_PID)"
echo "  Frontend: http://localhost:3000 (PID: $FRONTEND_PID)"
echo "  Wialon:   Running (PID: $WIALON_PID)"
echo ""
echo "📝 Logs:"
echo "  Backend:  tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend.log"
echo "  Wialon:   tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon.log"
echo ""
echo "🛑 To stop: ./stop_stack.sh"
