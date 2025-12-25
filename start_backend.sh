#!/bin/bash

cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
source venv/bin/activate

# Primero, verificar que no hay otro servidor corriendo
lsof -ti :8000 | xargs kill -9 2>/dev/null
sleep 1

# Iniciar uvicorn directamente
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

