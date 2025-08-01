#!/usr/bin/env python3
"""
SerialRouter GUI Entry Point
Launch the PyQt6 GUI interface for SerialRouter.
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gui.main_window import main

if __name__ == "__main__":
    main()