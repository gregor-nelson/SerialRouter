@echo off
setlocal

echo Installing com0com binaries...

set "TARGET_DIR=C:\Program Files (x86)\com0com"
set "SOURCE_DIR=%~dp0"

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

if not exist "%SOURCE_DIR%PortRouter\" (
    echo ERROR: PortRouter folder not found in script directory.
    pause
    exit /b 1
)

if not exist "%SOURCE_DIR%VirtualPortManager\" (
    echo ERROR: VirtualPortManager folder not found in script directory.
    pause
    exit /b 1
)

echo Copying PortRouter folder to %TARGET_DIR%...
xcopy "%SOURCE_DIR%PortRouter\" "%TARGET_DIR%\PortRouter\" /E /I /Y >nul
if errorlevel 1 (
    echo ERROR: Failed to copy PortRouter folder. Please run as administrator.
    pause
    exit /b 1
)

echo Copying VirtualPortManager folder to %TARGET_DIR%...
xcopy "%SOURCE_DIR%VirtualPortManager\" "%TARGET_DIR%\VirtualPortManager\" /E /I /Y >nul
if errorlevel 1 (
    echo ERROR: Failed to copy VirtualPortManager folder. Please run as administrator.
    pause
    exit /b 1
)

echo Creating Start Menu shortcuts...

set "START_MENU_DIR=C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Serial Tools"

if not exist "%START_MENU_DIR%" (
    mkdir "%START_MENU_DIR%" 2>nul
    if errorlevel 1 (
        echo WARNING: Failed to create Start Menu folder. Shortcuts not created.
        goto :skip_shortcuts
    )
)

powershell -Command "& {$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%START_MENU_DIR%\Port Router.lnk'); $s.TargetPath = '%TARGET_DIR%\PortRouter\Port Router.exe'; $s.WorkingDirectory = '%TARGET_DIR%\PortRouter'; $s.Save()}" 2>nul

powershell -Command "& {$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%START_MENU_DIR%\Virtual Port Manager.lnk'); $s.TargetPath = '%TARGET_DIR%\VirtualPortManager\VirtualPortManager.exe'; $s.WorkingDirectory = '%TARGET_DIR%\VirtualPortManager'; $s.Save()}" 2>nul

echo Start Menu shortcuts created in: %START_MENU_DIR%

echo Creating desktop shortcut for Port Router...

set "DESKTOP_DIR=%PUBLIC%\Desktop"

powershell -Command "& {$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_DIR%\Port Router.lnk'); $s.TargetPath = '%TARGET_DIR%\PortRouter\Port Router.exe'; $s.WorkingDirectory = '%TARGET_DIR%\PortRouter'; $s.Save()}" 2>nul

if exist "%DESKTOP_DIR%\Port Router.lnk" (
    echo Desktop shortcut created: %DESKTOP_DIR%\Port Router.lnk
) else (
    echo WARNING: Failed to create desktop shortcut.
)

:skip_shortcuts
echo.
echo Installation completed successfully!
echo Folders installed to: %TARGET_DIR%
pause