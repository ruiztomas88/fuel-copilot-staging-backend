#!/bin/bash
# Emergency Backend Recovery Script
# Run this if backend crashes or becomes unresponsive

BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
PYTHON_BIN="/opt/anaconda3/bin/python"
LOG_FILE="$BACKEND_DIR/recovery.log"

cd "$BACKEND_DIR" || exit 1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "═══════════════════════════════════════════════════════════"
log "🚨 EMERGENCY RECOVERY STARTED"
log "═══════════════════════════════════════════════════════════"

# Step 1: Kill all backend processes
log "🔪 Killing all backend processes..."
pkill -9 -f "python.*main.py"
pkill -9 -f "wialon_sync"
sleep 2

# Step 2: Check system resources
log "📊 Checking system resources..."
FREE_RAM=$(vm_stat | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
FREE_DISK=$(df -h / | awk 'NR==2 {print $4}')
log "   Free RAM pages: $FREE_RAM"
log "   Free Disk: $FREE_DISK"

# Step 3: Clear temp files
log "🧹 Cleaning temporary files..."
rm -f nohup.out
rm -f *.pyc
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Step 4: Backup current logs
log "💾 Backing up current logs..."
BACKUP_DIR="$BACKEND_DIR/logs/crash_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp *.log "$BACKUP_DIR/" 2>/dev/null
log "   Logs backed up to: $BACKUP_DIR"

# Step 5: Restart backend
log "🚀 Starting backend..."
nohup "$PYTHON_BIN" main.py > backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > backend.pid
log "   Backend PID: $BACKEND_PID"

# Step 6: Wait and verify
log "⏳ Waiting for backend to initialize (15 seconds)..."
sleep 15

# Check if process is running
if ps -p $BACKEND_PID > /dev/null 2>&1; then
    log "✅ Backend process is running"
    
    # Check health endpoint
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ]; then
        log "✅ Backend is responding to requests"
    else
        log "⚠️ Backend started but not responding correctly (HTTP $HTTP_CODE)"
    fi
else
    log "❌ Backend failed to start - check backend.log for errors"
fi

# Step 7: Restart wialon sync
log "🔄 Starting wialon sync..."
nohup "$PYTHON_BIN" wialon_sync_enhanced.py > wialon_sync.log 2>&1 &
WIALON_PID=$!
log "   Wialon sync PID: $WIALON_PID"

log "═══════════════════════════════════════════════════════════"
log "✅ RECOVERY COMPLETE"
log "═══════════════════════════════════════════════════════════"
log ""
log "📋 Next steps:"
log "   1. Check backend.log for any startup errors"
log "   2. Monitor monitor.log if using the monitor script"
log "   3. Verify frontend can connect to backend"
log ""
log "Crash logs archived in: $BACKUP_DIR"
