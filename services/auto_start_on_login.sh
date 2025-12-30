#!/bin/bash
# 🚀 FUEL ANALYTICS - Auto-Start Script
# Este script se debe ejecutar al iniciar sesión
# Agrega este script a System Settings → General → Login Items

# Esperar a que el sistema esté listo
sleep 10

# Ejecutar el script de inicio
/bin/bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_all_services_v2.sh

# Registrar que se ejecutó
echo "$(date): Fuel Analytics services started" >> /Users/tomasruiz/fuel_analytics_startup.log
