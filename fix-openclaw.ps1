$ErrorActionPreference = 'Stop'
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$MachinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$env:PATH = "$UserPath;$MachinePath"

Write-Host "Running OpenClaw doctor..."
openclaw doctor --fix

Write-Host "Reinstalling OpenClaw Gateway..."
openclaw gateway install --force

Write-Host "Starting OpenClaw Daemon..."
openclaw daemon start

Write-Host "Checking OpenClaw Daemon status..."
openclaw daemon status
