#!/bin/bash

# ============================================================================
# Fuel Analytics - Inicio Manual con Logging Detallado
# ============================================================================
# Este script inicia todos los servicios con logging visible para debugging
# Cada servicio guarda logs con timestamp para diagnóstico
# ============================================================================

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
FRONTEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Frontend"
LOGS_DIR="$BACKEND_DIR/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Crear directorio de logs si no existe
mkdir -p "$LOGS_DIR"

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Fuel Analytics - Inicio con Logging Detallado            ║${NC}"
echo -e "${BLUE}║  Timestamp: $(date '+%Y-%m-%d %H:%M:%S')                        ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo ""

# ============================================================================
# 1. VERIFICAR DEPENDENCIAS
# ============================================================================
echo -e "${YELLOW}🔍 Verificando dependencias...${NC}"

if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo -e "${RED}❌ ERROR: Archivo .env no encontrado${NC}"
    exit 1
fi

if [ ! -f "$BACKEND_DIR/main.py" ]; then
    echo -e "${RED}❌ ERROR: main.py no encontrado${NC}"
    exit 1
fi

if [ ! -f "$BACKEND_DIR/wialon_sync_enhanced.py" ]; then
    echo -e "${RED}❌ ERROR: wialon_sync_enhanced.py no encontrado${NC}"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}❌ ERROR: Frontend directory no encontrado${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Todas las dependencias encontradas${NC}"
echo ""

# ============================================================================
# 2. WIALON SYNC
# ============================================================================
echo -e "${YELLOW}📊 Iniciando Wialon Sync Service...${NC}"
cd "$BACKEND_DIR"

# Verificar si ya está corriendo
WIALON_PID=$(pgrep -f "python.*wialon_sync_enhanced")
if [ -n "$WIALON_PID" ]; then
    echo -e "${YELLOW}⚠️  Wialon Sync ya está corriendo (PID: $WIALON_PID)${NC}"
else
    # Iniciar con logging
    python3 wialon_sync_enhanced.py > "$LOGS_DIR/wialon_${TIMESTAMP}.log" 2>&1 &
    WIALON_PID=$!
    sleep 3
    
    # Verificar que arrancó
    if ps -p $WIALON_PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Wialon Sync iniciado (PID: $WIALON_PID)${NC}"
        echo -e "   Log: $LOGS_DIR/wialon_${TIMESTAMP}.log"
        tail -5 "$LOGS_DIR/wialon_${TIMESTAMP}.log" | sed 's/^/   /'
    else
        echo -e "${RED}❌ ERROR: Wialon Sync falló al iniciar${NC}"
        echo -e "   Últimas líneas del log:"
        tail -10 "$LOGS_DIR/wialon_${TIMESTAMP}.log" | sed 's/^/   /'
    fi
fi
echo ""

# ============================================================================
# 3. BACKEND API
# ============================================================================
echo -e "${YELLOW}🔧 Iniciando Backend API...${NC}"

# Verificar si ya está corriendo
BACKEND_PID=$(pgrep -f "python.*main.py")
if [ -n "$BACKEND_PID" ]; then
    echo -e "${YELLOW}⚠️  Backend ya está corriendo (PID: $BACKEND_PID)${NC}"
    echo -e "   Matando proceso existente..."
    kill -9 $BACKEND_PID 2>/dev/null
    sleep 2
fi

# Cargar variables de entorno
source .env 2>/dev/null || echo "⚠️  No se pudo cargar .env"

# Iniciar con Anaconda Python y logging detallado
echo -e "   Usando: /opt/anaconda3/bin/python"
echo -e "   Directorio: $BACKEND_DIR"
echo -e "   Log: $LOGS_DIR/backend_${TIMESTAMP}.log"
echo ""

/opt/anaconda3/bin/python main.py > "$LOGS_DIR/backend_${TIMESTAMP}.log" 2>&1 &
BACKEND_PID=$!

# Esperar arranque (FastAPI tarda ~8-10 segundos)
echo -e "   Esperando arranque del servidor FastAPI..."
for i in {1..15}; do
    echo -n "."
    sleep 1
    
    # Verificar si el proceso sigue vivo
    if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo ""
        echo -e "${RED}❌ ERROR: Backend crasheó durante el arranque${NC}"
        echo -e "   Últimas 20 líneas del log:"
        tail -20 "$LOGS_DIR/backend_${TIMESTAMP}.log" | sed 's/^/   /'
        exit 1
    fi
    
    # Intentar conectar al health endpoint
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✅ Backend API respondiendo (PID: $BACKEND_PID)${NC}"
        break
    fi
done
echo ""

# Verificar que esté respondiendo
HEALTH_CHECK=$(curl -s http://localhost:8000/health 2>/dev/null)
if [ -n "$HEALTH_CHECK" ]; then
    echo -e "${GREEN}✅ Health check exitoso${NC}"
    echo "$HEALTH_CHECK" | python3 -m json.tool 2>/dev/null | head -8 | sed 's/^/   /'
else
    echo -e "${RED}❌ Backend no responde en puerto 8000${NC}"
    echo -e "   Últimas líneas del log:"
    tail -15 "$LOGS_DIR/backend_${TIMESTAMP}.log" | sed 's/^/   /'
fi
echo ""

# ============================================================================
# 4. FRONTEND (Vite Dev Server)
# ============================================================================
echo -e "${YELLOW}🎨 Iniciando Frontend...${NC}"
cd "$FRONTEND_DIR"

# Verificar si ya está corriendo
FRONTEND_PID=$(pgrep -f "vite.*dev")
if [ -n "$FRONTEND_PID" ]; then
    echo -e "${YELLOW}⚠️  Frontend ya está corriendo (PID: $FRONTEND_PID)${NC}"
else
    # Iniciar con npm y logging
    npm run dev > "$LOGS_DIR/frontend_${TIMESTAMP}.log" 2>&1 &
    FRONTEND_PID=$!
    
    # Esperar a que Vite esté listo (usualmente 2-4 segundos)
    echo -e "   Esperando a Vite dev server..."
    sleep 5
    
    # Detectar puerto dinámico
    FRONTEND_PORT=$(lsof -ti:3000,3001,3004,5173 2>/dev/null | head -1)
    if [ -n "$FRONTEND_PORT" ]; then
        ACTUAL_PORT=$(lsof -Pan -p $FRONTEND_PORT -i 2>/dev/null | grep LISTEN | awk '{print $9}' | cut -d: -f2)
        echo -e "${GREEN}✅ Frontend iniciado (PID: $FRONTEND_PID, Puerto: $ACTUAL_PORT)${NC}"
        echo -e "   Log: $LOGS_DIR/frontend_${TIMESTAMP}.log"
        echo -e "   URL: http://localhost:$ACTUAL_PORT"
    else
        echo -e "${YELLOW}⚠️  Frontend iniciado pero puerto no detectado${NC}"
        echo -e "   Verifica manualmente: lsof -i :3000 -i :5173"
    fi
fi
echo ""

# ============================================================================
# RESUMEN FINAL
# ============================================================================
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    RESUMEN DE SERVICIOS                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar procesos
echo -e "${GREEN}Procesos activos:${NC}"
ps aux | grep -E "(wialon_sync_enhanced|python.*main.py|vite.*dev)" | grep -v grep | awk '{printf "   PID %-6s  %s\n", $2, $11" "$12" "$13}'
echo ""

echo -e "${GREEN}Logs generados:${NC}"
echo -e "   Wialon:   $LOGS_DIR/wialon_${TIMESTAMP}.log"
echo -e "   Backend:  $LOGS_DIR/backend_${TIMESTAMP}.log"
echo -e "   Frontend: $LOGS_DIR/frontend_${TIMESTAMP}.log"
echo ""

echo -e "${GREEN}Monitoreo en tiempo real:${NC}"
echo -e "   Backend:  tail -f $LOGS_DIR/backend_${TIMESTAMP}.log"
echo -e "   Frontend: tail -f $LOGS_DIR/frontend_${TIMESTAMP}.log"
echo -e "   Wialon:   tail -f $LOGS_DIR/wialon_${TIMESTAMP}.log"
echo ""

echo -e "${GREEN}URLs:${NC}"
echo -e "   Backend API: ${BLUE}http://localhost:8000${NC}"
echo -e "   Frontend:    ${BLUE}http://localhost:3000${NC} (o puerto detectado)"
echo ""

echo -e "${YELLOW}Para ver logs de errores:${NC}"
echo -e "   grep -i error $LOGS_DIR/backend_${TIMESTAMP}.log"
echo -e "   grep -i error $LOGS_DIR/frontend_${TIMESTAMP}.log"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
