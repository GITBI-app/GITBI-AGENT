<#
install.ps1 - Instalador local para GITBI Agent

Requisitos: Windows 10/11, PowerShell (incluido por defecto).

Este script realiza:
- Detecta Python 3.12 instalado y obtiene su ejecutable.
- Crea un entorno virtual `.venv` en la raíz del repo si no existe.
- Instala dependencias desde `requirements.txt` en el venv.
- Comprueba/descarga `newt.exe` desde los releases de GitHub (fosrl/newt)
- Valida el estado y crea un acceso directo en el Escritorio.

#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $ScriptRoot
try{
    Write-Info "Checking Python 3.12..."

    $pythonExe = $null

    # Preferir el lanzador py si está disponible
    try{
        $out = & py -3.12 -c "import sys, json; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out){ $pythonExe = $out.Trim() }
    } catch {}

    if (-not $pythonExe){
        # Fallback: probar 'python' y validar versión
        try{
            $ver = & python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver -like '3.12*'){
                $pythonExe = (& python -c "import sys; print(sys.executable)").Trim()
            }
        } catch {}
    }

    if (-not $pythonExe){
        Write-Err "Python 3.12 not found. Install Python 3.12 from: https://www.python.org/downloads/"
        Write-Err "The installer requires Python 3.12 (3.12.x series). Aborting without changes." 
        exit 1
    }

    Write-Info "Using Python: $pythonExe"

    # Crear venv si hace falta
    $venvPath = Join-Path $ScriptRoot ".venv"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (-not (Test-Path $venvPath)){
        Write-Info "Creating virtual environment at $venvPath..."
        & $pythonExe -m venv $venvPath
        if ($LASTEXITCODE -ne 0){ Write-Err "Failed to create the virtual environment."; exit 1 }
    } else {
        Write-Info "Virtual environment already exists: $venvPath"
    }

    if (-not (Test-Path $venvPython)){
        Write-Err "Interpreter not found inside the venv ($venvPython)."; exit 1
    }

    Write-Info "Updating pip and installing dependencies in the venv..."
    & $venvPython -m pip install --upgrade pip setuptools wheel | Write-Host
    try{
        if (Test-Path (Join-Path $ScriptRoot "requirements.txt")){
            & $venvPython -m pip install -r (Join-Path $ScriptRoot "requirements.txt")
        } elseif (Test-Path (Join-Path $ScriptRoot "pyproject.toml")){
            & $venvPython -m pip install -e .
        } else {
            Write-Warn "Neither requirements.txt nor pyproject.toml was found. Skipping dependency installation."
        }
    } catch {
        Write-Err "Error installing dependencies: $_"
        exit 1
    }

    # Comprobar newt
    $newtNames = @("newt.exe", "newt-windows-amd64.exe", "newt-windows.exe")
    $newtPath = Join-Path $ScriptRoot "newt.exe"
    $haveNewt = $false
    foreach ($n in $newtNames){
        $src = Join-Path $ScriptRoot $n
        if (Test-Path $src){
            # Evitar copiar el mismo archivo sobre sí mismo
            if ($src -ieq $newtPath){
                $haveNewt = $true
                break
            }
            Copy-Item -Path $src -Destination $newtPath -Force
            $haveNewt = $true
            break
        }
    }
    if (-not $haveNewt){
        Write-Info "newt not found locally. Checking GitHub releases..."
        try{
            $release = Invoke-RestMethod -UseBasicParsing -Uri "https://api.github.com/repos/fosrl/newt/releases/latest"
            $asset = $release.assets | Where-Object { ($_.name -match 'win' -or $_.name -match 'windows') -and ($_.name -match 'amd64' -or $_.name -match 'x64' -or $_.name -match '.exe') } | Select-Object -First 1
            if ($asset){
                $dl = $asset.browser_download_url
                Write-Info "Downloading $($asset.name) ..."
                Invoke-WebRequest -UseBasicParsing -Uri $dl -OutFile $newtPath

                # Si existe un asset de checksum en el release, intentar verificar
                $checksumAsset = $release.assets | Where-Object { $_.name -match 'sha256' -or $_.name -match 'sha256sum' } | Select-Object -First 1
                if ($checksumAsset){
                    $chUrl = $checksumAsset.browser_download_url
                    $chFile = Join-Path $ScriptRoot $checksumAsset.name
                    Invoke-WebRequest -UseBasicParsing -Uri $chUrl -OutFile $chFile
                    $computed = Get-FileHash -Algorithm SHA256 $newtPath
                    $chText = Get-Content $chFile -Raw
                    if ($chText -notmatch $computed.Hash){
                        Write-Warn "Checksum is available but does not match. The binary will be kept; proceed with caution."
                    } else {
                        Write-Info "Checksum verified successfully."
                    }
                } else {
                    Write-Warn "No checksum was found in the release. The binary was downloaded without additional verification."
                }
            } else {
                Write-Warn "No Newt asset for Windows/amd64 was found in the latest release. Please download it manually from https://github.com/fosrl/newt/releases"
            }
        } catch {
            Write-Warn "Error checking GitHub: $_. newt was not downloaded automatically."
        }
    } else {
        Write-Info "newt is already present in the repository."
    }

    if (-not (Test-Path $newtPath)){
        Write-Warn "newt.exe is not available. Some agent features may fail."
    } else {
        Write-Info "newt available at: $newtPath"
    }

    # Validaciones finales
    Write-Info "Validating installation..."
    $checksOk = $true
    if (-not (Test-Path $venvPython)){ Write-Err "venv interpreter not found: $venvPython"; $checksOk = $false }
    try{ & $venvPython -c "import pkgutil, sys; print('ok')" > $null } catch { Write-Err "The venv interpreter is not working correctly: $_"; $checksOk = $false }
    if (-not (Test-Path $newtPath)){ Write-Warn "Warning: newt.exe is not present." }

    if (-not $checksOk){ Write-Err "Checks failed. Fix the errors and run the installer again."; exit 1 }

    # Crear script de arranque (batch) idempotente
    $startBat = Join-Path $ScriptRoot "start-agent.bat"
    $batContent = "@echo off`r`ncd /d %~dp0`r`ncall .venv\Scripts\activate.bat`r`npython start.py`r`n"
    Set-Content -Path $startBat -Value $batContent -Encoding ASCII
    Write-Info "Generated start-agent.bat at $startBat"

    # Crear acceso directo en el Escritorio usando WScript (COM)
    $WshShell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop "GITBI Agent.lnk"
    $target = Join-Path $ScriptRoot "start-agent.bat"
    $shortcut = $WshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $target
    $shortcut.WorkingDirectory = $ScriptRoot
    # Usar icono del proyecto si existe
    $iconPath = Join-Path $ScriptRoot "assets\icon.ico"
    if (Test-Path $iconPath){ $shortcut.IconLocation = $iconPath } else { $shortcut.IconLocation = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe,0" }
    $shortcut.Description = "GITBI Agent (inicia el agente local)"
    $shortcut.Save()
    Write-Info "Shortcut created on the Desktop: $shortcutPath"

    # Validar .env y variables requeridas (no arrancar el servicio desde el instalador)
    $required = @("AGENT_BEARER_TOKEN","PANGOLIN_ID","PANGOLIN_SECRET")
    $envPath = Join-Path $ScriptRoot ".env"
    if (-not (Test-Path $envPath)){
        $samplePath = Join-Path $ScriptRoot ".env.sample"
        if (-not (Test-Path $samplePath)){
            $lines = @("# Copy to .env and fill in the required values")
            foreach ($k in $required){ $lines += "${k}=" }
            $lines += "# AGENT_PORT=8000"
            $lines += "# Other settings: PANGOLIN_SERVER, GITBI_SERVER_URL, AGENT_PUBLIC_URL"
            $lines | Out-File -FilePath $samplePath -Encoding utf8
        }
        Write-Warn ".env was not found; settings will be configured when the agent starts for the first time."
    } else {
        $missing = @()
        Get-Content $envPath | ForEach-Object {
            foreach ($k in $required){ if ($_ -match "^$k=") { $script:found = $true } }
        }
        foreach ($k in $required){
            $val = (& $venvPython -c "import os; print(os.getenv('$k') or '')") 2>$null
            if (-not $val){ $missing += $k }
        }
        if ($missing.Count -gt 0){
            Write-Warn ".env exists but required variables are missing: $($missing -join ', '); they will be configured when the agent starts for the first time."
            
        }
    }

    Write-Info "Installation complete. You can start the agent from the Desktop shortcut after configuring .env if needed."
    Write-Info "To stop the agent: open Task Manager and end the corresponding 'python.exe' process, or carefully use 'taskkill /IM python.exe /F'."

} finally {
    Pop-Location
}
