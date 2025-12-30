#!/bin/bash
# Install Fuel Analytics Services for macOS
# This script installs launchd services to run the full stack 24/7

set -e

echo "🚀 Installing Fuel Analytics Services..."
echo ""

# Kill any manually running processes first
echo "🛑 Stopping any manually running processes..."
pkill -f "main.py" 2>/dev/null || true
pkill -f "wialon_sync_enhanced.py" 2>/dev/null || true
pkill -f "vite.*Fuel-Analytics-Frontend" 2>/dev/null || true
sleep 2

# Create logs directories
mkdir -p /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs
mkdir -p /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/logs

echo "📁 Created log directories"

# Stop any existing services (use correct unload syntax)
echo "🛑 Stopping existing launchd services..."
launchctl bootout gui/$(id -u)/com.fuelanalytics.backend 2>/dev/null || true
launchctl bootout gui/$(id -u)/com.fuelanalytics.wialon 2>/dev/null || true
launchctl bootout gui/$(id -u)/com.fuelanalytics.frontend 2>/dev/null || true
sleep 2

# Remove old service files
echo "🗑️  Removing old service files..."
rm -f ~/Library/LaunchAgents/com.fuelanalytics.backend.plist
rm -f ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist
rm -f ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist

# Copy new service files
echo "📋 Copying service files..."
cp /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/com.fuelanalytics.backend.plist ~/Library/LaunchAgents/
cp /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/com.fuelanalytics.wialon.plist ~/Library/LaunchAgents/
cp /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/services/com.fuelanalytics.frontend.plist ~/Library/LaunchAgents/

# Set correct permissions
chmod 644 ~/Library/LaunchAgents/com.fuelanalytics.*.plist
echo "🔐 Set permissions (644)"

# Load services with error handling
echo ""
echo "⚡ Loading services..."

echo "  Loading backend..."
if launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fuelanalytics.backend.plist 2>&1 | grep -q "Bootstrap failed"; then
    echo "    ⚠️  Backend bootstrap failed (may already be loaded)"
else
    echo "    ✅ Backend loaded"
fi
sleep 3

echo "  Loading wialon sync..."
if launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist 2>&1 | grep -q "Bootstrap failed"; then
    echo "    ⚠️  Wialon bootstrap failed (may already be loaded)"
else
    echo "    ✅ Wialon loaded"
fi
sleep 3

echo "  Loading frontend..."
if launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist 2>&1 | grep -q "Bootstrap failed"; then
    echo "    ⚠️  Frontend bootstrap failed (may already be loaded)"
else
    echo "    ✅ Frontend loaded"
fi

echo ""
echo "⏳ Waiting 10 seconds for services to start..."
sleep 10

# Show service status
echo ""
echo "📊 Service Status:"
echo "=================="

# Backend status
if launchctl print gui/$(id -u)/com.fuelanalytics.backend 2>/dev/null | grep -q "state = running"; then
    echo "✅ Backend: Running"
    if lsof -i :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "   Port 8000: Listening"
    else
        echo "   ⚠️  Port 8000: Not listening yet (may still be starting)"
    fi
else
    echo "❌ Backend: Not running"
    echo "   Check: tail -20 logs/backend.error.log"
fi

# Wialon status
if launchctl print gui/$(id -u)/com.fuelanalytics.wialon 2>/dev/null | grep -q "state = running"; then
    echo "✅ Wialon: Running"
else
    echo "❌ Wialon: Not running"
    echo "   Check: tail -20 logs/wialon.error.log"
fi

# Frontend status  
if launchctl print gui/$(id -u)/com.fuelanalytics.frontend 2>/dev/null | grep -q "state = running"; then
    echo "✅ Frontend: Running"
    if lsof -i :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "   Port 3000: Listening"
    else
        echo "   ⚠️  Port 3000: Not listening yet (vite may still be compiling)"
    fi
else
    echo "❌ Frontend: Not running"
    echo "   Check: tail -20 ../Fuel-Analytics-Frontend/logs/frontend.error.log"
fi

echo ""
echo "📝 Log Files:"
echo "============="
echo "Backend:  tail -f logs/backend.log"
echo "          tail -f logs/backend.error.log"
echo "Wialon:   tail -f logs/wialon.log"
echo "          tail -f logs/wialon.error.log"
echo "Frontend: tail -f ../Fuel-Analytics-Frontend/logs/frontend.log"
echo "          tail -f ../Fuel-Analytics-Frontend/logs/frontend.error.log"

echo ""
echo "🎯 Useful Commands:"
echo "==================="
echo "Check status:    ./check_services.sh"
echo "Uninstall:       ./uninstall_services.sh"
echo ""
echo "Restart backend: launchctl kickstart -k gui/\$(id -u)/com.fuelanalytics.backend"
echo "Restart wialon:  launchctl kickstart -k gui/\$(id -u)/com.fuelanalytics.wialon"
echo "Restart frontend:launchctl kickstart -k gui/\$(id -u)/com.fuelanalytics.frontend"

echo ""
echo "✅ Installation complete!"
echo ""
echo "📖 Read SERVICES_README.md for detailed documentation"

