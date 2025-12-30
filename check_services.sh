#!/bin/bash
# Check status of Fuel Analytics Services

echo "📊 Fuel Analytics Service Status"
echo "================================="
echo ""

# Backend
echo "🔧 Backend API (port 8000):"
if launchctl print gui/$(id -u)/com.fuelanalytics.backend 2>/dev/null | grep -q "state = running"; then
    echo "  ✅ Running"
    # Check if port is listening
    if lsof -i :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  ✅ Port 8000 listening"
    else
        echo "  ⚠️  Service running but port 8000 not listening"
    fi
else
    echo "  ❌ Not running"
fi
echo ""

# Wialon
echo "🌐 Wialon Sync:"
if launchctl print gui/$(id -u)/com.fuelanalytics.wialon 2>/dev/null | grep -q "state = running"; then
    echo "  ✅ Running"
else
    echo "  ❌ Not running"
fi
echo ""

# Frontend
echo "🎨 Frontend (port 3000):"
if launchctl print gui/$(id -u)/com.fuelanalytics.frontend 2>/dev/null | grep -q "state = running"; then
    echo "  ✅ Running"
    # Check if port is listening
    if lsof -i :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  ✅ Port 3000 listening"
    else
        echo "  ⚠️  Service running but port 3000 not listening"
    fi
else
    echo "  ❌ Not running"
fi
echo ""

# Process list
echo "📝 Active processes:"
ps aux | grep -E "main.py|wialon_sync_enhanced|vite" | grep -v grep | awk '{printf "  PID %s: %s\n", $2, $11}'

echo ""
echo "📈 Recent log activity (last 5 lines):"
echo ""
echo "Backend:"
tail -5 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend_api.log 2>/dev/null || echo "  No logs yet"
echo ""
echo "Wialon:"
tail -5 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync.log 2>/dev/null || echo "  No logs yet"
echo ""
echo "Frontend:"
tail -5 /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/logs/frontend.log 2>/dev/null || echo "  No logs yet"
