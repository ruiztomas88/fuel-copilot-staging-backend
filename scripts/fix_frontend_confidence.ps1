# Fix Frontend - Confidence Display
# Ejecutar desde: C:\Users\devteam\Proyectos\Fuel-Analytics-Frontend

cd C:\Users\devteam\Proyectos\Fuel-Analytics-Frontend

Write-Host "=== FIXING FRONTEND CONFIDENCE DISPLAY ===" -ForegroundColor Cyan

# 1. MaintenanceDashboard.tsx
Write-Host "`n1. Procesando MaintenanceDashboard.tsx..." -ForegroundColor Yellow
$file1 = "src\pages\MaintenanceDashboard.tsx"
$content1 = Get-Content $file1 -Raw

# Añadir import
if ($content1 -notmatch 'confidenceHelpers') {
    $content1 = $content1 -replace '(import \{ useLanguage \})', "import { displayConfidence } from '../utils/confidenceHelpers';`r`n`$1"
    Write-Host "  ✅ Import añadido" -ForegroundColor Green
}

# Fix 3 ubicaciones
$content1 = $content1 -replace '`\(\(p\.confidence \* 100\)\.toFixed\(0\)\)`', 'displayConfidence(p.confidence).replace("%", "")'
$content1 = $content1 -replace '`\(\(summary\.avgConfidence \* 100\)\.toFixed\(0\)\)`', 'displayConfidence(summary.avgConfidence).replace("%", "")'
$content1 = $content1 -replace '\{`\(\(event\.confidence \* 100\)\.toFixed\(0\)\)`\}', '{displayConfidence(event.confidence).replace("%", "")}'

Set-Content $file1 -Value $content1 -NoNewline
Write-Host "  ✅ 3 fixes aplicados" -ForegroundColor Green

# 2. PredictiveMaintenanceUnified.tsx
Write-Host "`n2. Procesando PredictiveMaintenanceUnified.tsx..." -ForegroundColor Yellow
$file2 = "src\pages\PredictiveMaintenanceUnified.tsx"
if (Test-Path $file2) {
    $content2 = Get-Content $file2 -Raw
    
    # Añadir import
    if ($content2 -notmatch 'confidenceHelpers') {
        $content2 = $content2 -replace '(import.*useState)', "import { displayConfidence, styleConfidence } from '../utils/confidenceHelpers';`r`n`$1"
        Write-Host "  ✅ Import añadido" -ForegroundColor Green
    }
    
    # Fix width
    $content2 = $content2 -replace 'width: ``\$\{alert\.confidence \* 100\}%``', 'width: `${styleConfidence(alert.confidence)}%`'
    # Fix display
    $content2 = $content2 -replace '\{`\(\(alert\.confidence \* 100\)\.toFixed\(0\)\)`\}', '{displayConfidence(alert.confidence).replace("%", "")}'
    
    Set-Content $file2 -Value $content2 -NoNewline
    Write-Host "  ✅ 2 fixes aplicados" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Archivo no encontrado" -ForegroundColor Red
}

# 3. AlertSettings.tsx
Write-Host "`n3. Procesando AlertSettings.tsx..." -ForegroundColor Yellow
$file3 = "src\pages\AlertSettings.tsx"
if (Test-Path $file3) {
    $content3 = Get-Content $file3 -Raw
    
    # Añadir import
    if ($content3 -notmatch 'confidenceHelpers') {
        $content3 = $content3 -replace '(import.*useState)', "import { displayConfidence } from '../utils/confidenceHelpers';`r`n`$1"
        Write-Host "  ✅ Import añadido" -ForegroundColor Green
    }
    
    # Fix threshold display
    $content3 = $content3 -replace '\(settings\?\.thresholds\.theft_confidence_min \|\| 0\) \* 100\}%', 'displayConfidence(settings?.thresholds.theft_confidence_min)}'
    
    Set-Content $file3 -Value $content3 -NoNewline
    Write-Host "  ✅ 1 fix aplicado" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Archivo no encontrado" -ForegroundColor Red
}

Write-Host "`n=== FIXES COMPLETADOS ===" -ForegroundColor Cyan
Write-Host "Total archivos modificados: 3" -ForegroundColor Green
Write-Host "Total fixes aplicados: 6" -ForegroundColor Green
