@echo off
setlocal

echo ========================================
echo Serial Router Installation Script
echo ========================================
echo.

REM Determine base Serial directory (two levels up from script location)
set "SERIAL_BASE=%~dp0..\..\\"
echo Base directory: %SERIAL_BASE%
echo.

REM Define source directories
set "SERIAL_ROUTER_SRC=%SERIAL_BASE%SerialRouter\dist"
set "VIRTUAL_PORT_MGR_SRC=%SERIAL_BASE%VirtualPortManager\dist"
set "SERIAL_TERMINAL_SRC=%SERIAL_BASE%SerialTerminal\dist"

REM Define target directory
set "TARGET_DIR=C:\Program Files (x86)\com0com"

REM Validate com0com installation
if not exist "%TARGET_DIR%" (
    echo.
    echo ERROR: com0com directory not found!
    echo.
    echo Please install com0com first from:
    echo https://sourceforge.net/projects/com0com/
    echo.
    echo After installation, run this script again.
    pause
    exit /b 1
)

REM ========================================
REM Clean up previous installations
REM ========================================
echo Cleaning up previous installations...

if exist "%TARGET_DIR%\PortRouter" (
    echo   - Removing old Serial Router installation...
    rmdir /S /Q "%TARGET_DIR%\PortRouter" 2>nul
)

if exist "%TARGET_DIR%\Virtual Port Manager" (
    echo   - Removing old Virtual Port Manager installation...
    rmdir /S /Q "%TARGET_DIR%\Virtual Port Manager" 2>nul
)

if exist "%TARGET_DIR%\Serial Terminal" (
    echo   - Removing old Serial Terminal installation...
    rmdir /S /Q "%TARGET_DIR%\Serial Terminal" 2>nul
)

echo   - Cleanup complete - starting fresh installation
echo.

REM Validate source directories exist
echo Validating source directories...

if not exist "%SERIAL_ROUTER_SRC%\Serial Router.exe" (
    echo ERROR: Serial Router.exe not found at:
    echo %SERIAL_ROUTER_SRC%
    pause
    exit /b 1
)

if not exist "%VIRTUAL_PORT_MGR_SRC%\VirtualPortManager.exe" (
    echo ERROR: VirtualPortManager.exe not found at:
    echo %VIRTUAL_PORT_MGR_SRC%
    pause
    exit /b 1
)

if not exist "%SERIAL_TERMINAL_SRC%\SerialTerminal.exe" (
    echo ERROR: SerialTerminal.exe not found at:
    echo %SERIAL_TERMINAL_SRC%
    pause
    exit /b 1
)

if not exist "%SERIAL_TERMINAL_SRC%\SerialPortManager.exe" (
    echo ERROR: SerialPortManager.exe not found at:
    echo %SERIAL_TERMINAL_SRC%
    pause
    exit /b 1
)

echo All source files validated successfully.
echo.

REM ========================================
REM Install Serial Router (PortRouter)
REM ========================================
echo Installing Serial Router...

if not exist "%TARGET_DIR%\PortRouter" mkdir "%TARGET_DIR%\PortRouter"

copy "%SERIAL_ROUTER_SRC%\Serial Router.exe" "%TARGET_DIR%\PortRouter\Serial Router.exe" /Y >nul
if errorlevel 1 (
    echo ERROR: Failed to copy Serial Router. Please run as administrator.
    pause
    exit /b 1
)

echo   - Serial Router installed successfully
echo.

REM ========================================
REM Install Virtual Port Manager
REM ========================================
echo Installing Virtual Port Manager...

if not exist "%TARGET_DIR%\Virtual Port Manager" mkdir "%TARGET_DIR%\Virtual Port Manager"

REM Copy and rename VirtualPortManager.exe to Virtual Port Manager.exe
copy "%VIRTUAL_PORT_MGR_SRC%\VirtualPortManager.exe" "%TARGET_DIR%\Virtual Port Manager\Virtual Port Manager.exe" /Y >nul
if errorlevel 1 (
    echo ERROR: Failed to copy Virtual Port Manager. Please run as administrator.
    pause
    exit /b 1
)

echo   - Virtual Port Manager installed successfully
echo.

REM ========================================
REM Install Serial Terminal
REM ========================================
echo Installing Serial Terminal...

if not exist "%TARGET_DIR%\Serial Terminal" mkdir "%TARGET_DIR%\Serial Terminal"

REM Copy and rename SerialTerminal.exe to Serial Terminal.exe
copy "%SERIAL_TERMINAL_SRC%\SerialTerminal.exe" "%TARGET_DIR%\Serial Terminal\Serial Terminal.exe" /Y >nul
if errorlevel 1 (
    echo ERROR: Failed to copy Serial Terminal. Please run as administrator.
    pause
    exit /b 1
)

REM Copy SerialPortManager.exe (keep original name)
copy "%SERIAL_TERMINAL_SRC%\SerialPortManager.exe" "%TARGET_DIR%\Serial Terminal\SerialPortManager.exe" /Y >nul
if errorlevel 1 (
    echo ERROR: Failed to copy Serial Port Manager utility. Please run as administrator.
    pause
    exit /b 1
)

echo   - Serial Terminal installed successfully
echo.

REM ========================================
REM Create Start Menu Shortcuts
REM ========================================
echo Creating Start Menu shortcuts...

set "START_MENU_DIR=C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Serial Tools"

if not exist "%START_MENU_DIR%" (
    mkdir "%START_MENU_DIR%" 2>nul
    if errorlevel 1 (
        echo WARNING: Failed to create Start Menu folder. Shortcuts not created.
        goto :skip_shortcuts
    )
)

REM Serial Router shortcut
powershell -Command "& {$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%START_MENU_DIR%\Serial Router.lnk'); $s.TargetPath = '%TARGET_DIR%\PortRouter\Serial Router.exe'; $s.WorkingDirectory = '%TARGET_DIR%\PortRouter'; $s.Save()}" 2>nul

REM Virtual Port Manager shortcut
powershell -Command "& {$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%START_MENU_DIR%\Virtual Port Manager.lnk'); $s.TargetPath = '%TARGET_DIR%\Virtual Port Manager\Virtual Port Manager.exe'; $s.WorkingDirectory = '%TARGET_DIR%\Virtual Port Manager'; $s.Save()}" 2>nul

REM Serial Terminal shortcut
powershell -Command "& {$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%START_MENU_DIR%\Serial Terminal.lnk'); $s.TargetPath = '%TARGET_DIR%\Serial Terminal\Serial Terminal.exe'; $s.WorkingDirectory = '%TARGET_DIR%\Serial Terminal'; $s.Save()}" 2>nul

echo   - Start Menu shortcuts created in: %START_MENU_DIR%
echo.

REM ========================================
REM Create Desktop Shortcut
REM ========================================
echo Creating desktop shortcut for Serial Router...

set "DESKTOP_DIR=%PUBLIC%\Desktop"

powershell -Command "& {$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_DIR%\Serial Router.lnk'); $s.TargetPath = '%TARGET_DIR%\PortRouter\Serial Router.exe'; $s.WorkingDirectory = '%TARGET_DIR%\PortRouter'; $s.Save()}" 2>nul

if exist "%DESKTOP_DIR%\Serial Router.lnk" (
    echo   - Desktop shortcut created: %DESKTOP_DIR%\Serial Router.lnk
) else (
    echo WARNING: Failed to create desktop shortcut.
)
echo.

:skip_shortcuts

REM ========================================
REM Installation Complete
REM ========================================
echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo Installed applications:
echo   - Serial Router:         %TARGET_DIR%\PortRouter
echo   - Virtual Port Manager:  %TARGET_DIR%\Virtual Port Manager
echo   - Serial Terminal:       %TARGET_DIR%\Serial Terminal
echo.
echo Start Menu shortcuts created in: %START_MENU_DIR%
echo Desktop shortcut created for Serial Router
echo.
pause
