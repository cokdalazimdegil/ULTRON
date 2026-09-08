$ErrorActionPreference = 'Stop'
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$MachinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$env:PATH = "$UserPath;$MachinePath"

Write-Host "Installing OpenClaw Gateway..."
openclaw gateway install
Write-Host "Starting OpenClaw Gateway..."
openclaw gateway start
Write-Host "Checking OpenClaw Gateway status..."
openclaw gateway status
