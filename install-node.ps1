$ErrorActionPreference = 'Stop'
Write-Host "Downloading Node.js..."
Invoke-WebRequest -Uri "https://nodejs.org/dist/v26.7.0/node-v26.7.0-win-x64.zip" -OutFile "node.zip"
Write-Host "Extracting Node.js..."
Expand-Archive -Path "node.zip" -DestinationPath "C:\Users\OSMBILISIM" -Force
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notmatch "node-v26\.7\.0-win-x64") {
    $NewPath = "C:\Users\OSMBILISIM\node-v26.7.0-win-x64;" + $UserPath
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
    Write-Host "Added Node.js to PATH."
} else {
    Write-Host "Node.js already in PATH."
}
