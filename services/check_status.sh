#!/bin/bash
# 📊 Script para verificar el estado de todos los servicios

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Estado de Fuel Analytics Stack                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

echo "🔍 Procesos corriendo:"
echo "─────────────────────────────────────────────────────────────"
ps aux | grep -E "(main.py|wialon_sync|vite)" | grep -v grep | awk '{printf "%-10s %-50s\n", $2, $11" "$12" "$13}'

echo ""
echo "🏥 Backend Health Check:"
echo "─────────────────────────────────────────────────────────────"
curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool | head -15 || echo "❌ Backend no responde"

echo ""
echo "🎨 Frontend Status:"
echo "─────────────────────────────────────────────────────────────"
# Detectar puerto de Vite
VITE_PORT=$(lsof -nP -iTCP -sTCP:LISTEN | grep node | grep -o ':\d\{4\}' | head -1 | tr -d ':')
if [ -n "$VITE_PORT" ]; then
    curl -s http://localhost:$VITE_PORT 2>&1 | head -5 | grep -q "html" && \
        echo "✅ Frontend OK en puerto $VITE_PORT (http://localhost:$VITE_PORT)" || \
        echo "❌ Frontend no responde en puerto $VITE_PORT"
else
    echo "❌ No se detectó puerto de Frontend"
fi

echo ""
echo "📁 Últimas líneas de logs:"
echo "─────────────────────────────────────────────────────────────"
echo "Backend (últimas 3 líneas):"
tail -3 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend.log 2>/dev/null || echo "  Sin logs"

echo ""
echo "Wialon (últimas 3 líneas):"
tail -3 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon.log 2>/dev/null || echo "  Sin logs"

echo ""
