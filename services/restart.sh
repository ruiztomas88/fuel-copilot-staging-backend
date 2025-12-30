#!/bin/bash
# Script para reiniciar todos los servicios

echo "🔄 Reiniciando servicios Fuel Analytics..."
echo ""

# Detener
echo "⏹️  Deteniendo servicios..."
launchctl stop com.fuelanalytics.backend
launchctl stop com.fuelanalytics.wialon
launchctl stop com.fuelanalytics.frontend

sleep 3

# Iniciar
echo "▶️  Iniciando servicios..."
launchctl start com.fuelanalytics.backend
launchctl start com.fuelanalytics.wialon
launchctl start com.fuelanalytics.frontend

echo ""
echo "⏳ Esperando 10 segundos para que inicien..."
sleep 10

echo ""
echo "✅ Reinicio completado. Verificando estado..."
echo ""

bash "$(dirname "$0")/status.sh"
