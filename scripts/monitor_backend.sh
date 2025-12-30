#!/bin/bash
# Backend Health Monitor & Auto-Restart Script
# Monitors backend health and restarts if necessary
# Logs all events to monitor.log

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
PYTHON_BIN="/opt/anaconda3/bin/python"
BACKEND_SCRIPT="main.py"
HEALTH_URL="http://localhost:8000/health"
LOG_FILE="$BACKEND_DIR/monitor.log"
PID_FILE="$BACKEND_DIR/backend.pid"
MAX_FAILURES=3
FAILURE_COUNT=0
CHECK_INTERVAL=30

cd "$BACKEND_DIR" || exit 1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

is_backend_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

check_health() {
    # Check if backend responds to health endpoint
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL" 2>/dev/null)
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ]; then
        # 404 is OK if health endpoint doesn't exist - means server is up
        return 0
    else
        return 1
    fi
}

start_backend() {
    log "🚀 Starting backend..."
    
    # Kill any existing backend processes
    pkill -f "python.*main.py" 2>/dev/null
    sleep 2
    
    # Start backend in background
    nohup "$PYTHON_BIN" "$BACKEND_SCRIPT" > backend.log 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$PID_FILE"
    
    log "✅ Backend started with PID: $BACKEND_PID"
    
    # Wait for backend to initialize
    sleep 10
    
    if check_health; then
        log "✅ Backend health check passed"
        FAILURE_COUNT=0
        return 0
    else
        log "⚠️ Backend started but health check failed"
        return 1
    fi
}

log "═══════════════════════════════════════════════════════════"
log "🔍 Backend Monitor Started"
log "═══════════════════════════════════════════════════════════"

# Initial check
if ! is_backend_running; then
    log "⚠️ Backend not running, starting..."
    start_backend
fi

# Monitor loop
while true; do
    sleep "$CHECK_INTERVAL"
    
    if ! is_backend_running; then
        log "❌ Backend process died"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        
        if [ $FAILURE_COUNT -le $MAX_FAILURES ]; then
            log "🔄 Attempting restart ($FAILURE_COUNT/$MAX_FAILURES)..."
            start_backend
        else
            log "🚨 CRITICAL: Backend failed $MAX_FAILURES times, stopping monitor"
            log "🚨 Manual intervention required"
            exit 1
        fi
    elif ! check_health; then
        log "⚠️ Backend process running but health check failed"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        
        if [ $FAILURE_COUNT -le $MAX_FAILURES ]; then
            log "🔄 Restarting backend due to health check failure ($FAILURE_COUNT/$MAX_FAILURES)..."
            start_backend
        else
            log "🚨 CRITICAL: Backend health failed $MAX_FAILURES times, stopping monitor"
            exit 1
        fi
    else
        # Backend is healthy
        if [ $FAILURE_COUNT -gt 0 ]; then
            log "✅ Backend recovered, resetting failure count"
        fi
        FAILURE_COUNT=0
    fi
done
