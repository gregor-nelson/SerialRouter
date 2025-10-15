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
    # Get project root directory (parent of scripts folder)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Change to project root directory
    os.chdir(project_root)

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

    # Just use the spec file - it's simpler and less error-prone
    cmd = [
        "pyinstaller",
        "--clean" if clean else "",
        r".\scripts\serial_router.spec"
    ]

    # Remove empty strings
    cmd = [c for c in cmd if c]
    
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
