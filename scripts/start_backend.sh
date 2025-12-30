#!/bin/bash
# Script wrapper para iniciar el backend con la configuración correcta

# Cambiar al directorio del backend
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend

# Configurar variables de entorno
export PATH="/opt/anaconda3/bin:$PATH"
export PYTHONPATH="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
export PYTHONUNBUFFERED=1
export DEV_MODE=false

# Ejecutar el backend (sin reload para producción)
exec /opt/anaconda3/bin/python main.py

