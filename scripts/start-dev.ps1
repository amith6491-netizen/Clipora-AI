$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$MongoDataDir = Join-Path $Root ".mongod_data"

Write-Host "Starting Clipora AI development services..." -ForegroundColor Cyan

# Start local MongoDB if port 27017 is not already listening
$mongoUp = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 27017)
    $tcp.Close()
    $mongoUp = $true
} catch {
    $mongoUp = $false
}

if (-not $mongoUp) {
    $mongod = Get-Command mongod -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
    if (-not $mongod -and (Test-Path "C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe")) {
        $mongod = "C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe"
    }
    if ($mongod) {
        New-Item -ItemType Directory -Force -Path $MongoDataDir | Out-Null
        Start-Process -FilePath $mongod -ArgumentList "--dbpath", "`"$MongoDataDir`"", "--port", "27017", "--bind_ip", "127.0.0.1" -WindowStyle Minimized
        Write-Host "Started local MongoDB on 127.0.0.1:27017" -ForegroundColor Green
        Start-Sleep -Seconds 2
    } else {
        Write-Warning "MongoDB is not running on port 27017 and mongod.exe was not found. Start MongoDB before uploading."
    }
}

$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Backend virtual environment not found at $PythonExe. Run setup instructions in README.md first."
}

if (-not (Test-Path (Join-Path $BackendDir ".env")) -and (Test-Path (Join-Path $BackendDir ".env.example"))) {
    Copy-Item (Join-Path $BackendDir ".env.example") (Join-Path $BackendDir ".env")
}
if (-not (Test-Path (Join-Path $FrontendDir ".env")) -and (Test-Path (Join-Path $FrontendDir ".env.example"))) {
    Copy-Item (Join-Path $FrontendDir ".env.example") (Join-Path $FrontendDir ".env")
}

Start-Process -FilePath $PythonExe -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" -WorkingDirectory $BackendDir
Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $FrontendDir

Write-Host "Backend API: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Frontend UI: http://localhost:5173" -ForegroundColor Green
