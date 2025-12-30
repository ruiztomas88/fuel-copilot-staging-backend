#!/bin/bash
# 🚀 Script para iniciar todos los servicios de Fuel Analytics
# Este script debe ejecutarse al iniciar sesión o cuando se necesite

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Iniciando Fuel Analytics Stack (Backend + Frontend)     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Directorio base
BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
FRONTEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Frontend"

# Crear directorios de logs si no existen
mkdir -p "$BACKEND_DIR/logs"
mkdir -p "$FRONTEND_DIR/logs"

# 1. Wialon Sync (sincronización de datos)
echo "📊 Iniciando Wialon Sync..."
cd "$BACKEND_DIR"
if pgrep -f "wialon_sync_enhanced.py" > /dev/null; then
    echo "   ✅ Wialon Sync ya está corriendo"
else
    /opt/anaconda3/bin/python wialon_sync_enhanced.py > logs/wialon.log 2>&1 &
    sleep 2
    echo "   ✅ Wialon Sync iniciado (PID: $!)"
fi

# 2. Backend API
echo "🔧 Iniciando Backend API..."
if pgrep -f "python.*main.py" > /dev/null; then
    echo "   ✅ Backend API ya está corriendo"
else
    # Cargar variables de entorno y ejecutar
    cd "$BACKEND_DIR"
    set -a
    [ -f .env ] && . .env
    set +a
    
    export PATH=/opt/anaconda3/bin:/usr/local/bin:/usr/bin:/bin
    export PYTHONPATH="$BACKEND_DIR"
    export PYTHONUNBUFFERED=1
    export DEV_MODE=false
    
    /opt/anaconda3/bin/python main.py > logs/backend.log 2>&1 &
    sleep 5
    echo "   ✅ Backend API iniciado (PID: $!)"
fi

# 3. Frontend (Vite dev server)
echo "🎨 Iniciando Frontend..."
cd "$FRONTEND_DIR"
if pgrep -f "vite.*dev" > /dev/null; then
    echo "   ✅ Frontend ya está corriendo"
else
    # Set PATH for node/npm
    export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
    /opt/homebrew/bin/npm run dev > logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    sleep 5
    
    # Verify it started
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "   ✅ Frontend iniciado (PID: $FRONTEND_PID)"
    else
        echo "   ❌ Frontend falló al iniciar, revisa logs/frontend.log"
    fi
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                     ✅ TODOS LOS SERVICIOS INICIADOS       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "📡 Backend API:  http://localhost:8000"
echo "🎨 Frontend:     http://localhost:5173"
echo "📊 Wialon Sync:  Corriendo en background"
echo ""
echo "Para verificar el estado:"
echo "  ps aux | grep -E '(main.py|wialon_sync|vite)' | grep -v grep"
echo ""
echo "Para detener todos los servicios:"
echo "  bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/stop_all_services.sh"
echo ""
