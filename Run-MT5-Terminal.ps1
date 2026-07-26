# Run-MT5-Terminal.ps1 — PowerShell launcher for MT5 Institutional Terminal
Set-Location $PSScriptRoot
Write-Host "Launching MT5 Institutional Terminal..." -ForegroundColor Green

if (Test-Path "dist/MT5_Institutional_Terminal/MT5_Institutional_Terminal.exe") {
    Start-Process "dist/MT5_Institutional_Terminal/MT5_Institutional_Terminal.exe"
} else {
    python mt5_terminal/app.py
}
