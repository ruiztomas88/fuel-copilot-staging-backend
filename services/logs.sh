#!/bin/bash
# Script para ver logs de los servicios

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
FRONTEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Frontend"

echo "════════════════════════════════════════════════════════════"
echo "  📋 LOGS DE SERVICIOS FUEL ANALYTICS"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Selecciona qué logs quieres ver:"
echo ""
echo "  1) Backend (últimas 50 líneas)"
echo "  2) Backend - errores (últimas 50 líneas)"
echo "  3) Wialon (últimas 50 líneas)"
echo "  4) Wialon - errores (últimas 50 líneas)"
echo "  5) Frontend (últimas 50 líneas)"
echo "  6) Frontend - errores (últimas 50 líneas)"
echo "  7) Todos los logs en tiempo real (tail -f)"
echo "  8) Salir"
echo ""
read -p "Opción (1-8): " option

case $option in
    1)
        echo ""
        echo "📄 Backend log:"
        echo "────────────────────────────────────────────────────────────"
        tail -50 "$BACKEND_DIR/logs/backend.log"
        ;;
    2)
        echo ""
        echo "📄 Backend error log:"
        echo "────────────────────────────────────────────────────────────"
        tail -50 "$BACKEND_DIR/logs/backend.error.log" 2>/dev/null || echo "No hay errores registrados"
        ;;
    3)
        echo ""
        echo "📄 Wialon log:"
        echo "────────────────────────────────────────────────────────────"
        tail -50 "$BACKEND_DIR/logs/wialon.log"
        ;;
    4)
        echo ""
        echo "📄 Wialon error log:"
        echo "────────────────────────────────────────────────────────────"
        tail -50 "$BACKEND_DIR/logs/wialon.error.log" 2>/dev/null || echo "No hay errores registrados"
        ;;
    5)
        echo ""
        echo "📄 Frontend log:"
        echo "────────────────────────────────────────────────────────────"
        tail -50 "$FRONTEND_DIR/logs/frontend.log"
        ;;
    6)
        echo ""
        echo "📄 Frontend error log:"
        echo "────────────────────────────────────────────────────────────"
        tail -50 "$FRONTEND_DIR/logs/frontend.error.log" 2>/dev/null || echo "No hay errores registrados"
        ;;
    7)
        echo ""
        echo "📺 Monitoreando todos los logs en tiempo real..."
        echo "   Presiona Ctrl+C para salir"
        echo ""
        tail -f "$BACKEND_DIR/logs/backend.log" \
                "$BACKEND_DIR/logs/backend.error.log" \
                "$BACKEND_DIR/logs/wialon.log" \
                "$BACKEND_DIR/logs/wialon.error.log" \
                "$FRONTEND_DIR/logs/frontend.log" \
                "$FRONTEND_DIR/logs/frontend.error.log" 2>/dev/null
        ;;
    8)
        echo "Saliendo..."
        exit 0
        ;;
    *)
        echo "Opción inválida"
        exit 1
        ;;
esac

echo ""
