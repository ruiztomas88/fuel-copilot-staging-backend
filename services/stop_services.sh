#!/bin/bash
# Script para detener servicios de Fuel Analytics

echo "⏸️  Deteniendo servicios de Fuel Analytics..."
echo ""

# Detener servicios
launchctl stop com.fuelanalytics.backend
launchctl stop com.fuelanalytics.wialon
launchctl stop com.fuelanalytics.frontend

echo "✅ Servicios detenidos"
echo ""
echo "Para iniciarlos nuevamente:"
echo "  launchctl start com.fuelanalytics.backend"
echo "  launchctl start com.fuelanalytics.wialon"
echo "  launchctl start com.fuelanalytics.frontend"
echo ""
