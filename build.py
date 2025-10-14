#!/usr/bin/env python3
"""
Build script for Serial Router using PyInstaller
"""

import subprocess
import sys
import os
import time
import shutil

def build(clean=False):
    """Build the Serial Router executable using PyInstaller"""
    # Try to remove existing build directory
    dist_dir = r".\dist\Serial Router"
    exe_path = os.path.join(dist_dir, "Serial Router.exe")
    
    if os.path.exists(dist_dir):
        try:
            shutil.rmtree(dist_dir)
            print("Removed existing build directory")
        except PermissionError:
            print("Warning: Existing build is locked. Close the application and try again.")
            return 1
    
    cmd = [
        "pyinstaller",
        "--distpath", "dist",
        "--workpath", "build", 
        "--specpath", ".",
        "--uac-admin",
    ]
    
    if clean:
        cmd.append("--clean")
    
    # Check if MinGW strip is available
    strip_available = shutil.which("strip") is not None
    
    cmd.extend([
        "--windowed", 
        "--onedir",
        "--optimize=1",  # Safe optimization level
        "--noupx",       # Disable UPX if present
        "--icon", r".\assets\icons\app_icon.ico",
        "--version-file", "version_info.txt",
        
        # Include all necessary data files (Windows uses semicolon separator)
        "--add-data", r"src;src",
        "--add-data", r"assets;assets",
        "--add-data", r"guide;guide",
        
        # Essential hidden imports for standard library modules
        "--hidden-import", "json",
        "--hidden-import", "threading",
        "--hidden-import", "logging",
        "--hidden-import", "logging.handlers",
        "--hidden-import", "queue",
        "--hidden-import", "datetime",
        "--hidden-import", "pathlib",
        "--hidden-import", "typing",
        "--hidden-import", "collections",
        "--hidden-import", "signal",
        "--hidden-import", "traceback",
        
        # PyQt6 - only include what we need
        "--collect-submodules", "PyQt6.QtCore",
        "--collect-submodules", "PyQt6.QtGui", 
        "--collect-submodules", "PyQt6.QtWidgets",
        "--collect-submodules", "PyQt6.QtSvg",
        "--collect-submodules", "PyQt6.QtSvgWidgets",
        "--collect-submodules", "serial",
        
        # Exclude heavy PyQt6 modules we don't need
        "--exclude-module", "PyQt6.QtWebEngine",
        "--exclude-module", "PyQt6.QtWebEngineCore", 
        "--exclude-module", "PyQt6.QtWebEngineWidgets",
        "--exclude-module", "PyQt6.QtMultimedia",
        "--exclude-module", "PyQt6.QtNetwork",
        "--exclude-module", "PyQt6.QtOpenGL",
        
        "--name", "Serial Router",
        r".\main.py"
    ])
    
    # Add strip flag only if available
    if strip_available:
        cmd.insert(-1, "--strip")  # Insert before main.py only
        print("MinGW strip found - using --strip for smaller binaries")
    else:
        print("MinGW strip not found - skipping --strip (install MinGW for smaller binaries)")
    
    print("Building Serial Router executable...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("Build completed successfully!")
        
        # Print size information
        if os.path.exists(dist_dir):
            total_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                           for dirpath, dirnames, filenames in os.walk(dist_dir)
                           for filename in filenames)
            print(f"Total build size: {total_size / (1024*1024):.1f} MB")
        
        print(f"Executable location: {exe_path}")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        return e.returncode

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Build Serial Router executable')
    parser.add_argument('--clean', action='store_true', help='Force clean build (slower)')
    args = parser.parse_args()
    
    sys.exit(build(clean=args.clean))
