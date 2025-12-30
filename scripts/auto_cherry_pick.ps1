# Auto Cherry-Pick con Testing
# Implementa commits no-MPG uno por uno con validación de tests

$ErrorActionPreference = "Continue"

# Lista de commits no-MPG (en orden cronológico)
$commits = @(
    "5cb2440",  # Test auto-approval
    "48aa4a3",  # Remove test file
    "45643e2",  # Test coverage improvements
    "bd6bbf2",  # FIX: Columnas SQL intake_temp_f + idle_hours
    "802a7ce",  # FIX: refuel_events schema
    "40916c2",  # FIX: Loss Analysis refuel_gallons
    "d2c68f6",  # FIX: Loss Analysis odom_delta_mi
    "a600a85",  # FIX: Command Center DTCs
    "2d5ec9f",  # AUTO-UPDATE: daily_truck_metrics
    "8243372",  # Fix: dtc_events schema Mac
    "a7f0b45",  # FIX: Registrar cost_router
    "08498cc",  # FIX: Cost router miles calculation
    "4373fe8",  # FIX: Sensor naming consistency ⭐
    "5e82fed",  # AUDIT: Wialon validation scripts
    "9362bdc",  # DEPRECATE: sensor_cache_updater
    "0f4dc59",  # VM: NSSM services
    "7f04c94",  # v5.17.1: Refuel detection fix
    "11eff18",  # Fix SQL recovery script
    "ed04c9b",  # v5.18.0: Theft speed gating
    "3bd0135",  # v5.19.0: Loss Analysis V2
    "3076312",  # v6.4.0: Loss Analysis ROI
    "2432e73",  # VM: refuel_events schema
    "6951d86",  # P0 bug fixes + test coverage
    "773d1d3",  # VM: Quick launch scripts
    "297fcb9",  # API: truck_details 37 sensors
    "14ca31f",  # API: truck_sensors_cache
    "0a00213",  # v7.1.0: Advanced algorithms + security
    "edbe38a",  # Fix: IndentationError
    "141baf7",  # Fix: predictive maintenance endpoints
    "f281a12",  # Fix: missing os import
    "7ac28de",  # Fix: SQL column mappings
    "53e67db",  # Fleet metrics endpoints
    "cde8b8a",  # Fleet metrics schema mapping
    "fbcbcc9",  # Merge: VM changes
    "1260d91",  # Fix: Remove odom_delta_mi
    "140b165",  # Docs: Action plan
    "dd94dbb"   # Security & ML v7.0.0
)

# Threshold mínimo de coverage
$MIN_COVERAGE = 50

Write-Host "`n=== AUTO CHERRY-PICK CON TESTING ===" -ForegroundColor Cyan
Write-Host "Total commits: $($commits.Count)" -ForegroundColor Yellow
Write-Host "Min coverage requerido: $MIN_COVERAGE%" -ForegroundColor Yellow
Write-Host ""

$successCount = 0
$failCount = 0
$skipCount = 0
$logFile = "cherry_pick_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

foreach ($commit in $commits) {
    Write-Host "`n[$($commits.IndexOf($commit) + 1)/$($commits.Count)] Procesando commit: $commit" -ForegroundColor Cyan
    
    # Obtener mensaje del commit
    $commitMsg = git log --oneline -1 $commit 2>$null
    Write-Host "  Mensaje: $commitMsg" -ForegroundColor Gray
    
    # Intentar cherry-pick
    Write-Host "  → Aplicando cherry-pick..." -ForegroundColor Yellow
    git cherry-pick $commit --no-commit 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ CONFLICTO detectado - Abortando" -ForegroundColor Red
        git cherry-pick --abort 2>&1 | Out-Null
        $failCount++
        Add-Content $logFile "FAIL (conflict): $commit - $commitMsg"
        continue
    }
    
    # Correr tests con coverage
    Write-Host "  → Corriendo tests + coverage..." -ForegroundColor Yellow
    $testOutput = & .\venv\Scripts\python.exe -m pytest --cov=. --cov-report=term-missing --tb=short -q 2>&1
    $testExitCode = $LASTEXITCODE
    
    # Parsear resultados
    $coverageMatch = $testOutput | Select-String "TOTAL\s+\d+\s+\d+\s+(\d+)%"
    if ($coverageMatch) {
        $coverage = [int]$coverageMatch.Matches.Groups[1].Value
    }
    else {
        $coverage = 0
    }
    
    $failedMatch = $testOutput | Select-String "(\d+) failed"
    if ($failedMatch) {
        $failures = [int]$failedMatch.Matches.Groups[1].Value
    }
    else {
        $failures = 0
    }
    
    # Evaluar resultado
    if ($testExitCode -eq 0 -and $coverage -ge $MIN_COVERAGE -and $failures -eq 0) {
        Write-Host "  ✓ TESTS PASSED - Coverage: $coverage%" -ForegroundColor Green
        git commit -m "Cherry-pick: $commitMsg" 2>&1 | Out-Null
        $successCount++
        Add-Content $logFile "SUCCESS ($coverage%): $commit - $commitMsg"
    }
    elseif ($testExitCode -eq 5) {
        # Exit code 5 = No tests collected (acceptable for docs/configs)
        Write-Host "  ⊘ NO TESTS - Aceptando commit (probablemente docs/config)" -ForegroundColor DarkYellow
        git commit -m "Cherry-pick: $commitMsg" 2>&1 | Out-Null
        $successCount++
        Add-Content $logFile "SUCCESS (no tests): $commit - $commitMsg"
    }
    else {
        Write-Host "  ✗ TESTS FAILED - Coverage: $coverage%, Failures: $failures" -ForegroundColor Red
        git reset --hard HEAD 2>&1 | Out-Null
        $failCount++
        Add-Content $logFile "FAIL (tests): $commit - Coverage: $coverage%, Failures: $failures - $commitMsg"
    }
    
    Start-Sleep -Seconds 1
}

Write-Host "`n=== RESUMEN ===" -ForegroundColor Cyan
Write-Host "✓ Exitosos: $successCount" -ForegroundColor Green
Write-Host "✗ Fallidos: $failCount" -ForegroundColor Red
Write-Host "⊘ Saltados: $skipCount" -ForegroundColor Yellow
Write-Host "`nLog guardado en: $logFile" -ForegroundColor Gray
