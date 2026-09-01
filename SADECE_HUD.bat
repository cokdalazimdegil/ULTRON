@echo off
chcp 65001 >nul
title U.L.T.R.O.N - Sadece HUD Modu
echo ======================================================
echo   U.L.T.R.O.N Sadece HUD Modunda Baslatiliyor
echo ======================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BASLAT.ps1" --hud
if errorlevel 1 (
    echo.
    echo [HATA] ULTRON beklenmedik sekilde kapandi veya hata olustu.
    pause
)
pause
