# ============================================================================
# INSTALL OPENSSH SERVER - ALTERNATIVE METHOD
# ============================================================================

Write-Host "🔐 Instalando OpenSSH Server..." -ForegroundColor Cyan

# Method 1: Via Optional Features (Windows Server/Pro)
try {
    Write-Host "`n📦 Intentando instalar via WindowsCapability..." -ForegroundColor Yellow
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 -ErrorAction Stop
    Write-Host "   ✅ Instalado via WindowsCapability" -ForegroundColor Green
}
catch {
    Write-Host "   ⚠️ WindowsCapability falló, intentando método alternativo..." -ForegroundColor Yellow
    
    # Method 2: Direct download and install
    $url = "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.5.0.0p1-Beta/OpenSSH-Win64.zip"
    $downloadPath = "$env:TEMP\OpenSSH-Win64.zip"
    $extractPath = "$env:ProgramFiles\OpenSSH"
    
    Write-Host "`n📥 Descargando OpenSSH desde GitHub..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $url -OutFile $downloadPath
    
    Write-Host "📂 Extrayendo archivos..." -ForegroundColor Yellow
    Expand-Archive -Path $downloadPath -DestinationPath $env:ProgramFiles -Force
    Rename-Item "$env:ProgramFiles\OpenSSH-Win64" "$extractPath" -Force -ErrorAction SilentlyContinue
    
    Write-Host "⚙️ Instalando servicio SSH..." -ForegroundColor Yellow
    & "$extractPath\install-sshd.ps1"
}

# Start and configure service
Write-Host "`n🚀 Iniciando servicio SSH..." -ForegroundColor Yellow
Start-Service sshd -ErrorAction SilentlyContinue
Set-Service -Name sshd -StartupType 'Automatic'

# Open firewall
Write-Host "`n🔥 Abriendo puerto 22 en Firewall..." -ForegroundColor Yellow
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -ErrorAction SilentlyContinue

# Verify
Write-Host "`n✅ VERIFICACIÓN:" -ForegroundColor Green
Write-Host "=" * 70
Get-Service sshd
Write-Host ""
netstat -an | Select-String ":22 "

Write-Host "`n📱 DESDE TU MAC:" -ForegroundColor Cyan
Write-Host "=" * 70
Write-Host "ssh devteam@172.210.11.234" -ForegroundColor White
Write-Host ""
Write-Host "Para MySQL tunnel:" -ForegroundColor Gray
Write-Host "ssh -L 3307:localhost:3306 devteam@172.210.11.234" -ForegroundColor Yellow
Write-Host ""
