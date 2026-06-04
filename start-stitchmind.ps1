# StitchMind Startup Orchestrator for Windows

$ProjectRoot = Resolve-Path "."

Clear-Host
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "              STITCHMIND: AI CONTEXT STITCHER             " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Initializing local services..." -ForegroundColor Gray

# 1. Start Python FastAPI backend in a separate terminal window
Write-Host "[1/2] Spawning FastAPI Backend (Port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\backend'; Write-Host 'Booting FastAPI Backend...' -ForegroundColor Cyan; .\\venv\\Scripts\\python run.py"

# 2. Start React Vite Dev server in a separate terminal window
Write-Host "[2/2] Spawning Vite Frontend (Port 5173)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\frontend'; Write-Host 'Booting Vite React Frontend...' -ForegroundColor Cyan; npm run dev"

Write-Host ""
Write-Host "Both processes have been spun up in separate background terminal windows." -ForegroundColor Yellow
Write-Host "You can close this orchestrator console. Keep the spawned windows open to monitor logs." -ForegroundColor Gray
Write-Host "----------------------------------------------------------" -ForegroundColor Cyan
Write-Host "StitchMind Web UI will be active at: http://localhost:5173" -ForegroundColor Green
Write-Host "StitchMind Swagger APIs active at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
