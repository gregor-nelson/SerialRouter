"""
Resource Management for SerialRouter GUI
Handles theme loading, icon management, and asset paths.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QDir


class ResourceManager:
    """Centralized resource management for GUI assets."""
    
    def __init__(self):
        self._base_path = self._get_base_path()
        self._assets_path = self._base_path / "assets"
        self._themes_path = self._base_path / "src" / "gui" / "themes"
        self._icons_path = self._assets_path / "icons"
        
        # Ensure directories exist
        self._themes_path.mkdir(parents=True, exist_ok=True)
        
    def _get_base_path(self) -> Path:
        """Get the base path of the application."""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable - PyInstaller sets sys._MEIPASS
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller temp extraction folder
                return Path(sys._MEIPASS)
            else:
                # Fallback to executable directory
                return Path(sys.executable).parent
        else:
            # Running as script - go up from src/gui/resources.py to project root
            return Path(__file__).parent.parent.parent
    
    def get_theme_path(self, theme_name: str = "windows_theme.qss") -> Optional[Path]:
        """Get path to theme file."""
        theme_path = self._themes_path / theme_name
        if theme_path.exists():
            return theme_path
        return None
    
    def load_theme(self, theme_name: str = "windows_theme.qss") -> str:
        """Load theme stylesheet content."""
        theme_path = self.get_theme_path(theme_name)
        if theme_path and theme_path.exists():
            try:
                with open(theme_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Warning: Failed to load theme {theme_name}: {e}")
                return ""
        else:
            print(f"Warning: Theme file not found: {theme_name}")
            return ""
    
    def get_icon_path(self, icon_name: str, subfolder: str = "") -> Optional[Path]:
        """Get path to icon file."""
        if subfolder:
            icon_path = self._icons_path / subfolder / icon_name
        else:
            icon_path = self._icons_path / icon_name
            
        if icon_path.exists():
            return icon_path
        return None
    
    def load_icon(self, icon_name: str, subfolder: str = "") -> QIcon:
        """Load icon from assets."""
        icon_path = self.get_icon_path(icon_name, subfolder)
        if icon_path:
            return QIcon(str(icon_path))
        else:
            print(f"Warning: Icon not found: {icon_name}")
            return QIcon()  # Return empty icon as fallback
    
    def load_pixmap(self, icon_name: str, subfolder: str = "") -> QPixmap:
        """Load pixmap from assets."""
        icon_path = self.get_icon_path(icon_name, subfolder)
        if icon_path:
            return QPixmap(str(icon_path))
        else:
            print(f"Warning: Pixmap not found: {icon_name}")
            return QPixmap()  # Return empty pixmap as fallback
    
    def get_app_icon(self) -> QIcon:
        """Get the main application icon."""
        # Try ICO first, then SVG as fallback
        ico_icon = self.load_icon("app_icon.ico")
        if not ico_icon.isNull():
            return ico_icon
        
        svg_icon = self.load_icon("app_icon.svg")
        if not svg_icon.isNull():
            return svg_icon
            
        return QIcon()  # Empty icon if neither found
    
    def get_toolbar_icon(self, action_name: str) -> QIcon:
        """Get toolbar icon by action name."""
        icon_name = f"{action_name}.svg"
        return self.load_icon(icon_name, "toolbar")
    
    @property
    def assets_path(self) -> Path:
        """Get assets directory path."""
        return self._assets_path
    
    @property
    def icons_path(self) -> Path:
        """Get icons directory path."""
        return self._icons_path
    
    @property
    def themes_path(self) -> Path:
        """Get themes directory path."""
        return self._themes_path


# Global resource manager instance
resource_manager = ResourceManager()