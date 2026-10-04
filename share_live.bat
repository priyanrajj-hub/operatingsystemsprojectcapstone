@echo off
echo ====================================================
echo   AI-DAX Lite - Live Public Sharing URL Generator
echo ====================================================
echo.
echo Make sure you have already run "start_dashboard.bat" first
echo so that your local processes are being monitored!
echo.
echo Generating a public HTTPS link to your local Dashboard...
npx localtunnel --port 8000
pause
