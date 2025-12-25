#!/bin/bash

##############################################################################
# A/B TESTING SETUP SCRIPT
##############################################################################
# 
# Este script configura el sistema de A/B testing para validar
# algoritmos nuevos vs actuales antes de deployment a producción.
#
# Uso:
#   chmod +x ab_testing_setup.sh
#   ./ab_testing_setup.sh
#
##############################################################################

echo "════════════════════════════════════════════════════════════════════════"
echo "🧪 A/B TESTING SETUP"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================================================
# STEP 1: Verificar archivos necesarios
# ============================================================================

echo "📋 Step 1: Verificando archivos..."

required_files=(
    "ab_testing_framework.py"
    "ab_integration_tests.py"
    "ab_quick_tests.py"
    "ab_monitoring.py"
    "algorithm_improvements.py"
    "db_config.py"
    "sql_safe.py"
)

missing=0
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (MISSING)"
        missing=$((missing + 1))
    fi
done

if [ $missing -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Error: $missing archivos faltantes${NC}"
    exit 1
fi

echo ""

# ============================================================================
# STEP 2: Verificar dependencias Python
# ============================================================================

echo "📦 Step 2: Verificando dependencias Python..."

python3 -c "import pymysql; print('  ✓ pymysql')" 2>/dev/null || echo -e "  ${RED}✗ pymysql${NC}"
python3 -c "import numpy; print('  ✓ numpy')" 2>/dev/null || echo -e "  ${RED}✗ numpy${NC}"
python3 -c "import dotenv; print('  ✓ python-dotenv')" 2>/dev/null || echo -e "  ${RED}✗ python-dotenv${NC}"

echo ""

# ============================================================================
# STEP 3: Crear tablas de base de datos
# ============================================================================

echo "🗄️  Step 3: Creando tablas de base de datos..."

python3 ab_monitoring.py --setup 2>&1 | grep -E "(✅|ERROR)"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Tablas creadas correctamente${NC}"
else
    echo -e "${RED}❌ Error al crear tablas${NC}"
    exit 1
fi

echo ""

# ============================================================================
# STEP 4: Ejecutar quick tests
# ============================================================================

echo "🧪 Step 4: Ejecutando quick tests..."

python3 ab_quick_tests.py 2>&1 | grep -E "(Testing|PASS|FAIL|Error)" | head -20

echo ""

# ============================================================================
# STEP 5: Ejecutar un ciclo de monitoring
# ============================================================================

echo "📊 Step 5: Ejecutando primer ciclo de monitoring..."

python3 ab_monitoring.py --cycle 2>&1 | grep -E "(Testing|cycle|Error)" | head -10

echo ""

# ============================================================================
# STEP 6: Verificar resultados
# ============================================================================

echo "📋 Step 6: Verificando resultados en base de datos..."

# Contar registros en ab_monitoring_log
count=$(mysql -u root fuel_copilot_local -se "SELECT COUNT(*) FROM ab_monitoring_log" 2>/dev/null)

if [ -n "$count" ] && [ "$count" -gt 0 ]; then
    echo -e "  ${GREEN}✓${NC} ab_monitoring_log: $count registros"
else
    echo -e "  ${YELLOW}⚠${NC}  ab_monitoring_log: vacía (esperado si no hay datos recientes)"
fi

# Verificar alertas
alerts=$(mysql -u root fuel_copilot_local -se "SELECT COUNT(*) FROM ab_monitoring_alerts WHERE resolved = FALSE" 2>/dev/null)

if [ -n "$alerts" ]; then
    echo -e "  ${GREEN}✓${NC} ab_monitoring_alerts: $alerts activas"
else
    echo -e "  ${GREEN}✓${NC} ab_monitoring_alerts: 0 activas"
fi

echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "════════════════════════════════════════════════════════════════════════"
echo "✅ SETUP COMPLETADO"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "Próximos pasos:"
echo ""
echo "1️⃣  Ejecutar quick tests manualmente:"
echo "   python3 ab_quick_tests.py"
echo ""
echo "2️⃣  Ejecutar integration tests con datos reales:"
echo "   python3 ab_integration_tests.py"
echo ""
echo "3️⃣  Iniciar monitoring continuo (cada 60 min):"
echo "   python3 ab_monitoring.py --monitor --interval 60 &"
echo ""
echo "4️⃣  Ver reporte de últimos 7 días:"
echo "   python3 ab_monitoring.py --report 7"
echo ""
echo "5️⃣  Revisar alertas en DB:"
echo "   mysql -u root fuel_copilot_local -e 'SELECT * FROM ab_monitoring_alerts WHERE resolved = FALSE LIMIT 10'"
echo ""
echo "📚 Documentación completa: AB_TESTING_DOCUMENTATION.md"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
