#!/bin/bash
# 🚀 Script maestro de configuración de servicios Fuel Analytics
# Este script configura todo lo necesario para que el backend y frontend
# corran automáticamente 24/7 en macOS

set -e

echo "════════════════════════════════════════════════════════════"
echo "  🚀 CONFIGURACIÓN DE SERVICIOS FUEL ANALYTICS 24/7"
echo "════════════════════════════════════════════════════════════"
echo ""

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
FRONTEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Frontend"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

# Función para imprimir con color
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo "ℹ️  $1"
}

# Paso 1: Crear directorios de logs
echo ""
print_info "Paso 1: Creando directorios de logs..."
mkdir -p "$BACKEND_DIR/logs"
mkdir -p "$FRONTEND_DIR/logs"
print_success "Directorios de logs creados"

# Paso 2: Detener servicios existentes
echo ""
print_info "Paso 2: Deteniendo servicios existentes (si existen)..."
launchctl unload "$LAUNCH_AGENTS/com.fuelanalytics.backend.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS/com.fuelanalytics.wialon.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS/com.fuelanalytics.frontend.plist" 2>/dev/null || true
sleep 2
print_success "Servicios detenidos"

# Paso 3: Copiar archivos .plist actualizados
echo ""
print_info "Paso 3: Instalando configuraciones de servicios..."
cp "$BACKEND_DIR/services/com.fuelanalytics.backend.plist" "$LAUNCH_AGENTS/"
cp "$BACKEND_DIR/services/com.fuelanalytics.wialon.plist" "$LAUNCH_AGENTS/"
cp "$FRONTEND_DIR/services/com.fuelanalytics.frontend.plist" "$LAUNCH_AGENTS/"
print_success "Archivos .plist copiados"

# Paso 4: Cargar servicios
echo ""
print_info "Paso 4: Cargando servicios en launchd..."
launchctl load "$LAUNCH_AGENTS/com.fuelanalytics.backend.plist"
launchctl load "$LAUNCH_AGENTS/com.fuelanalytics.wialon.plist"
launchctl load "$LAUNCH_AGENTS/com.fuelanalytics.frontend.plist"
print_success "Servicios cargados"

# Paso 5: Esperar a que inicien
echo ""
print_info "Paso 5: Esperando a que los servicios inicien (15 segundos)..."
sleep 15

# Paso 6: Verificar estado
echo ""
print_info "Paso 6: Verificando estado de servicios..."
echo ""
echo "────────────────────────────────────────────────────────────"
echo "  📊 ESTADO DE SERVICIOS"
echo "────────────────────────────────────────────────────────────"

# Verificar backend
if lsof -ti:8000 > /dev/null 2>&1; then
    print_success "Backend API corriendo en puerto 8000"
    BACKEND_OK=1
else
    print_error "Backend API NO está corriendo"
    BACKEND_OK=0
fi

# Verificar wialon
if launchctl list | grep -q "com.fuelanalytics.wialon"; then
    print_success "Wialon Sync servicio activo"
    WIALON_OK=1
else
    print_error "Wialon Sync NO está activo"
    WIALON_OK=0
fi

# Verificar frontend
if lsof -ti:3000 > /dev/null 2>&1; then
    print_success "Frontend corriendo en puerto 3000"
    FRONTEND_OK=1
else
    print_error "Frontend NO está corriendo"
    FRONTEND_OK=0
fi

echo ""
echo "════════════════════════════════════════════════════════════"
if [ $BACKEND_OK -eq 1 ] && [ $WIALON_OK -eq 1 ] && [ $FRONTEND_OK -eq 1 ]; then
    print_success "¡TODOS LOS SERVICIOS ESTÁN CORRIENDO!"
    echo ""
    echo "🌐 Accede a tu dashboard en: http://localhost:3000"
    echo "📚 API Documentation: http://localhost:8000/docs"
    echo ""
    echo "Los servicios ahora se ejecutarán automáticamente:"
    echo "  • Al iniciar sesión en macOS"
    echo "  • Se reiniciarán automáticamente si fallan"
    echo ""
else
    print_warning "Algunos servicios no están corriendo correctamente"
    echo ""
    echo "Revisa los logs para más detalles:"
    echo "  Backend:  tail -f $BACKEND_DIR/logs/backend.error.log"
    echo "  Wialon:   tail -f $BACKEND_DIR/logs/wialon.error.log"
    echo "  Frontend: tail -f $FRONTEND_DIR/logs/frontend.error.log"
    echo ""
fi

echo "════════════════════════════════════════════════════════════"
echo ""
echo "📋 COMANDOS ÚTILES:"
echo ""
echo "  Ver estado:       bash $BACKEND_DIR/services/status.sh"
echo "  Reiniciar todo:   bash $BACKEND_DIR/services/restart.sh"
echo "  Detener todo:     bash $BACKEND_DIR/services/stop.sh"
echo "  Ver logs:         bash $BACKEND_DIR/services/logs.sh"
echo "  Desinstalar:      bash $BACKEND_DIR/services/uninstall.sh"
echo ""
echo "════════════════════════════════════════════════════════════"
