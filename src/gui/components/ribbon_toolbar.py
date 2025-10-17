"""Ribbon-style toolbar for SerialRouter main commands."""

import os
from typing import Optional
from PyQt6.QtWidgets import (QToolBar, QWidget, QHBoxLayout, QVBoxLayout, 
                            QLabel, QPushButton, QFrame, QSizePolicy,
                            QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QAction, QPixmap, QFont
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtSvg import QSvgRenderer

from ..resources import resource_manager


class RibbonButton(QPushButton):
    """Large ribbon-style button."""
    
    def __init__(self, text: str, icon_name: str = None, parent=None):
        super().__init__(parent)
        self.setText(text)

        # Set icon if provided using resource manager
        if icon_name:
            icon = resource_manager.get_toolbar_icon(icon_name)
            if not icon.isNull():
                self.setIcon(icon)
                self.setIconSize(QSize(16, 16))

        # Set medium font weight for better readability
        font = self.font()
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)


class RibbonGroup(QFrame):
    """Group of related ribbon buttons."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setup_ui(title)
    
    def setup_ui(self, title: str):
        """Set up the group UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 2)
        
        # Buttons area
        self.buttons_widget = QWidget()
        self.buttons_layout = QHBoxLayout(self.buttons_widget)
        self.buttons_layout.setSpacing(4)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(self.buttons_widget)
    
    def add_button(self, button: RibbonButton):
        """Add a button to the group."""
        self.buttons_layout.addWidget(button)
    
    def add_separator(self):
        """Add a vertical separator."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.buttons_layout.addWidget(separator)


class RibbonToolbar(QToolBar):
    """Ribbon-style toolbar with SerialRouter commands."""
    
    # Signals for SerialRouter actions
    start_routing = pyqtSignal()
    stop_routing = pyqtSignal()
    configure_ports = pyqtSignal()
    launch_terminal = pyqtSignal()
    refresh_ports = pyqtSignal()
    view_stats = pyqtSignal()
    clear_log = pyqtSignal()
    show_help = pyqtSignal()
    show_about = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_actions()
    
    def setup_ui(self):
        """Set up the ribbon toolbar UI."""
        self.setMovable(False)
        self.setFloatable(False)
        self.setMinimumHeight(48)
        self.setMaximumHeight(48)
        
        # Main widget to hold ribbon groups
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Router Control group (primary actions)
        self.control_group = RibbonGroup("Router Control")
        
        self.start_button = RibbonButton("Start", "enable")
        self.start_button.setToolTip("Start serial port routing")
        # Use default button styling
        
        self.stop_button = RibbonButton("Stop", "disable")
        self.stop_button.setToolTip("Stop serial port routing")
        self.stop_button.setEnabled(False)
        # Use default button styling
        
        self.control_group.add_button(self.start_button)
        self.control_group.add_button(self.stop_button)
        
        # Configuration group
        self.config_group = RibbonGroup("Configuration")

        self.configure_button = RibbonButton("Setup", "configure")
        self.configure_button.setToolTip("Configure port settings")

        self.terminal_button = RibbonButton("Terminal", "terminal")
        self.terminal_button.setToolTip("Launch serial terminal")

        self.config_group.add_button(self.configure_button)
        self.config_group.add_button(self.terminal_button)
        
        # Monitoring group
        self.monitoring_group = RibbonGroup("Monitoring")
        
        self.stats_button = RibbonButton("Stats", "stats")
        self.stats_button.setToolTip("View routing statistics")
        
        self.refresh_button = RibbonButton("Refresh", "refresh")
        self.refresh_button.setToolTip("Refresh port list and status")
        
        self.monitoring_group.add_button(self.stats_button)
        self.monitoring_group.add_button(self.refresh_button)
        
        # System group
        self.system_group = RibbonGroup("System")

        self.clear_button = RibbonButton("Clear", "remove")
        self.clear_button.setToolTip("Clear activity log")

        self.help_button = RibbonButton("Help", "help")
        self.help_button.setToolTip("Show help information")

        self.about_button = RibbonButton("About", "info")
        self.about_button.setToolTip("About Serial Router")

        self.system_group.add_button(self.clear_button)
        self.system_group.add_button(self.help_button)
        self.system_group.add_button(self.about_button)
        
        # Add groups to main layout
        main_layout.addWidget(self.control_group)
        main_layout.addWidget(self.config_group)
        main_layout.addWidget(self.monitoring_group)
        main_layout.addWidget(self.system_group)
        main_layout.addStretch()
        
        # Add main widget to toolbar
        self.addWidget(main_widget)
    
    def setup_actions(self):
        """Set up button actions."""
        self.start_button.clicked.connect(self.start_routing.emit)
        self.stop_button.clicked.connect(self.stop_routing.emit)
        self.configure_button.clicked.connect(self.configure_ports.emit)
        self.terminal_button.clicked.connect(self.launch_terminal.emit)
        self.refresh_button.clicked.connect(self.refresh_ports.emit)
        self.stats_button.clicked.connect(self.view_stats.emit)
        self.clear_button.clicked.connect(self.clear_log.emit)
        self.help_button.clicked.connect(self.show_help.emit)
        self.about_button.clicked.connect(self.show_about.emit)
    
    def set_routing_state(self, is_routing: bool):
        """Update button states based on routing status."""
        self.start_button.setEnabled(not is_routing)
        self.stop_button.setEnabled(is_routing)
        
        # Disable configuration changes while routing
        self.configure_button.setEnabled(not is_routing)
    
    def set_busy(self, busy: bool):
        """Enable/disable buttons based on busy state."""
        buttons = [
            self.start_button, self.stop_button, self.configure_button,
            self.stats_button, self.clear_button, self.help_button, self.about_button
        ]

        for button in buttons:
            button.setEnabled(not busy)

        # Refresh button should always be available unless specifically busy
        self.refresh_button.setEnabled(not busy)
