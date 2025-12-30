#!/bin/bash
# Script para desinstalar servicios de Fuel Analytics

set -e

echo "🛑 Desinstalando servicios de Fuel Analytics..."
echo ""

# Descargar y eliminar servicios
echo "⏹️  Deteniendo servicios..."
launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.backend.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist 2>/dev/null || true

echo "🗑️  Eliminando configuraciones..."
rm -f ~/Library/LaunchAgents/com.fuelanalytics.backend.plist
rm -f ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist
rm -f ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist

echo ""
echo "✅ Servicios desinstalados exitosamente"
echo ""
echo "Los logs se mantienen en:"
echo "  - ~/Desktop/Fuel-Analytics-Backend/logs/"
echo "  - ~/Desktop/Fuel-Analytics-Frontend/logs/"
echo ""
