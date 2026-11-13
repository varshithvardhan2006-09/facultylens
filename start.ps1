# Starts FacultyLens: checks the setup, then runs the API and the website in two windows
# and opens the site in your browser. Run from anywhere:  .\start.cmd   (or  .\start.ps1)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

function Fail($message) {
    Write-Host ""
    Write-Host "  Cannot start: $message" -ForegroundColor Red
    Write-Host ""
    exit 1
}

function PortInUse($port) {
    # The API listens on IPv4 and the website on IPv6 localhost, so try both.
    $targets = @(
        @([System.Net.Sockets.AddressFamily]::InterNetwork, [System.Net.IPAddress]::Loopback),
        @([System.Net.Sockets.AddressFamily]::InterNetworkV6, [System.Net.IPAddress]::IPv6Loopback)
    )
    foreach ($target in $targets) {
        $client = New-Object System.Net.Sockets.TcpClient($target[0])
        try {
            $client.Connect($target[1], $port)
            return $true
        } catch {
        } finally {
            $client.Close()
        }
    }
    return $false
}

Write-Host "Checking the setup..." -ForegroundColor Cyan

# 1. Python environment
if (-not (Test-Path $python)) {
    Fail "the backend virtual environment is missing. Follow 'Run Locally' in README.md once to create it."
}

# 2. Settings file
if (-not (Test-Path (Join-Path $backend ".env"))) {
    Fail "backend\.env is missing. Copy backend\.env.example to backend\.env and fill it in."
}

# 3. Node and frontend packages
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Fail "Node.js is not installed (npm not found). Install Node 22 from nodejs.org."
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "  Installing website packages (first run only)..."
    Push-Location $frontend
    npm install --no-fund --no-audit
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Fail "npm install failed." }
}

# 4. Database reachable (Atlas needs this computer's IP on its access list)
Push-Location $backend
$dbCheck = & $python -c "from pymongo import MongoClient; from app.config import get_settings; s=get_settings(); MongoClient(s.mongodb_uri, serverSelectionTimeoutMS=15000).admin.command('ping'); print('ok')" 2>&1
Pop-Location
if (($dbCheck | Select-Object -Last 1) -ne "ok") {
    Fail "the database is not reachable. If you use MongoDB Atlas, add this computer's IP in Atlas > Network Access. If you use a local MongoDB, make sure it is running."
}
Write-Host "  Database: connected"

# 5. Start the API (skip if it is already running)
if (PortInUse 8000) {
    Write-Host "  API: already running on port 8000"
} else {
    Start-Process powershell -WorkingDirectory $backend -ArgumentList @(
        "-NoExit", "-Command",
        "`$Host.UI.RawUI.WindowTitle = 'FacultyLens API'; & '$python' -m uvicorn app.main:app --reload --port 8000"
    )
    Write-Host "  API: starting..."
}

# 6. Start the website (skip if it is already running)
if (PortInUse 5173) {
    Write-Host "  Website: already running on port 5173"
} else {
    Start-Process powershell -WorkingDirectory $frontend -ArgumentList @(
        "-NoExit", "-Command",
        "`$Host.UI.RawUI.WindowTitle = 'FacultyLens website'; npm run dev"
    )
    Write-Host "  Website: starting..."
}

# 7. Wait until the API answers, then open the browser
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Fail "the API did not start within a minute. Look at the 'FacultyLens API' window for the error."
}

Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"
Write-Host ""
Write-Host "  FacultyLens is running at http://localhost:5173" -ForegroundColor Green
Write-Host "  To stop it, close the 'FacultyLens API' and 'FacultyLens website' windows."
Write-Host ""
