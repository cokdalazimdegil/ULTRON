$ErrorActionPreference = 'Stop'
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$MachinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$env:PATH = "$UserPath;$MachinePath"

Write-Host "Current Node version:"
node -v
Write-Host "Current NPM version:"
npm -v

npm config set engine-strict true
npm config set strict-ssl true
npm config delete force

Write-Host "Installing OpenClaw globally..."
npm -g install openclaw@latest
