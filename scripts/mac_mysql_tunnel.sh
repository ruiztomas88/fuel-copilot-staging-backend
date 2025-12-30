#!/bin/bash
# ============================================================================
# SSH TUNNEL PARA MYSQL - CONECTAR MAC A VM WINDOWS
# ============================================================================

echo "🔐 Creando túnel SSH a la VM..."
echo ""
echo "Si te pide password de Windows, ingrésalo."
echo "Dejá esta terminal abierta mientras uses MySQL."
echo ""
echo "Luego en OTRA terminal ejecuta:"
echo "  mysql -h 127.0.0.1 -P 3307 -u fuel_admin -pFuelCopilot2025! fuel_copilot"
echo ""

# Reemplaza TU_USUARIO con tu usuario de Windows
ssh -L 3307:localhost:3306 TU_USUARIO@10.2.4.4
