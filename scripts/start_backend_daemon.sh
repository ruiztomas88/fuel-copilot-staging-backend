#!/bin/bash
# Mantener el backend corriendo en background de forma permanente

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
LOG_FILE="$BACKEND_DIR/logs/backend.log"
ERROR_LOG="$BACKEND_DIR/logs/backend.error.log"
PID_FILE="$BACKEND_DIR/logs/backend.pid"

# Función para iniciar el backend
start_backend() {
    echo "$(date): Iniciando backend..." >> "$LOG_FILE"
    cd "$BACKEND_DIR"
    
    # Exportar variables de entorno
    export PATH="/opt/anaconda3/bin:$PATH"
    export PYTHONPATH="$BACKEND_DIR"
    export PYTHONUNBUFFERED=1
    export DEV_MODE=false
    
    # Iniciar con nohup
    nohup /opt/anaconda3/bin/python main.py >> "$LOG_FILE" 2>> "$ERROR_LOG" &
    
    # Guardar PID
    echo $! > "$PID_FILE"
    echo "$(date): Backend iniciado con PID $(cat $PID_FILE)" >> "$LOG_FILE"
}

# Verificar si ya está corriendo
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "$(date): Backend ya está corriendo con PID $OLD_PID" >> "$LOG_FILE"
        exit 0
    fi
fi

# Iniciar
start_backend
