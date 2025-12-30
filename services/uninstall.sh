#!/bin/bash
# Script para desinstalar completamente los servicios

echo "════════════════════════════════════════════════════════════"
echo "  🗑️  DESINSTALAR SERVICIOS FUEL ANALYTICS"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "⚠️  ADVERTENCIA: Esto eliminará los servicios y dejarán de"
echo "   ejecutarse automáticamente."
echo ""
read -p "¿Estás seguro? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelado."
    exit 1
fi

echo ""
echo "Desinstalando servicios..."
echo ""

# Descargar y eliminar cada servicio
for service in backend wialon frontend; do
    echo "  Eliminando com.fuelanalytics.$service..."
    launchctl unload ~/Library/LaunchAgents/com.fuelanalytics.$service.plist 2>/dev/null || true
    rm -f ~/Library/LaunchAgents/com.fuelanalytics.$service.plist
    echo "    ✓ Eliminado"
done

echo ""
echo "✅ Servicios desinstalados correctamente"
echo ""
echo "Para reinstalarlos: bash $(dirname "$0")/setup_services.sh"
echo ""
