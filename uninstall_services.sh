#!/bin/bash
# Uninstall Fuel Analytics Services

set -e

echo "🛑 Uninstalling Fuel Analytics Services..."

# Stop services
echo "Stopping services..."
launchctl bootout gui/$(id -u)/com.fuelanalytics.backend 2>/dev/null || true
launchctl bootout gui/$(id -u)/com.fuelanalytics.wialon 2>/dev/null || true
launchctl bootout gui/$(id -u)/com.fuelanalytics.frontend 2>/dev/null || true

# Remove service files
echo "Removing service files..."
rm -f ~/Library/LaunchAgents/com.fuelanalytics.backend.plist
rm -f ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist
rm -f ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist

echo "✅ Services uninstalled"
echo ""
echo "Note: Log files are preserved in:"
echo "  ~/Desktop/Fuel-Analytics-Backend/logs/"
echo "  ~/Desktop/Fuel-Analytics-Frontend/logs/"
