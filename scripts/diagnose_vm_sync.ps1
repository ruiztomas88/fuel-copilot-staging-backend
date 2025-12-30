# ============================================================================
# Diagnostic Script for Wialon Sync Service on Windows VM
# Run this in PowerShell to check if everything is working
# ============================================================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "WIALON SYNC DIAGNOSTIC SCRIPT" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Get current directory
$currentDir = Get-Location
Write-Host "Current directory: $currentDir" -ForegroundColor Yellow

# ============================================================================
# 1. CHECK PYTHON INSTALLATION
# ============================================================================
Write-Host "`n[1] Checking Python installation..." -ForegroundColor Green
try {
    $pythonVersion = python --version
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found or not in PATH" -ForegroundColor Red
    Write-Host "   Please install Python 3.7+ and add to PATH" -ForegroundColor Yellow
}

# ============================================================================
# 2. CHECK PYMYSQL DEPENDENCY
# ============================================================================
Write-Host "`n[2] Checking PyMySQL dependency..." -ForegroundColor Green
$pymysqlCheck = python -c "import pymysql; print('PyMySQL version:', pymysql.__version__)" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ $pymysqlCheck" -ForegroundColor Green
} else {
    Write-Host "❌ PyMySQL not installed" -ForegroundColor Red
    Write-Host "   Run: pip install pymysql" -ForegroundColor Yellow
}

# ============================================================================
# 3. CHECK IF SYNC SERVICE IS RUNNING
# ============================================================================
Write-Host "`n[3] Checking if Wialon sync service is running..." -ForegroundColor Green

# Check for NSSM service
$nssmService = Get-Service -Name "WialonSync" -ErrorAction SilentlyContinue
if ($nssmService) {
    if ($nssmService.Status -eq "Running") {
        Write-Host "✅ WialonSync service is RUNNING (NSSM)" -ForegroundColor Green
    } else {
        Write-Host "❌ WialonSync service exists but is NOT running (Status: $($nssmService.Status))" -ForegroundColor Red
        Write-Host "   Run: Start-Service WialonSync" -ForegroundColor Yellow
    }
} else {
    # Check for Scheduled Task
    $scheduledTask = Get-ScheduledTask -TaskName "WialonSyncService" -ErrorAction SilentlyContinue
    if ($scheduledTask) {
        $taskInfo = Get-ScheduledTaskInfo -TaskName "WialonSyncService"
        if ($taskInfo.LastTaskResult -eq 0) {
            Write-Host "✅ WialonSyncService scheduled task is running" -ForegroundColor Green
        } else {
            Write-Host "❌ WialonSyncService task exists but may have errors (Result: $($taskInfo.LastTaskResult))" -ForegroundColor Red
        }
    } else {
        # Check for running Python process
        $pythonProcess = Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.CommandLine -like "*wialon_full_sync_service*"}
        if ($pythonProcess) {
            Write-Host "✅ Python process running wialon_full_sync_service detected" -ForegroundColor Green
        } else {
            Write-Host "❌ Wialon sync service is NOT running" -ForegroundColor Red
            Write-Host "   No NSSM service, no Scheduled Task, and no Python process found" -ForegroundColor Yellow
            Write-Host "   Run: python wialon_full_sync_service.py" -ForegroundColor Yellow
        }
    }
}

# ============================================================================
# 4. CHECK LOG FILES
# ============================================================================
Write-Host "`n[4] Checking log files..." -ForegroundColor Green

if (Test-Path "wialon_sync.log") {
    $logSize = (Get-Item "wialon_sync.log").Length / 1KB
    Write-Host "✅ Log file found: wialon_sync.log ($([math]::Round($logSize, 2)) KB)" -ForegroundColor Green
    
    Write-Host "`n   Last 10 lines of log:" -ForegroundColor Cyan
    Get-Content "wialon_sync.log" -Tail 10 | ForEach-Object {
        if ($_ -match "❌") {
            Write-Host "   $_" -ForegroundColor Red
        } elseif ($_ -match "✅") {
            Write-Host "   $_" -ForegroundColor Green
        } else {
            Write-Host "   $_" -ForegroundColor Gray
        }
    }
    
    # Check for errors
    $errorCount = (Select-String -Path "wialon_sync.log" -Pattern "❌" | Measure-Object).Count
    if ($errorCount -gt 0) {
        Write-Host "`n   ⚠️  Found $errorCount error(s) in log" -ForegroundColor Yellow
    }
    
    # Check last sync time
    $lastSync = Select-String -Path "wialon_sync.log" -Pattern "Sync Cycle" | Select-Object -Last 1
    if ($lastSync) {
        Write-Host "`n   Last sync cycle: $($lastSync.Line)" -ForegroundColor Cyan
    }
} else {
    Write-Host "⚠️  Log file not found" -ForegroundColor Yellow
    Write-Host "   Service may not have started yet or is configured to log elsewhere" -ForegroundColor Gray
}

# ============================================================================
# 5. CHECK DATABASE CONNECTION
# ============================================================================
Write-Host "`n[5] Checking database connection..." -ForegroundColor Green

$dbCheckScript = @"
import pymysql
import sys

try:
    # Check local database
    conn = pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='tomas',
        database='fuel_copilot'
    )
    print('✅ Connected to local MySQL database (fuel_copilot)')
    
    with conn.cursor() as cursor:
        # Check tables exist
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['truck_sensors_cache', 'truck_trips', 'truck_speeding_events', 'truck_ignition_events']
        for table in required_tables:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                cursor.execute(f"SELECT MAX(created_at) FROM {table}" if table != 'truck_sensors_cache' else f"SELECT MAX(last_updated) FROM {table}")
                last_update = cursor.fetchone()[0]
                print(f'✅ Table {table}: {count} rows, Last update: {last_update}')
            else:
                print(f'❌ Table {table} NOT FOUND')
    
    conn.close()
    
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
"@

$dbCheckScript | python 2>&1

# ============================================================================
# 6. CHECK WIALON REMOTE CONNECTION
# ============================================================================
Write-Host "`n[6] Checking Wialon remote database connection..." -ForegroundColor Green

$wialonCheckScript = @"
import pymysql

try:
    conn = pymysql.connect(
        host='20.127.200.135',
        port=3306,
        user='wialonro',
        password='KjmAqwertY1#2024!@Wialon',
        database='wialon_collect',
        connect_timeout=5
    )
    print('✅ Connected to Wialon remote database')
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sensors")
        count = cursor.fetchone()[0]
        print(f'✅ Wialon sensors table has {count} rows')
        
        cursor.execute("SELECT COUNT(DISTINCT unit) FROM sensors")
        trucks = cursor.fetchone()[0]
        print(f'✅ Found {trucks} unique trucks in Wialon')
    
    conn.close()
    
except Exception as e:
    print(f'❌ Wialon connection failed: {e}')
    print('   Check network connectivity to 20.127.200.135:3306')
"@

$wialonCheckScript | python 2>&1

# ============================================================================
# 7. CHECK API ENDPOINTS
# ============================================================================
Write-Host "`n[7] Checking API endpoints..." -ForegroundColor Green

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8008/fuelAnalytics/api/v2/fleet/driver-behavior?days=7" -Method GET -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ API endpoint responding (Status: $($response.StatusCode))" -ForegroundColor Green
    
    $data = $response.Content | ConvertFrom-Json
    if ($data.trucks) {
        Write-Host "   Response contains $($data.trucks.Count) trucks" -ForegroundColor Cyan
    }
} catch {
    Write-Host "❌ API endpoint not responding" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "   Make sure FastAPI backend is running on port 8008" -ForegroundColor Yellow
}

# ============================================================================
# 8. RECOMMENDATIONS
# ============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "RECOMMENDATIONS" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "If you see ❌ errors above, try these solutions:`n" -ForegroundColor Yellow

Write-Host "1. If sync service is NOT running:" -ForegroundColor White
Write-Host "   → Start it: python wialon_full_sync_service.py" -ForegroundColor Gray
Write-Host "   → Or install as service: nssm install WialonSync python wialon_full_sync_service.py`n" -ForegroundColor Gray

Write-Host "2. If tables are empty:" -ForegroundColor White
Write-Host "   → Check if service is running (see above)" -ForegroundColor Gray
Write-Host "   → Check logs: Get-Content wialon_sync.log -Tail 50" -ForegroundColor Gray
Write-Host "   → Verify Wialon connection works`n" -ForegroundColor Gray

Write-Host "3. If Wialon connection fails:" -ForegroundColor White
Write-Host "   → Check firewall: Test-NetConnection -ComputerName 20.127.200.135 -Port 3306" -ForegroundColor Gray
Write-Host "   → Verify VPN/network access to Wialon server`n" -ForegroundColor Gray

Write-Host "4. If API not responding:" -ForegroundColor White
Write-Host "   → Check if FastAPI is running: Get-Process | Where-Object {`$_.ProcessName -like '*uvicorn*'}" -ForegroundColor Gray
Write-Host "   → Start API if needed`n" -ForegroundColor Gray

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "DIAGNOSTIC COMPLETE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
