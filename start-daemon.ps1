$ErrorActionPreference = 'Stop'
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$MachinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$env:PATH = "$UserPath;$MachinePath"

Write-Host "Starting OpenClaw Daemon..."
openclaw daemon start

Write-Host "Checking OpenClaw Daemon status..."
openclaw daemon status
