#!/bin/bash
# Script para reiniciar servicios de Fuel Analytics

echo "🔄 Reiniciando servicios de Fuel Analytics..."
echo ""

# Reiniciar backend
echo "🔄 Reiniciando backend..."
launchctl kickstart -k gui/$UID/com.fuelanalytics.backend

# Reiniciar wialon sync
echo "🔄 Reiniciando wialon sync..."
launchctl kickstart -k gui/$UID/com.fuelanalytics.wialon

# Reiniciar frontend
echo "🔄 Reiniciando frontend..."
launchctl kickstart -k gui/$UID/com.fuelanalytics.frontend

echo ""
echo "✅ Servicios reiniciados"
echo ""
echo "Verifica el estado con:"
echo "  launchctl list | grep fuelanalytics"
echo ""
