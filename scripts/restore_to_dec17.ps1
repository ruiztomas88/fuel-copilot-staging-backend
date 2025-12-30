# ============================================================================
# RESTORE SYSTEM TO DECEMBER 17 WORKING STATE (Windows VM)
# ============================================================================
# This script:
# 1. Stops NSSM services
# 2. Restores database structure (27 tables, removes 5 extras)
# 3. Restarts services with Dec 17 configuration
#
# Run on Windows VM as Administrator:
#   powershell -ExecutionPolicy Bypass -File restore_to_dec17.ps1
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "RESTORE TO DECEMBER 17 WORKING STATE (Windows VM)" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$DB_USER = "fuel_admin"
$DB_PASS = "FuelCopilot2025!"
$DB_NAME = "fuel_copilot"
$MYSQL_PATH = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
$BACKEND_DIR = "C:\Users\tomas\fuel-analytics-backend"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠ WARNING: Not running as Administrator. NSSM service control may fail." -ForegroundColor Yellow
    Write-Host "Please run PowerShell as Administrator for full functionality." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "STEP 1: Stopping services..." -ForegroundColor Yellow
# Stop NSSM services
nssm stop FuelCopilotSync 2>$null
nssm stop FuelCopilotSensorCache 2>$null
nssm stop FuelCopilotAPI 2>$null
Start-Sleep -Seconds 3
Write-Host "✓ Services stopped" -ForegroundColor Green
Write-Host ""

Write-Host "STEP 2: Backing up current database structure..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "fuel_copilot_structure_backup_$timestamp.sql"
$mysqldumpPath = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
if (Test-Path $mysqldumpPath) {
    & $mysqldumpPath -u$DB_USER -p$DB_PASS --no-data $DB_NAME > $backupFile 2>&1
    Write-Host "✓ Backup saved to $backupFile" -ForegroundColor Green
} else {
    Write-Host "⚠ mysqldump not found, skipping backup" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "STEP 3: Restoring database structure to Dec 17..." -ForegroundColor Yellow
if (Test-Path $MYSQL_PATH) {
    $sqlFile = Join-Path $BACKEND_DIR "restore_db_structure_dec17.sql"
    if (Test-Path $sqlFile) {
        Get-Content $sqlFile | & $MYSQL_PATH -u$DB_USER -p$DB_PASS $DB_NAME 2>&1 | Where-Object { $_ -notmatch "Warning" }
        Write-Host "✓ Database structure restored" -ForegroundColor Green
    } else {
        Write-Host "✗ SQL file not found: $sqlFile" -ForegroundColor Red
        Write-Host "Please ensure restore_db_structure_dec17.sql is in $BACKEND_DIR" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✗ MySQL not found at: $MYSQL_PATH" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "STEP 4: Verifying table count..." -ForegroundColor Yellow
$tableCountQuery = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$DB_NAME';"
$tableCount = & $MYSQL_PATH -u$DB_USER -p$DB_PASS -e $tableCountQuery 2>&1 | Select-Object -Last 1
Write-Host "Current table count: $tableCount"

if ($tableCount -eq "27" -or $tableCount -eq "28") {
    Write-Host "✓ Correct! Database has $tableCount tables (matching Dec 17)" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: Expected 27 tables, found $tableCount" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "STEP 5: Verifying extra tables were removed..." -ForegroundColor Yellow
$extraTablesQuery = "SHOW TABLES LIKE 'truck_ignition%';"
$extraTables = (& $MYSQL_PATH -u$DB_USER -p$DB_PASS $DB_NAME -e $extraTablesQuery 2>&1).Count
if ($extraTables -le 1) {
    Write-Host "✓ Extra tables removed successfully" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: Some extra tables still exist" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "STEP 6: Checking data in fuel_metrics..." -ForegroundColor Yellow
$fuelRecordsQuery = "SELECT COUNT(*) FROM fuel_metrics;"
$fuelRecords = & $MYSQL_PATH -u$DB_USER -p$DB_PASS $DB_NAME -e $fuelRecordsQuery 2>&1 | Select-Object -Last 1
Write-Host "fuel_metrics records: $fuelRecords"
Write-Host ""

Write-Host "STEP 7: Starting services with Dec 17 configuration..." -ForegroundColor Yellow
# Change to backend directory
Set-Location $BACKEND_DIR

# Create logs directory if it doesn't exist
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Start services via NSSM
Write-Host "Starting sensor_cache_updater service..." -ForegroundColor Cyan
nssm start FuelCopilotSensorCache 2>&1 | Out-Null
Start-Sleep -Seconds 3

Write-Host "Starting wialon_sync_enhanced service..." -ForegroundColor Cyan
nssm start FuelCopilotSync 2>&1 | Out-Null
Start-Sleep -Seconds 3

Write-Host "Starting FastAPI service..." -ForegroundColor Cyan
nssm start FuelCopilotAPI 2>&1 | Out-Null
Start-Sleep -Seconds 3

Write-Host "✓ All services started" -ForegroundColor Green
Write-Host ""

Write-Host "STEP 8: Verifying services are running..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
nssm status FuelCopilotSensorCache
nssm status FuelCopilotSync
nssm status FuelCopilotAPI
Write-Host ""

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "RESTORATION COMPLETE!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration restored to December 17, 2025:"
Write-Host "  • Database: 27 tables (5 extras removed)" -ForegroundColor White
Write-Host "  • sensor_cache_updater: 1-hour lookback (reverted from 12-hour)" -ForegroundColor White
Write-Host "  • wialon_reader: 1-hour lookback" -ForegroundColor White
Write-Host "  • All services: Running with Dec 17 settings" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Monitor logs: Get-Content logs\wialon_sync.log -Wait" -ForegroundColor White
Write-Host "  2. Check dashboard in 5 minutes" -ForegroundColor White
Write-Host "  3. Verify data: & `"$MYSQL_PATH`" -u$DB_USER -p$DB_PASS $DB_NAME -e 'SELECT MAX(timestamp_utc) FROM fuel_metrics;'" -ForegroundColor White
Write-Host ""
Write-Host "Service status:" -ForegroundColor Cyan
Write-Host "  • nssm status FuelCopilotSensorCache" -ForegroundColor White
Write-Host "  • nssm status FuelCopilotSync" -ForegroundColor White
Write-Host "  • nssm status FuelCopilotAPI" -ForegroundColor White
Write-Host ""
Write-Host "Log files:" -ForegroundColor Cyan
Write-Host "  • sensor_cache_updater: logs\sensor_cache_updater.log" -ForegroundColor White
Write-Host "  • wialon_sync: logs\wialon_sync.log" -ForegroundColor White
Write-Host "  • FastAPI: logs\fastapi.log" -ForegroundColor White
Write-Host ""
