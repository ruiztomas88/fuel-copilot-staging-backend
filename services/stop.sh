#!/bin/bash
# Script para detener todos los servicios

echo "⏹️  Deteniendo todos los servicios Fuel Analytics..."
echo ""

launchctl stop com.fuelanalytics.backend
echo "  ✓ Backend detenido"

launchctl stop com.fuelanalytics.wialon
echo "  ✓ Wialon detenido"

launchctl stop com.fuelanalytics.frontend
echo "  ✓ Frontend detenido"

echo ""
echo "✅ Todos los servicios han sido detenidos"
echo ""
echo "Para reiniciarlos: bash $(dirname "$0")/restart.sh"
echo "Para descargarlos completamente: bash $(dirname "$0")/uninstall.sh"
