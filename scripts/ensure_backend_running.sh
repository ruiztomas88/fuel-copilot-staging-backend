#!/bin/bash
# Script para asegurar que el backend esté corriendo
# Se puede ejecutar manualmente o programar con cron

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
PID_FILE="$BACKEND_DIR/logs/backend.pid"

# Verificar si el backend está corriendo
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "✅ Backend está corriendo en puerto 8000"
    exit 0
fi

echo "⚠️  Backend NO está corriendo, iniciando..."

# Matar proceso anterior si existe
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    kill -9 $OLD_PID 2>/dev/null || true
fi

# Iniciar backend
bash "$BACKEND_DIR/start_backend_daemon.sh"

sleep 5

# Verificar que inició
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "✅ Backend iniciado correctamente"
else
    echo "❌ Error: Backend no pudo iniciar"
    exit 1
fi
