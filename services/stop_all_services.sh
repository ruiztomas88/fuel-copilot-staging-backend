#!/bin/bash
# 🛑 Script para detener todos los servicios de Fuel Analytics

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║    Deteniendo Fuel Analytics Stack                        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

echo "🛑 Deteniendo Backend API..."
pkill -f "python.*main.py"
sleep 2
echo "   ✅ Backend detenido"

echo "🛑 Deteniendo Wialon Sync..."
pkill -f "wialon_sync_enhanced.py"
sleep 2
echo "   ✅ Wialon Sync detenido"

echo "🛑 Deteniendo Frontend..."
pkill -f "vite.*dev"
sleep 2
echo "   ✅ Frontend detenido"

echo ""
echo "✅ Todos los servicios han sido detenidos"
echo ""
