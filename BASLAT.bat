@echo off
chcp 65001 >nul
title U.L.T.R.O.N - Live Console & Logs
echo ======================================================
echo   U.L.T.R.O.N Sistem ve Canli Log Konsolu Baslatiliyor
echo ======================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BASLAT.ps1"
if errorlevel 1 (
    echo.
    echo [HATA] ULTRON beklenmedik sekilde kapandi veya hata olustu.
    echo Loglari yukaridan inceleyebilirsiniz.
    pause
)
pause
