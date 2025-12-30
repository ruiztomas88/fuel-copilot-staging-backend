#!/bin/bash
# stop_stack.sh - Stop the complete Fuel Analytics stack
# Usage: ./stop_stack.sh

echo "🛑 Stopping Fuel Analytics Stack..."
echo ""

# Stop backend
echo "📦 Stopping Backend API..."
pkill -f "python.*main.py" && echo "    ✅ Backend stopped" || echo "    ⚠️  Backend not running"

# Stop wialon sync
echo "📦 Stopping Wialon Sync..."
pkill -f "python.*wialon_sync_enhanced.py" && echo "    ✅ Wialon stopped" || echo "    ⚠️  Wialon not running"

# Stop frontend
echo "📦 Stopping Frontend..."
pkill -f "vite" && echo "    ✅ Frontend stopped" || echo "    ⚠️  Frontend not running"

echo ""
echo "✅ Stack stopped"
