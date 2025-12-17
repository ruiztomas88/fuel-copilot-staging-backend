#!/bin/bash
"""
🚀 DEPLOY UNIVERSAL SENSOR FIX
================================
Script para deployar el fix completo de sensores en la VM

Ejecutar desde la VM:
    bash deploy_sensor_fix.sh
"""

set -e  # Exit on error

echo "🚀 Starting Universal Sensor Fix Deployment"
echo "============================================"
echo ""

# 1. Backup current state
echo "📦 Step 1: Creating backup..."
mysqldump -u root -ptomas fuel_copilot truck_sensors_cache > /tmp/truck_sensors_cache_backup_$(date +%Y%m%d_%H%M%S).sql
echo "✅ Backup created"
echo ""

# 2. Run migration
echo "🔧 Step 2: Running database migration..."
cd /var/fuel-analytics-backend
python3 migrations/add_all_missing_sensors.py
echo "✅ Migration complete"
echo ""

# 3. Check which service is running
echo "🔍 Step 3: Checking active sync service..."
if systemctl is-active --quiet wialon_full_sync; then
    SYNC_SERVICE="wialon_full_sync"
    echo "✅ Found: wialon_full_sync service"
elif systemctl is-active --quiet sensor_cache_updater; then
    SYNC_SERVICE="sensor_cache_updater"
    echo "⚠️  Found: sensor_cache_updater (old service)"
    echo "   Will switch to wialon_full_sync"
else
    echo "❌ No sync service found!"
    echo "   Creating wialon_full_sync service..."
    SYNC_SERVICE="wialon_full_sync"
fi
echo ""

# 4. Stop old service if needed
if systemctl is-active --quiet sensor_cache_updater; then
    echo "🛑 Step 4a: Stopping old sensor_cache_updater..."
    sudo systemctl stop sensor_cache_updater
    sudo systemctl disable sensor_cache_updater
    echo "✅ Old service stopped"
fi

# 5. Restart sync service
echo "🔄 Step 5: Restarting $SYNC_SERVICE..."
sudo systemctl restart $SYNC_SERVICE
sleep 2
echo "✅ Service restarted"
echo ""

# 6. Check service status
echo "📊 Step 6: Checking service status..."
sudo systemctl status $SYNC_SERVICE --no-pager -l | head -20
echo ""

# 7. Monitor logs
echo "📋 Step 7: Monitoring logs (30 seconds)..."
echo "   Press Ctrl+C to stop monitoring early"
timeout 30 tail -f /var/log/wialon_sync.log || true
echo ""

# 8. Verify data
echo "✅ Step 8: Verifying sensor data..."
mysql -u root -ptomas fuel_copilot -e "
SELECT 
    truck_id,
    odometer_mi,
    def_temp_f,
    throttle_position_pct,
    transmission_temp_f,
    heading_deg,
    last_update
FROM truck_sensors_cache 
LIMIT 3;
" || echo "⚠️  Data check failed - may need to wait for first sync"
echo ""

echo "============================================"
echo "✅ Deployment Complete!"
echo ""
echo "📝 Next Steps:"
echo "   1. Wait 30-60 seconds for first sync"
echo "   2. Open dashboard and check 3 random trucks"
echo "   3. Verify odometer shows value (not N/A)"
echo "   4. Verify all sensors visible"
echo ""
echo "🔍 Monitor logs:"
echo "   tail -f /var/log/wialon_sync.log"
echo ""
echo "🔙 Rollback (if needed):"
echo "   mysql -u root -ptomas fuel_copilot < /tmp/truck_sensors_cache_backup_*.sql"
echo "   sudo systemctl restart $SYNC_SERVICE"
echo ""
