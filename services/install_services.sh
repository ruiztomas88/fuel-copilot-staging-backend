#!/bin/bash
# Script para instalar servicios de Fuel Analytics en macOS

set -e

echo "🚀 Instalando servicios de Fuel Analytics..."
echo ""

# Crear directorios de logs
echo "📁 Creando directorios de logs..."
mkdir -p /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs
mkdir -p /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/logs

# Copiar archivos plist a LaunchAgents
echo "📋 Instalando configuraciones de servicios..."
cp /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/com.fuelanalytics.backend.plist ~/Library/LaunchAgents/
cp /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/com.fuelanalytics.wialon.plist ~/Library/LaunchAgents/
cp /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/services/com.fuelanalytics.frontend.plist ~/Library/LaunchAgents/

# Cargar servicios
echo "⚡ Cargando servicios..."
launchctl load ~/Library/LaunchAgents/com.fuelanalytics.backend.plist
launchctl load ~/Library/LaunchAgents/com.fuelanalytics.wialon.plist
launchctl load ~/Library/LaunchAgents/com.fuelanalytics.frontend.plist

echo ""
echo "✅ ¡Servicios instalados exitosamente!"
echo ""
echo "Los servicios ahora se ejecutarán automáticamente al iniciar sesión"
echo "y se reiniciarán automáticamente si fallan."
echo ""
echo "Comandos útiles:"
echo "  - Ver estado:    launchctl list | grep fuelanalytics"
echo "  - Ver logs:      tail -f ~/Desktop/Fuel-Analytics-Backend/logs/*.log"
echo "  - Detener todo:  bash services/stop_services.sh"
echo "  - Reiniciar:     bash services/restart_services.sh"
echo ""
