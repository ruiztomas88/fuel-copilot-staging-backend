# ============================================
# LIMPIAR SERVICIOS DUPLICADOS Y DEPRECADOS
# ============================================

Write-Host "🔍 Verificando procesos Python..." -ForegroundColor Cyan

# 1. Matar sensor_cache_updater (DEPRECADO)
Write-Host "`n❌ Matando sensor_cache_updater (deprecado)..." -ForegroundColor Red
Get-Process python -ErrorAction SilentlyContinue | 
Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*sensor_cache_updater*' } |
ForEach-Object { 
    Write-Host "  Matando PID $($_.Id)" -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force 
}

# 2. Verificar wialon_sync_enhanced (debe haber SOLO 1)
Write-Host "`n🔍 Verificando wialon_sync_enhanced..." -ForegroundColor Cyan
$wialonProcs = Get-Process python -ErrorAction SilentlyContinue | 
Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*wialon_sync_enhanced*' }

if ($wialonProcs.Count -gt 1) {
    Write-Host "  ⚠️  HAY $($wialonProcs.Count) INSTANCIAS - Matando todas..." -ForegroundColor Yellow
    $wialonProcs | ForEach-Object { Stop-Process -Id $_.Id -Force }
    Write-Host "  ✅ Todas matadas. Reiniciar 1 manualmente con NSSM" -ForegroundColor Green
}
elseif ($wialonProcs.Count -eq 1) {
    Write-Host "  ✅ Solo 1 instancia corriendo (correcto)" -ForegroundColor Green
}
else {
    Write-Host "  ❌ NO HAY NINGUNA INSTANCIA - Iniciar con NSSM" -ForegroundColor Red
}

# 3. Verificar auto_update_daily_metrics (debe haber SOLO 1)
Write-Host "`n🔍 Verificando auto_update_daily_metrics..." -ForegroundColor Cyan
$dailyProcs = Get-Process python -ErrorAction SilentlyContinue | 
Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*auto_update_daily_metrics*' }

if ($dailyProcs.Count -gt 1) {
    Write-Host "  ⚠️  HAY $($dailyProcs.Count) INSTANCIAS - Matando duplicados..." -ForegroundColor Yellow
    $dailyProcs | Select-Object -Skip 1 | ForEach-Object { Stop-Process -Id $_.Id -Force }
    Write-Host "  ✅ Duplicados eliminados, 1 restante" -ForegroundColor Green
}
elseif ($dailyProcs.Count -eq 1) {
    Write-Host "  ✅ Solo 1 instancia corriendo (correcto)" -ForegroundColor Green
}
else {
    Write-Host "  ⚠️  NO HAY NINGUNA INSTANCIA - Considerar iniciar" -ForegroundColor Yellow
}

# 4. Verificar auto_backup_db (debe haber SOLO 1)
Write-Host "`n🔍 Verificando auto_backup_db..." -ForegroundColor Cyan
$backupProcs = Get-Process python -ErrorAction SilentlyContinue | 
Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*auto_backup_db*' }

if ($backupProcs.Count -gt 1) {
    Write-Host "  ⚠️  HAY $($backupProcs.Count) INSTANCIAS - Matando duplicados..." -ForegroundColor Yellow
    $backupProcs | Select-Object -Skip 1 | ForEach-Object { Stop-Process -Id $_.Id -Force }
    Write-Host "  ✅ Duplicados eliminados, 1 restante" -ForegroundColor Green
}
elseif ($backupProcs.Count -eq 1) {
    Write-Host "  ✅ Solo 1 instancia corriendo (correcto)" -ForegroundColor Green
}
else {
    Write-Host "  ⚠️  NO HAY NINGUNA INSTANCIA - Considerar iniciar" -ForegroundColor Yellow
}

# 5. Verificar uvicorn (API)
Write-Host "`n🔍 Verificando uvicorn (API Backend)..." -ForegroundColor Cyan
$uvicornProcs = Get-Process python -ErrorAction SilentlyContinue | 
Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*uvicorn*' }

if ($uvicornProcs.Count -eq 0) {
    Write-Host "  ❌ API NO ESTÁ CORRIENDO - Frontend no funcionará" -ForegroundColor Red
}
elseif ($uvicornProcs.Count -gt 1) {
    Write-Host "  ⚠️  HAY $($uvicornProcs.Count) INSTANCIAS - Matando duplicados..." -ForegroundColor Yellow
    $uvicornProcs | Select-Object -Skip 1 | ForEach-Object { Stop-Process -Id $_.Id -Force }
    Write-Host "  ✅ Duplicados eliminados, 1 restante" -ForegroundColor Green
}
else {
    Write-Host "  ✅ Solo 1 instancia corriendo (correcto)" -ForegroundColor Green
}

Write-Host "`n" -NoNewline
Write-Host "=" -ForegroundColor Cyan -NoNewline
Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host "✅ LIMPIEZA COMPLETADA" -ForegroundColor Green
Write-Host "=" -ForegroundColor Cyan -NoNewline
Write-Host "=" * 50 -ForegroundColor Cyan

# Mostrar resumen final
Write-Host "`n📊 ESTADO FINAL:" -ForegroundColor Cyan
Write-Host "  1. wialon_sync_enhanced: " -NoNewline
if ((Get-Process python -ErrorAction SilentlyContinue | Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*wialon_sync_enhanced*' }).Count -eq 1) {
    Write-Host "✅ OK" -ForegroundColor Green
}
else {
    Write-Host "❌ REINICIAR CON NSSM" -ForegroundColor Red
}

Write-Host "  2. uvicorn (API): " -NoNewline
if ((Get-Process python -ErrorAction SilentlyContinue | Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*uvicorn*' }).Count -eq 1) {
    Write-Host "✅ OK" -ForegroundColor Green
}
else {
    Write-Host "❌ INICIAR" -ForegroundColor Red
}

Write-Host "  3. auto_update_daily_metrics: " -NoNewline
if ((Get-Process python -ErrorAction SilentlyContinue | Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*auto_update_daily*' }).Count -eq 1) {
    Write-Host "✅ OK" -ForegroundColor Green
}
else {
    Write-Host "⚠️  OPCIONAL" -ForegroundColor Yellow
}

Write-Host "  4. auto_backup_db: " -NoNewline
if ((Get-Process python -ErrorAction SilentlyContinue | Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*auto_backup*' }).Count -eq 1) {
    Write-Host "✅ OK" -ForegroundColor Green
}
else {
    Write-Host "⚠️  OPCIONAL" -ForegroundColor Yellow
}

Write-Host "  5. sensor_cache_updater: " -NoNewline
if ((Get-Process python -ErrorAction SilentlyContinue | Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like '*sensor_cache*' }).Count -eq 0) {
    Write-Host "✅ DEPRECADO (correcto)" -ForegroundColor Green
}
else {
    Write-Host "❌ AÚN CORRIENDO - EJECUTAR SCRIPT NUEVAMENTE" -ForegroundColor Red
}
