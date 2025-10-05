
import sys
import json
import logging
import subprocess
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QTextEdit, QFrame, QGroupBox, 
    QGridLayout, QSpinBox, QProgressBar, QSplitter, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QIcon, QAction

import serial.tools.list_ports
from src.core.router_engine import SerialRouterCore
from src.core.port_enumerator import PortEnumerator, PortType
from src.gui.resources import resource_manager
from src.gui.components import RibbonToolbar, ConnectionDiagramWidget, EnhancedStatusWidget
from src.gui.components.dialogs.about_dialog import AboutDialog


class LogHandler(logging.Handler):
    """Custom logging handler that emits signals for GUI display."""
    
    def __init__(self):
        super().__init__()
        self.log_signal = None
        
    def emit(self, record):
        if self.log_signal:
            msg = self.format(record)
            self.log_signal.emit(msg)


class RouterControlThread(QThread):
    """QThread wrapper for SerialRouterCore operations to prevent GUI blocking."""
    
    operation_complete = pyqtSignal(bool, str)  # success, message
    
    def __init__(self):
        super().__init__()
        self.operation = None
        self.router_core = None
        
    def set_operation(self, operation: str, router_core: SerialRouterCore):
        """Set the operation to perform: 'start' or 'stop'."""
        self.operation = operation
        self.router_core = router_core
        
    def run(self):
        """Execute the router operation in background thread."""
        try:
            if self.operation == 'start':
                success = self.router_core.start()
                if success:
                    self.operation_complete.emit(True, "Router started successfully")
                else:
                    self.operation_complete.emit(False, "Router failed to start - check port connections")
            elif self.operation == 'stop':
                self.router_core.stop()
                self.operation_complete.emit(True, "Router stopped successfully")
            else:
                self.operation_complete.emit(False, f"Unknown operation: {self.operation}")
                
        except Exception as e:
            self.operation_complete.emit(False, f"Operation failed: {str(e)}")
        finally:
            # Critical: Clear router reference to prevent memory leaks
            self.router_core = None


class SerialRouterMainWindow(QMainWindow):
    """Main GUI window for SerialRouter application."""
    
    # Define signal for log messages
    log_message_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # Core components
        self.router_core: Optional[SerialRouterCore] = None
        self.control_thread: Optional[RouterControlThread] = None
        self.log_handler: Optional[LogHandler] = None
        self._router_state_lock = threading.Lock()  # Thread synchronisation to prevent concurrent state modification during router operations
        self._router_state_changing = False
        self._initializing = True  # Flag to suppress validation warnings during startup
        
        # Monitoring
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        
        # Statistics tracking
        self.last_bytes_transferred = {}
        self.last_update_time = datetime.now()
        
        # Initialize port enumerator for robust port detection
        self.port_enumerator = PortEnumerator()
        
        # System tray setup
        self.tray_icon = None
        self.setup_system_tray()
        
        # Initialize UI
        self.init_ui()
        self.setup_logging()
        self.apply_theme()
        self.refresh_available_ports()

        # Load saved configuration if available
        self.load_config()

        # Update port tooltips with paired port detection
        self._update_port_tooltips()

        # Update connection diagram with initial port configuration
        if self.connection_diagram:
            port1, port2 = self._get_selected_outgoing_ports()
            com0com_ports = self.port_enumerator.get_com0com_ports()
            com0com_names = [p.port_name for p in com0com_ports]
            self.connection_diagram.set_outgoing_ports(port1, port2, com0com_names)

        # Initialization complete - enable validation warnings
        self._initializing = False

        # Connect log signal to handler
        self.log_message_signal.connect(self.add_log_message)

        # Start status monitoring
        self.status_timer.start(1000)  # 1 second updates
        
    def setup_system_tray(self):
        """Setup system tray icon and menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
            
        # Create tray icon using app icon
        app_icon = resource_manager.get_app_icon()
        if app_icon.isNull():
            return
            
        self.tray_icon = QSystemTrayIcon(app_icon, self)
        
        # Create context menu
        tray_menu = QMenu()
        
        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.show_normal)
        tray_menu.addAction(restore_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.perform_shutdown)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Set tooltip
        self.tray_icon.setToolTip("SerialRouter v2.0")
        
        # Show tray icon
        self.tray_icon.show()
        
    def tray_icon_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_normal()
            
    def show_normal(self):
        """Restore window from tray."""
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
        
    def quit_application(self):
        """Quit the application completely."""
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Serial Router")
        self.setMinimumSize(880, 600)
        # Don't set maximum size to preserve maximize functionality
        self.resize(880, 600)
        
        
        # Set application icon
        app_icon = resource_manager.get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        
        # Create ribbon toolbar
        self.ribbon = RibbonToolbar()
        self.addToolBar(self.ribbon)
        
        # Connect ribbon signals
        self.connect_ribbon_signals()
        
        # Central widget with main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Main content area with horizontal splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Configuration
        left_panel = QWidget()
        left_panel.setMaximumWidth(350)
        left_panel.setMinimumWidth(300)
        self.create_configuration_panel(left_panel)
        content_splitter.addWidget(left_panel)
        
        # Right panel - Monitoring with nested vertical layout
        right_panel = QWidget()
        self.create_monitoring_panel(right_panel)
        content_splitter.addWidget(right_panel)
        
        # Set horizontal splitter proportions (35% left, 65% right)
        content_splitter.setSizes([350, 650])
        
        main_layout.addWidget(content_splitter)
        
    def create_configuration_group(self, parent_layout):
        """Create the port configuration group."""
        config_group = QGroupBox("Port Configuration")
        config_layout = QGridLayout(config_group)
        
        # Incoming Port Selection
        config_layout.addWidget(QLabel("Incoming Port:"), 0, 0)
        self.incoming_port_combo = QComboBox()
        self.incoming_port_combo.setMinimumWidth(120)
        # Connect port selection changes to diagram updates
        self.incoming_port_combo.currentTextChanged.connect(self.on_incoming_port_changed)
        config_layout.addWidget(self.incoming_port_combo, 0, 1)
        
        
        # Incoming Port Baud Rate
        config_layout.addWidget(QLabel("Incoming Baud:"), 1, 0)
        self.incoming_baud_spin = QSpinBox()
        self.incoming_baud_spin.setRange(1200, 921600)
        self.incoming_baud_spin.setValue(115200)
        self.incoming_baud_spin.setSingleStep(1200)
        config_layout.addWidget(self.incoming_baud_spin, 1, 1)
        
        # Outgoing Port 1
        config_layout.addWidget(QLabel("Outgoing Port 1:"), 2, 0)
        self.outgoing_port1_combo = QComboBox()
        self.outgoing_port1_combo.setMinimumWidth(120)
        self.outgoing_port1_combo.currentTextChanged.connect(self.on_outgoing_port_changed)
        config_layout.addWidget(self.outgoing_port1_combo, 2, 1)

        # Outgoing Port 2
        config_layout.addWidget(QLabel("Outgoing Port 2:"), 3, 0)
        self.outgoing_port2_combo = QComboBox()
        self.outgoing_port2_combo.setMinimumWidth(120)
        self.outgoing_port2_combo.currentTextChanged.connect(self.on_outgoing_port_changed)
        config_layout.addWidget(self.outgoing_port2_combo, 3, 1)

        # Outgoing Port Baud Rate
        config_layout.addWidget(QLabel("Outgoing Baud:"), 4, 0)
        self.outgoing_baud_spin = QSpinBox()
        self.outgoing_baud_spin.setRange(1200, 921600) 
        self.outgoing_baud_spin.setValue(115200)
        self.outgoing_baud_spin.setSingleStep(1200)
        config_layout.addWidget(self.outgoing_baud_spin, 4, 1)
        
        # Add control buttons at bottom of configuration panel
        control_frame = QFrame()
        control_layout = QVBoxLayout(control_frame)
        control_layout.setSpacing(15)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # Enhanced Status display
        status_group = QGroupBox("Router Status")
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(5, 5, 5, 0)  # Remove bottom margin
        
        # Enhanced status widget
        self.enhanced_status = EnhancedStatusWidget()
        status_layout.addWidget(self.enhanced_status)
        
        control_layout.addWidget(status_group)
        
        # Connection diagram
        diagram_group = QGroupBox("Port Connections")
        diagram_layout = QVBoxLayout(diagram_group)
        
        # Connection diagram widget
        try:
            self.connection_diagram = ConnectionDiagramWidget()
            diagram_layout.addWidget(self.connection_diagram)
        except Exception as e:
            print(f"Error creating ConnectionDiagramWidget: {e}")
            import traceback
            traceback.print_exc()
            # Create a simple placeholder label instead
            placeholder = QLabel("Connection Diagram (Error Loading)")
            placeholder.setMinimumHeight(200)
            # Use Qt palette colors for theme compatibility
            palette = placeholder.palette()
            bg_color = palette.color(palette.ColorRole.AlternateBase)
            border_color = palette.color(palette.ColorRole.Mid)
            placeholder.setStyleSheet(f"""
                background-color: {bg_color.name()};
                border: 1px solid {border_color.name()};
                text-align: center;
            """)
            diagram_layout.addWidget(placeholder)
            self.connection_diagram = None
        
        control_layout.addWidget(diagram_group)
        
        
        parent_layout.addWidget(config_group)
        parent_layout.addWidget(control_frame)
        
    def create_configuration_panel(self, parent_widget):
        """Create the left configuration panel."""
        layout = QVBoxLayout(parent_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Configuration Group
        self.create_configuration_group(layout)
        
        layout.addStretch()
    
    def create_monitoring_panel(self, parent_widget):
        """Create the right monitoring panel with nested vertical splitter."""
        layout = QVBoxLayout(parent_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create vertical splitter for monitoring stats and activity log
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top section - Status Monitoring
        monitoring_widget = QWidget()
        monitoring_layout = QVBoxLayout(monitoring_widget)
        monitoring_layout.setSpacing(15)
        monitoring_layout.setContentsMargins(10, 10, 10, 10)
        self.create_monitoring_group(monitoring_layout)
        # Remove stretch from parent - will be handled in child container
        vertical_splitter.addWidget(monitoring_widget)
        
        # Bottom section - Activity Log
        log_widget = QWidget()
        self.create_activity_log_panel(log_widget)
        vertical_splitter.addWidget(log_widget)
        
        # Set vertical splitter proportions (60% monitoring, 40% log) and enable dynamic resizing
        vertical_splitter.setSizes([360, 240])
        vertical_splitter.setStretchFactor(0, 1)  # Monitoring section can expand
        vertical_splitter.setStretchFactor(1, 0)  # Log section maintains size preference
        
        layout.addWidget(vertical_splitter)
    
    def connect_ribbon_signals(self):
        """Connect ribbon toolbar signals to existing methods."""
        self.ribbon.start_routing.connect(self.start_routing)
        self.ribbon.stop_routing.connect(self.stop_routing)
        self.ribbon.configure_ports.connect(self.show_port_configuration)
        self.ribbon.refresh_ports.connect(self.refresh_available_ports)
        self.ribbon.view_stats.connect(self.show_routing_stats)
        self.ribbon.clear_log.connect(self.clear_activity_log)
        self.ribbon.show_help.connect(self.show_help_information)
    
    def show_port_configuration(self):
        """Show detailed port information and launch com0com setup utility."""
        # Show detailed port analysis first
        self.show_detailed_port_analysis()
        
        # Then launch setup utility
        try:
            subprocess.Popen([r"C:\Program Files (x86)\com0com\VirtualPortManager\VirtualPortManager.exe"], 
                            creationflags=subprocess.DETACHED_PROCESS)
            self.add_log_message("Launched com0com setup utility")
        except Exception as e:
            self.add_log_message(f"Could not launch setup utility: {str(e)}")
    
    def show_detailed_port_analysis(self):
        """Show detailed analysis of available ports."""
        try:
            self.add_log_message("=== Detailed Port Analysis ===")

            all_ports = self.port_enumerator.enumerate_ports()
            if not all_ports:
                self.add_log_message("No serial ports detected on this system")
                return

            # Get dynamically excluded ports based on current outgoing selection
            excluded_ports = self._get_excluded_ports()
            
            # Group ports by type for better presentation
            port_groups = {
                PortType.PHYSICAL: [],
                PortType.MOXA_VIRTUAL: [],
                PortType.OTHER_VIRTUAL: []
            }
            
            for port in all_ports:
                port_groups[port.port_type].append(port)
            
            # Show physical ports
            if port_groups[PortType.PHYSICAL]:
                self.add_log_message("Physical Ports")
                for port in port_groups[PortType.PHYSICAL]:
                    if port.port_name in excluded_ports:
                        self.add_log_message(f"  - {port.port_name} - [RESERVED - Outgoing Only]")
                    else:
                        self.add_log_message(f"  - {port.port_name}")
            
            # Show Moxa ports (critical for offshore operations)
            if port_groups[PortType.MOXA_VIRTUAL]:
                self.add_log_message("Moxa Virtual Ports (Network Serial):")
                for port in port_groups[PortType.MOXA_VIRTUAL]:
                    if port.port_name in excluded_ports:
                        self.add_log_message(f"  - {port.port_name} - [RESERVED - Outgoing Only]")
                    else:
                        self.add_log_message(f"  - {port.port_name}")
            
            # Show other virtual ports
            if port_groups[PortType.OTHER_VIRTUAL]:
                self.add_log_message("Other Virtual Ports:")
                for port in port_groups[PortType.OTHER_VIRTUAL]:
                    if port.port_name in excluded_ports:
                        self.add_log_message(f"  - {port.port_name}")
                    else:
                        self.add_log_message(f"  - {port.port_name}")
            
            # Validate current router configuration
            current_incoming = self.incoming_port_combo.currentText()
            if current_incoming:
                validation = self.port_enumerator.validate_router_ports(current_incoming, ["COM131", "COM141"])
                self.add_log_message("Current Router Configuration:")
                for port_name, is_available in validation.items():
                    status = "[OK]" if is_available else "[MISSING]"
                    self.add_log_message(f"  {status} {port_name}")        
        except Exception as e:
            self.add_log_message(f"Port analysis error: {str(e)}")
    
    def show_routing_stats(self):
        """Show historical performance and reliability statistics."""
        if not self.router_core:
            self.add_log_message("Router not active - no statistics available")
            return
        
        try:
            status = self.router_core.get_status()
            
            self.add_log_message("=== Router Performance Report ===")
            
            # Data transfer totals
            bytes_transferred = status.get('bytes_transferred', {})
            for direction, bytes_count in bytes_transferred.items():
                if isinstance(bytes_count, int):
                    if bytes_count > 1024:
                        self.add_log_message(f"Total {direction}: {bytes_count:,} bytes ({bytes_count/1024:.1f} KB)")
                    else:
                        self.add_log_message(f"Total {direction}: {bytes_count} bytes")
            
            # Performance metrics
            critical_metrics = status.get('critical_metrics', {})
            peak_bps = critical_metrics.get('peak_throughput_bps', 0)
            self.add_log_message(f"Peak throughput: {peak_bps:,} bps")
            
            # Reliability
            restart_counts = status.get('thread_restart_counts', {})
            total_restarts = 0
            for key, value in restart_counts.items():
                if isinstance(value, int):
                    total_restarts += value
            self.add_log_message(f"Thread restarts: {total_restarts} total")
            
            # Runtime
            uptime = critical_metrics.get('system_uptime_hours', 0)
            self.add_log_message(f"Runtime: {uptime:.2f} hours")
            
        except Exception as e:
            self.add_log_message(f"Could not retrieve statistics: {str(e)}")
    
    def show_help_information(self):
        """Show about dialog and add helpful console information."""
        # Show about dialog
        AboutDialog.show_about(self)
        
        # Add stylized console log information
        port1, port2 = self._get_selected_outgoing_ports()
        self.add_log_message(" ╔══════════════════════════════════════════════════════════════════╗")
        self.add_log_message(" ║                   SerialRouter v2.0 - Operation Guide            ║")
        self.add_log_message(" ╠══════════════════════════════════════════════════════════════════╣")
        self.add_log_message(" ║ • Routes incoming port to COM131 & COM41 (Default port pairs)    ║")
        self.add_log_message(" ║ • Connect applications to paired endpoints (COM132 & COM142)     ║")
        self.add_log_message(" ║ • Select START ROUTING to begin, STOP ROUTING to end             ║")
        self.add_log_message(" ║ • Configure incoming port before starting operations             ║")
        self.add_log_message(" ╚══════════════════════════════════════════════════════════════════╝")
    
    def on_incoming_port_changed(self, port_name: str):
        """Handle incoming port selection changes."""
        if hasattr(self, 'connection_diagram') and port_name:
            if self.connection_diagram:
                self.connection_diagram.set_incoming_port(port_name)

    def on_outgoing_port_changed(self):
        """Handle outgoing port selection changes - validate and update diagram."""
        if not hasattr(self, 'outgoing_port1_combo') or not hasattr(self, 'outgoing_port2_combo'):
            return

        self.validate_port_configuration()

        # Update tooltips with paired port detection
        self._update_port_tooltips()

        # Update connection diagram with new ports
        port1 = self.outgoing_port1_combo.currentText()
        port2 = self.outgoing_port2_combo.currentText()
        if self.connection_diagram and port1 and port2:
            # Get all com0com ports for proximity detection
            com0com_ports = self.port_enumerator.get_com0com_ports()
            com0com_names = [p.port_name for p in com0com_ports]
            self.connection_diagram.set_outgoing_ports(port1, port2, com0com_names)

    def _get_selected_outgoing_ports(self):
        """Returns currently selected outgoing ports from UI dropdowns."""
        if hasattr(self, 'outgoing_port1_combo') and hasattr(self, 'outgoing_port2_combo'):
            return (
                self.outgoing_port1_combo.currentText(),
                self.outgoing_port2_combo.currentText()
            )
        return ("COM131", "COM141")  # Safe fallback

    def _update_port_tooltips(self):
        """Update tooltips to show detected paired ports."""
        if not hasattr(self, 'outgoing_port1_combo') or not hasattr(self, 'outgoing_port2_combo'):
            return

        port1 = self.outgoing_port1_combo.currentText()
        port2 = self.outgoing_port2_combo.currentText()

        # Get all com0com ports for pairing detection
        com0com_ports = self.port_enumerator.get_com0com_ports()
        com0com_names = [p.port_name for p in com0com_ports]

        # Detect paired port for port1
        if port1:
            paired1 = self._detect_paired_port(port1, com0com_names)
            if paired1.startswith("COM"):
                # High confidence - found neighbor
                self.outgoing_port1_combo.setToolTip(f"Router writes to {port1}\nApplications read from paired port {paired1}")
            else:
                # Low confidence - generic fallback
                self.outgoing_port1_combo.setToolTip(f"Router writes to {port1}\nVerify paired port in com0com setup")

        # Detect paired port for port2
        if port2:
            paired2 = self._detect_paired_port(port2, com0com_names)
            if paired2.startswith("COM"):
                # High confidence - found neighbor
                self.outgoing_port2_combo.setToolTip(f"Router writes to {port2}\nApplications read from paired port {paired2}")
            else:
                # Low confidence - generic fallback
                self.outgoing_port2_combo.setToolTip(f"Router writes to {port2}\nVerify paired port in com0com setup")

    def _detect_paired_port(self, port: str, all_com0com_ports: list) -> str:
        """
        Detect the paired port using proximity algorithm.
        Returns the paired port name or a generic label if detection fails.
        """
        try:
            num = int(port.replace("COM", ""))
            # Check +1 and -1 neighbors
            candidates = [f"COM{num + 1}", f"COM{num - 1}"]
            for candidate in candidates:
                if candidate in all_com0com_ports:
                    return candidate
            # No neighbor found
            return "Unknown"
        except:
            return "Unknown"

    def _get_excluded_ports(self) -> set:
        """
        Get ports that should be excluded from incoming port selection.
        Returns the currently selected outgoing ports plus their likely paired ports.
        """
        excluded = set()
        port1, port2 = self._get_selected_outgoing_ports()

        # Add the selected outgoing ports
        if port1:
            excluded.add(port1)
        if port2:
            excluded.add(port2)

        # Add their probable paired ports using proximity algorithm
        try:
            for port in [port1, port2]:
                if not port:
                    continue
                num = int(port.replace("COM", ""))
                # Check +1 and -1 neighbors (likely pairs)
                excluded.add(f"COM{num + 1}")
                excluded.add(f"COM{num - 1}")
        except:
            # If parsing fails, fall back to default reserved ports
            excluded.update({"COM131", "COM132", "COM141", "COM142"})

        return excluded

    def validate_port_configuration(self) -> bool:
        """Validate current port configuration."""
        if not hasattr(self, 'outgoing_port1_combo') or not hasattr(self, 'outgoing_port2_combo'):
            return True

        incoming = self.incoming_port_combo.currentText()
        port1 = self.outgoing_port1_combo.currentText()
        port2 = self.outgoing_port2_combo.currentText()

        # Rule 1: Both ports cannot be the same
        if port1 == port2 and port1:
            if not self._initializing:
                self.add_log_message(f"Warning: Both outgoing ports set to {port1} - select different ports")
            return False

        # Rule 2: Outgoing port cannot be same as incoming
        if incoming == port1 or incoming == port2:
            if not self._initializing:
                self.add_log_message(f"Warning: Outgoing port cannot be same as incoming port {incoming}")
            return False

        # Rule 3: CRITICAL - Prevent paired ports (would cause feedback loop)
        if port1 and port2:
            try:
                num1 = int(port1.replace("COM", ""))
                num2 = int(port2.replace("COM", ""))

                # Check if ports are adjacent (likely paired in com0com)
                if abs(num1 - num2) == 1:
                    if not self._initializing:
                        self.add_log_message(
                            f"ERROR: {port1} and {port2} appear to be paired ports! "
                            f"This will create a feedback loop. Select non-adjacent ports."
                        )
                    return False
            except:
                # If parsing fails, allow the configuration (can't validate)
                pass

        return True
    
    def create_control_group(self, parent_layout):
        """Legacy method - functionality moved to configuration panel."""
        pass
        
    def create_monitoring_group(self, parent_layout):
        """Create the real-time monitoring group with two-column grid layout."""
        from PyQt6.QtWidgets import QSizePolicy

        monitor_group = QGroupBox("Data Flow Monitor")
        monitor_layout = QGridLayout(monitor_group)
        monitor_layout.setSpacing(5)
        monitor_layout.setHorizontalSpacing(20)  # Fixed gap between columns
        monitor_layout.setVerticalSpacing(5)  # Slightly more vertical spacing for clarity
        monitor_layout.setColumnMinimumWidth(0, 200)  # Minimum width for left column
        monitor_layout.setColumnMinimumWidth(1, 200)  # Minimum width for right column

        # Row 0-2: Two-column channel stats
        # Left Column (col 0): Outgoing Channels
        outgoing_header = self._create_section_header('data_outbound', 'Outgoing Channels')
        monitor_layout.addWidget(outgoing_header, 0, 0)

        # Port 1 subsection
        self.port1_widget = self._create_port_widget("1", "outgoing")
        self.port1_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        monitor_layout.addWidget(self.port1_widget, 1, 0)

        # Port 2 subsection
        self.port2_widget = self._create_port_widget("2", "outgoing")
        self.port2_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        monitor_layout.addWidget(self.port2_widget, 2, 0)

        # Right Column (col 1): Incoming Channel
        incoming_header = self._create_section_header('data_inbound', 'Incoming Channel')
        monitor_layout.addWidget(incoming_header, 0, 1)

        self.incoming_widget = self._create_incoming_widget()
        self.incoming_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        monitor_layout.addWidget(self.incoming_widget, 1, 1, 2, 1)  # Span 2 rows to match left column height

        # Row 3-4: System Health spans full width
        health_header = self._create_section_header('session_stats', 'System Health')
        monitor_layout.addWidget(health_header, 3, 0, 1, 2)  # Span both columns

        self.health_widget = self._create_health_widget()
        self.health_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        monitor_layout.addWidget(self.health_widget, 4, 0, 1, 2)  # Span both columns

        # Add horizontal stretch column to absorb extra width
        monitor_layout.setColumnStretch(0, 0)  # No stretch - fixed width
        monitor_layout.setColumnStretch(1, 0)  # No stretch - fixed width
        monitor_layout.setColumnStretch(2, 1)  # Stretch column absorbs extra space

        # Add vertical stretch to push content to top
        monitor_layout.setRowStretch(5, 1)

        parent_layout.addWidget(monitor_group)

    def _create_section_header(self, icon_name: str, text: str) -> QWidget:
        """Create a section header with icon and text, matching ribbon toolbar style."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 4)  # More top padding for visual separation
        layout.setSpacing(6)

        # Add icon using stats icon loader
        icon = resource_manager.get_stats_icon(icon_name)
        if not icon.isNull():
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(16, 16))  # Match ribbon icon size
            layout.addWidget(icon_label)

        # Add text label
        text_label = QLabel(text)
        text_label.setProperty("class", "section-header")
        font = text_label.font()
        font.setBold(True)
        font.setPointSize(9)  # Slightly larger for section headers
        text_label.setFont(font)
        layout.addWidget(text_label)

        layout.addStretch()

        return container

    def _create_port_widget(self, port_num: str, direction: str) -> QWidget:
        """Create port stat display with tree indent."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 3, 0, 8)  # Indent for tree effect, bottom padding for spacing
        layout.setSpacing(3)

        # Simple header: "├─ Port 1" or "├─ Port 2"
        header_text = f"├─ Port {port_num}"

        header = QLabel(header_text)
        font = header.font()
        font.setFamily("Consolas, Courier New, monospace")
        font.setPointSize(8)
        header.setFont(font)
        header.setStyleSheet("color: #555;")  # Subtle color for tree structure
        layout.addWidget(header)

        # Store reference to header for potential dynamic updates
        if port_num == "1":
            self.port1_header = header
        else:
            self.port2_header = header

        # Metrics row 1: ↑ To Client
        to_client_row = QHBoxLayout()
        to_client_row.setSpacing(8)
        to_label = QLabel("  │   ↑ To Client:")
        to_label.setFont(font)
        to_label.setStyleSheet("color: #555;")
        to_client_row.addWidget(to_label)

        bytes_out_label = QLabel("0 bytes")
        bytes_out_label.setProperty("class", "metric-value")
        metric_font = bytes_out_label.font()
        metric_font.setFamily("Consolas, Courier New, monospace")
        metric_font.setPointSize(8)
        bytes_out_label.setFont(metric_font)
        to_client_row.addWidget(bytes_out_label)

        rate_sep = QLabel("│")
        rate_sep.setStyleSheet("color: #ccc;")
        to_client_row.addWidget(rate_sep)

        rate_label = QLabel("Rate:")
        rate_label.setFont(font)
        rate_label.setStyleSheet("color: #555;")
        to_client_row.addWidget(rate_label)

        rate_out_label = QLabel("0 B/s")
        rate_out_label.setProperty("class", "metric-value")
        rate_out_label.setFont(metric_font)
        to_client_row.addWidget(rate_out_label)

        to_client_row.addStretch()
        layout.addLayout(to_client_row)

        # Store label references
        if port_num == "1":
            self.port1_bytes_out = bytes_out_label
            self.port1_rate_out = rate_out_label
        else:
            self.port2_bytes_out = bytes_out_label
            self.port2_rate_out = rate_out_label

        # Metrics row 2: ↓ From Client
        from_client_row = QHBoxLayout()
        from_client_row.setSpacing(8)
        from_label = QLabel("  │   ↓ From Client:")
        from_label.setFont(font)
        from_label.setStyleSheet("color: #555;")
        from_client_row.addWidget(from_label)

        bytes_in_label = QLabel("0 bytes")
        bytes_in_label.setProperty("class", "metric-value")
        bytes_in_label.setFont(metric_font)
        from_client_row.addWidget(bytes_in_label)

        rate_sep2 = QLabel("│")
        rate_sep2.setStyleSheet("color: #ccc;")
        from_client_row.addWidget(rate_sep2)

        rate_label2 = QLabel("Rate:")
        rate_label2.setFont(font)
        rate_label2.setStyleSheet("color: #555;")
        from_client_row.addWidget(rate_label2)

        rate_in_label = QLabel("0 B/s")
        rate_in_label.setProperty("class", "metric-value")
        rate_in_label.setFont(metric_font)
        from_client_row.addWidget(rate_in_label)

        from_client_row.addStretch()
        layout.addLayout(from_client_row)

        # Store label references
        if port_num == "1":
            self.port1_bytes_in = bytes_in_label
            self.port1_rate_in = rate_in_label
        else:
            self.port2_bytes_in = bytes_in_label
            self.port2_rate_in = rate_in_label

        return container

    def _create_incoming_widget(self) -> QWidget:
        """Create incoming port stats."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 3, 0, 8)
        layout.setSpacing(3)

        # Header: "└─ Port <dynamic>"
        incoming_port = self.incoming_port_combo.currentText() if hasattr(self, 'incoming_port_combo') else "COM54"
        self.incoming_header = QLabel(f"└─ Port {incoming_port}")
        font = self.incoming_header.font()
        font.setFamily("Consolas, Courier New, monospace")
        font.setPointSize(8)
        self.incoming_header.setFont(font)
        self.incoming_header.setStyleSheet("color: #555;")
        layout.addWidget(self.incoming_header)

        # Metrics row
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)
        metrics_label = QLabel("    Total Routed:")
        metrics_label.setFont(font)
        metrics_label.setStyleSheet("color: #555;")
        metrics_row.addWidget(metrics_label)

        self.bytes_routed_label = QLabel("0 bytes")
        self.bytes_routed_label.setProperty("class", "metric-value")
        metric_font = self.bytes_routed_label.font()
        metric_font.setFamily("Consolas, Courier New, monospace")
        metric_font.setPointSize(8)
        self.bytes_routed_label.setFont(metric_font)
        metrics_row.addWidget(self.bytes_routed_label)

        rate_sep = QLabel("│")
        rate_sep.setStyleSheet("color: #ccc;")
        metrics_row.addWidget(rate_sep)

        rate_label = QLabel("Rate:")
        rate_label.setFont(font)
        rate_label.setStyleSheet("color: #555;")
        metrics_row.addWidget(rate_label)

        self.rate_routed_label = QLabel("0 B/s")
        self.rate_routed_label.setProperty("class", "metric-value")
        self.rate_routed_label.setFont(metric_font)
        metrics_row.addWidget(self.rate_routed_label)

        metrics_row.addStretch()
        layout.addLayout(metrics_row)

        return container

    def _create_health_widget(self) -> QWidget:
        """Create system health display with session info."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 3, 0, 8)
        layout.setSpacing(3)

        # Create consistent font for tree structure
        tree_font = QFont("Consolas, Courier New, monospace", 8)
        label_font = QFont("Consolas, Courier New, monospace", 8)

        # Row 1: Connections and Threads
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        conn_label = QLabel("├─ Connections:")
        conn_label.setFont(tree_font)
        conn_label.setStyleSheet("color: #555;")
        row1.addWidget(conn_label)

        self.connections_label = QLabel("0/3")
        self.connections_label.setProperty("class", "metric-value")
        self.connections_label.setFont(label_font)
        row1.addWidget(self.connections_label)

        sep1 = QLabel("│")
        sep1.setStyleSheet("color: #ccc;")
        row1.addWidget(sep1)

        thread_label = QLabel("Threads:")
        thread_label.setFont(tree_font)
        thread_label.setStyleSheet("color: #555;")
        row1.addWidget(thread_label)

        self.thread_status_label = QLabel("0/3 Active")
        self.thread_status_label.setProperty("class", "metric-value")
        self.thread_status_label.setFont(label_font)
        row1.addWidget(self.thread_status_label)
        row1.addStretch()
        layout.addLayout(row1)

        # Row 2: Uptime and Health
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        uptime_label = QLabel("├─ Uptime:")
        uptime_label.setFont(tree_font)
        uptime_label.setStyleSheet("color: #555;")
        row2.addWidget(uptime_label)

        self.uptime_label = QLabel("0 hours")
        self.uptime_label.setProperty("class", "metric-value")
        self.uptime_label.setFont(label_font)
        row2.addWidget(self.uptime_label)

        sep2 = QLabel("│")
        sep2.setStyleSheet("color: #ccc;")
        row2.addWidget(sep2)

        health_label = QLabel("Health:")
        health_label.setFont(tree_font)
        health_label.setStyleSheet("color: #555;")
        row2.addWidget(health_label)

        self.health_status_label = QLabel("Offline")
        self.health_status_label.setProperty("class", "metric-value")
        self.health_status_label.setFont(label_font)
        row2.addWidget(self.health_status_label)
        row2.addStretch()
        layout.addLayout(row2)

        # Row 3: Errors and Queue
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        error_label = QLabel("├─ Errors:")
        error_label.setFont(tree_font)
        error_label.setStyleSheet("color: #555;")
        row3.addWidget(error_label)

        self.error_count_label = QLabel("0")
        self.error_count_label.setProperty("class", "metric-value")
        self.error_count_label.setFont(label_font)
        row3.addWidget(self.error_count_label)

        sep3 = QLabel("│")
        sep3.setStyleSheet("color: #ccc;")
        row3.addWidget(sep3)

        queue_label = QLabel("Queue:")
        queue_label.setFont(tree_font)
        queue_label.setStyleSheet("color: #555;")
        row3.addWidget(queue_label)

        self.queue_util_label = QLabel("0%")
        self.queue_util_label.setProperty("class", "metric-value")
        self.queue_util_label.setFont(label_font)
        row3.addWidget(self.queue_util_label)
        row3.addStretch()
        layout.addLayout(row3)

        # Row 4: Session info (moved from footer)
        row4 = QHBoxLayout()
        row4.setSpacing(8)
        session_label = QLabel("└─ Session:")
        session_label.setFont(tree_font)
        session_label.setStyleSheet("color: #555;")
        row4.addWidget(session_label)

        self.session_duration_label = QLabel("0h 0m")
        self.session_duration_label.setProperty("class", "metric-value")
        self.session_duration_label.setFont(label_font)
        row4.addWidget(self.session_duration_label)

        sep4 = QLabel("│")
        sep4.setStyleSheet("color: #ccc;")
        row4.addWidget(sep4)

        reset_label = QLabel("Last Reset:")
        reset_label.setFont(tree_font)
        reset_label.setStyleSheet("color: #555;")
        row4.addWidget(reset_label)

        self.last_reset_label = QLabel("Never")
        self.last_reset_label.setProperty("class", "metric-value")
        self.last_reset_label.setFont(label_font)
        row4.addWidget(self.last_reset_label)
        row4.addStretch()
        layout.addLayout(row4)

        # Keep legacy labels for backward compatibility
        self.throughput_label = QLabel("0 bytes/sec")
        self.last_activity_label = QLabel("N/A")
        self.data_loss_label = QLabel("0")
        self.error_rate_label = QLabel("0.0/hour")
        self.restart_count_label = QLabel("0")

        # Hide them as they're not displayed in new layout
        for label in [self.throughput_label, self.last_activity_label, self.data_loss_label,
                      self.error_rate_label, self.restart_count_label]:
            label.setVisible(False)

        return container

    def _create_session_footer(self) -> QWidget:
        """Create session info footer."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 5)
        layout.setSpacing(6)

        # Add session icon
        icon = resource_manager.get_stats_icon('session_stats')
        if not icon.isNull():
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(14, 14))  # Slightly smaller for footer
            layout.addWidget(icon_label)

        layout.addWidget(QLabel("Session:"))
        self.session_duration_label = QLabel("0h 0m")
        self.session_duration_label.setProperty("class", "metric-value")
        layout.addWidget(self.session_duration_label)

        layout.addWidget(QLabel("│"))

        layout.addWidget(QLabel("Last Reset:"))
        self.last_reset_label = QLabel("Never")
        self.last_reset_label.setProperty("class", "metric-value")
        layout.addWidget(self.last_reset_label)

        layout.addStretch()

        return container

    def create_activity_log_panel(self, parent_widget):
        """Create the activity log panel for the right pane."""
        layout = QVBoxLayout(parent_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)
        
        
        # Log display
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        
        # Set monospace font for proper Unicode box-drawing character alignment
        # Windows-optimized font stack for clean, modern appearance
        monospace_font = QFont("Cascadia Code, Cascadia Mono, Consolas, 'Courier New', monospace")
        monospace_font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.activity_log.setFont(monospace_font)
        
        log_layout.addWidget(self.activity_log)
        
        layout.addWidget(log_group)
        
    def setup_logging(self):
        """Setup custom logging handler for activity log."""
        self.log_handler = LogHandler()
        self.log_handler.log_signal = self.log_message_signal
        
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        self.log_handler.setFormatter(formatter)
        
    def add_log_message(self, message: str):
        """Add a message to the activity log."""
        self.activity_log.append(message)
        
        # Auto-scroll to bottom
        scrollbar = self.activity_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def refresh_available_ports(self):
        """Refresh the list of available COM ports using enhanced port enumerator."""
        current_port = self.incoming_port_combo.currentText()
        current_out1 = self.outgoing_port1_combo.currentText() if hasattr(self, 'outgoing_port1_combo') else ""
        current_out2 = self.outgoing_port2_combo.currentText() if hasattr(self, 'outgoing_port2_combo') else ""

        self.incoming_port_combo.clear()
        if hasattr(self, 'outgoing_port1_combo'):
            self.outgoing_port1_combo.clear()
        if hasattr(self, 'outgoing_port2_combo'):
            self.outgoing_port2_combo.clear()
        
        try:
            # Use our robust port enumerator
            all_ports = self.port_enumerator.enumerate_ports()
            
            if not all_ports:
                # Fallback to COM54 if no ports detected
                self.incoming_port_combo.addItem("COM54")
                self.add_log_message("No ports detected - using COM54 fallback")
                return
            
            # Separate ports by type for better user experience
            physical_ports = []
            moxa_ports = []
            com0com_ports = []
            other_virtual_ports = []

            for port in all_ports:
                if port.port_type == PortType.PHYSICAL:
                    physical_ports.append(port)
                elif port.port_type == PortType.MOXA_VIRTUAL:
                    moxa_ports.append(port)
                elif port.port_type == PortType.COM0COM_VIRTUAL:
                    com0com_ports.append(port)
                else:
                    other_virtual_ports.append(port)

            # Add ports to incoming dropdown in order of priority: Physical, Moxa, Other Virtual
            # CRITICAL: com0com ports are NEVER added to incoming dropdown (outgoing only)
            port_items = []
            port_details = []

            # Add physical ports first (preferred for incoming)
            for port in physical_ports:
                port_items.append(port.port_name)
                port_details.append(f"{port.port_name} (Physical)")

            # Add Moxa ports next (common for incoming in marine/offshore)
            for port in moxa_ports:
                port_items.append(port.port_name)
                port_details.append(f"{port.port_name} (Moxa Virtual)")

            # Add other non-com0com virtual ports last
            for port in other_virtual_ports:
                port_items.append(port.port_name)
                port_details.append(f"{port.port_name} (Virtual)")
            
            # Populate the dropdown
            if port_items:
                self.incoming_port_combo.addItems(port_items)
                
                # Smart default selection priority:
                # 1. Previous selection if still available
                # 2. COM54 if it's a Moxa port (current system default)
                # 3. First physical port
                # 4. First available port
                if current_port and current_port in port_items:
                    self.incoming_port_combo.setCurrentText(current_port)
                elif "COM54" in port_items:
                    self.incoming_port_combo.setCurrentText("COM54")
                elif physical_ports:
                    self.incoming_port_combo.setCurrentText(physical_ports[0].port_name)
                else:
                    self.incoming_port_combo.setCurrentIndex(0)
            else:
                self.incoming_port_combo.addItem("COM54")
            
            # Populate outgoing port dropdowns with com0com ports only
            if hasattr(self, 'outgoing_port1_combo') and hasattr(self, 'outgoing_port2_combo'):
                com0com_ports = self.port_enumerator.get_com0com_ports()
                com0com_names = [p.port_name for p in com0com_ports]

                if com0com_names:
                    self.outgoing_port1_combo.addItems(com0com_names)
                    self.outgoing_port2_combo.addItems(com0com_names)

                    # Set defaults: restore previous or use COM131/COM141
                    if current_out1 and current_out1 in com0com_names:
                        self.outgoing_port1_combo.setCurrentText(current_out1)
                    elif "COM131" in com0com_names:
                        self.outgoing_port1_combo.setCurrentText("COM131")

                    if current_out2 and current_out2 in com0com_names:
                        self.outgoing_port2_combo.setCurrentText(current_out2)
                    elif "COM141" in com0com_names:
                        self.outgoing_port2_combo.setCurrentText("COM141")
                else:
                    # No com0com ports found - add defaults anyway
                    self.outgoing_port1_combo.addItems(["COM131"])
                    self.outgoing_port2_combo.addItems(["COM141"])
                    self.add_log_message("Warning: No com0com ports detected - using defaults")

            # Report findings with port type details
            total_ports = len(all_ports)
            available_ports = len(port_items)
            moxa_count = len(moxa_ports)
            physical_count = len(physical_ports)
            com0com_count = len(com0com_ports)

            self.add_log_message(f"Port scan: {total_ports} total, {available_ports} available for incoming ({physical_count} Physical, {moxa_count} Moxa, {com0com_count} com0com)")

            # Show com0com ports information (reserved for outgoing only)
            if com0com_ports:
                com0com_names_list = [p.port_name for p in com0com_ports]
                self.add_log_message(f"com0com ports reserved for outgoing: {', '.join(com0com_names_list)}")

            # Show Moxa ports specifically (important for offshore operations)
            if moxa_ports:
                moxa_names = [p.port_name for p in moxa_ports]
                self.add_log_message(f"Available Moxa ports: {', '.join(moxa_names)}")
            
        except Exception as e:
            self.add_log_message(f"Error scanning ports: {str(e)}")
            # Safe fallback
            self.incoming_port_combo.addItem("COM54")
            self.add_log_message("Using COM54 fallback due to scan error")
            
    def validate_selected_port(self) -> bool:
        """Enhanced port validation using port enumerator with exclusion checks."""
        port = self.incoming_port_combo.currentText()
        if not port or port in ["No COM ports available", "Error reading ports"]:
            return False

        # Critical safety check: prevent using reserved outgoing ports as incoming
        excluded_ports = self._get_excluded_ports()
        if port in excluded_ports:
            self.add_log_message(f"ERROR: Cannot use {port} as incoming port - reserved for outgoing routing")
            return False
        
        try:
            # Get current outgoing ports
            outgoing_ports = []
            if hasattr(self, 'outgoing_port1_combo') and hasattr(self, 'outgoing_port2_combo'):
                outgoing_ports = [
                    self.outgoing_port1_combo.currentText(),
                    self.outgoing_port2_combo.currentText()
                ]
            else:
                outgoing_ports = ["COM131", "COM141"]

            # Validate that router ports exist using our enumerator
            validation = self.port_enumerator.validate_router_ports(port, outgoing_ports)
            
            if not validation.get(port, False):
                self.add_log_message(f"Warning: Selected port {port} not found during validation")
                return False
                
            # Check that selected outgoing ports are available
            missing_ports = []
            for outgoing_port in outgoing_ports:
                if not validation.get(outgoing_port, False):
                    missing_ports.append(outgoing_port)
            
            if missing_ports:
                self.add_log_message(f"Warning: Required outgoing ports not found: {', '.join(missing_ports)}")
                # Still allow operation - ports might become available
                
            return True
            
        except Exception as e:
            self.add_log_message(f"Port validation error: {str(e)}")
            # Fallback to basic validation with exclusion check
            return bool(port) and port not in excluded_ports
        
    def cleanup_router_core(self):
        """Simple cleanup helper for router core and logging handler."""
        if self.router_core:
            try:
                # Critical fix: stop the router engine to properly release ports and threads
                if self.router_core.running:
                    self.router_core.stop()
                # Remove log handler after stopping
                if self.log_handler:
                    self.router_core.logger.removeHandler(self.log_handler)
            except ValueError:
                pass  # Handler was already removed
            except Exception as e:
                self.add_log_message(f"Warning: Router cleanup failed: {str(e)}")
        self.router_core = None
        
    def is_routing_active(self) -> bool:
        """Check if routing is currently active."""
        return self.router_core is not None and self.router_core.running
        
    def start_routing(self):
        """Start the serial routing process."""
        if not self.validate_selected_port():
            self.add_log_message("Cannot start: Selected port is not available")
            return

        if not self.validate_port_configuration():
            self.add_log_message("Cannot start: Invalid port configuration")
            return
            
        with self._router_state_lock:  # Ensure atomic state change to prevent concurrent router operations
            if self._router_state_changing:
                return  # Operation already in progress
            self._router_state_changing = True
        try:
            # Apply current configuration
            config = self.get_current_config()

            # Initialize router core with GUI values
            self.router_core = SerialRouterCore(
                incoming_port=config["incoming_port"],
                incoming_baud=config["incoming_baud"],
                outgoing_baud=config["outgoing_baud"],
                outgoing_ports=config["outgoing_ports"]
            )
            
            # Setup logging integration
            if self.log_handler:
                self.router_core.logger.addHandler(self.log_handler)
                
            self.add_log_message(f"Starting router: {config['incoming_port']} <-> {config['outgoing_ports'][0]} & {config['outgoing_ports'][1]}")
            
            # Clean up existing thread first to prevent leaks
            if hasattr(self, 'control_thread') and self.control_thread:
                if self.control_thread.isRunning():
                    self.control_thread.quit()
                    if not self.control_thread.wait(3000):
                        self.add_log_message("WARNING: Control thread did not terminate cleanly")
                        self.control_thread.terminate()
                        self.control_thread.wait(1000)
                # Proper cleanup: ensure thread is fully stopped before clearing reference
                self.control_thread.deleteLater()  # Qt cleanup for thread object
                self.control_thread = None
            
            # Start router in background thread
            self.control_thread = RouterControlThread()
            self.control_thread.operation_complete.connect(self.on_operation_complete)
            self.control_thread.set_operation('start', self.router_core)
            self.control_thread.start()
            
            # Update UI state
            self.set_ui_state_starting()
            
        except Exception as e:
            self.add_log_message(f"Failed to start routing: {str(e)}")
            self.cleanup_router_core()
            self._router_state_changing = False
            
    def stop_routing(self):
        """Stop the serial routing process."""
        if not self.router_core:
            return
            
        with self._router_state_lock:  # Ensure atomic state change to prevent concurrent router operations
            if self._router_state_changing:
                return  # Operation already in progress
            self._router_state_changing = True
        self.add_log_message("Stopping serial routing...")
        
        try:
            # Clean up existing thread first to prevent leaks
            if hasattr(self, 'control_thread') and self.control_thread:
                if self.control_thread.isRunning():
                    self.control_thread.quit()
                    if not self.control_thread.wait(3000):
                        self.add_log_message("WARNING: Control thread did not terminate cleanly")
                        self.control_thread.terminate()
                        self.control_thread.wait(1000)
                # Proper cleanup: ensure thread is fully stopped before clearing reference
                self.control_thread.deleteLater()  # Qt cleanup for thread object
                self.control_thread = None
            
            # Stop router in background thread
            self.control_thread = RouterControlThread()
            self.control_thread.operation_complete.connect(self.on_operation_complete)
            self.control_thread.set_operation('stop', self.router_core)
            self.control_thread.start()
            
            # Update UI state
            self.set_ui_state_stopping()
            
        except Exception as e:
            self.add_log_message(f"Error stopping routing: {str(e)}")
            self._router_state_changing = False
            
    def on_operation_complete(self, success: bool, message: str):
        """Handle completion of router operations."""
        self.add_log_message(message)
        
        if success:
            if "started" in message.lower():
                self.set_ui_state_running()
                self._router_state_changing = False
            elif "stopped" in message.lower():
                self.set_ui_state_stopped()
                self.cleanup_router_core()
                self._router_state_changing = False
        else:
            # Operation failed, show error state then transition to stopped
            self.enhanced_status.set_state(EnhancedStatusWidget.STATE_ERROR)
            # After a brief delay, transition to stopped state
            QTimer.singleShot(2000, self._handle_failed_operation)  # Direct method reference prevents reference issues
            
    def _handle_failed_operation(self):
        """Handle failed router operations with proper cleanup."""
        self.set_ui_state_stopped()
        self.cleanup_router_core()
        self._router_state_changing = False
            
    def set_ui_state_starting(self):
        """Set UI to starting state."""
        self.ribbon.set_routing_state(False)
        self.ribbon.set_busy(True)
        self.enhanced_status.set_state(EnhancedStatusWidget.STATE_STARTING)
        
    def set_ui_state_running(self):
        """Set UI to running state."""
        self.ribbon.set_routing_state(True)
        self.ribbon.set_busy(False)
        self.enhanced_status.set_state(EnhancedStatusWidget.STATE_ACTIVE)

        # Lock port configuration during routing
        self.incoming_port_combo.setEnabled(False)
        self.outgoing_port1_combo.setEnabled(False)
        self.outgoing_port2_combo.setEnabled(False)

        # Update connection diagram with active state
        self.update_connection_diagram_state()
        
    def set_ui_state_stopping(self):
        """Set UI to stopping state."""
        self.ribbon.set_routing_state(False)
        self.ribbon.set_busy(True)
        self.enhanced_status.set_state(EnhancedStatusWidget.STATE_STOPPING)
        
    def set_ui_state_stopped(self):
        """Set UI to stopped state."""
        self.ribbon.set_routing_state(False)
        self.ribbon.set_busy(False)
        self.enhanced_status.set_state(EnhancedStatusWidget.STATE_OFFLINE)

        # Unlock port configuration when routing stops
        self.incoming_port_combo.setEnabled(True)
        self.outgoing_port1_combo.setEnabled(True)
        self.outgoing_port2_combo.setEnabled(True)

        # Reset connection diagram to inactive state
        if self.connection_diagram:
            port1, port2 = self._get_selected_outgoing_ports()
            self.connection_diagram.set_connection_states({
                port1: False,
                port2: False
            })
        
    def update_connection_diagram_state(self):
        """Update connection diagram based on current router status."""
        if not self.router_core:
            return
            
        try:
            status = self.router_core.get_status()
            port_connections = status.get("port_connections", {})

            # Update connection states based on actual port status
            port1, port2 = self._get_selected_outgoing_ports()
            connection_states = {}
            for port in [port1, port2]:
                if port in port_connections:
                    connection_states[port] = port_connections[port].get("connected", False)
                else:
                    connection_states[port] = False

            if self.connection_diagram:
                self.connection_diagram.set_connection_states(connection_states)
            
        except Exception as e:
            # Fallback to basic active state
            if self.connection_diagram:
                port1, port2 = self._get_selected_outgoing_ports()
                self.connection_diagram.set_connection_states({
                    port1: True,
                    port2: True
                })
        
    def update_status_display(self):
        """Update the real-time status display with advanced metrics."""
        if not self.router_core or self._router_state_changing:
            # Reset displays when not running
            self.uptime_label.setText("0 hours")
            self.connections_label.setText("0/3")
            self.health_status_label.setText("Offline")
            self.health_status_label.setProperty("class", "metric-value status-error")
            self.health_status_label.setStyleSheet("color: #757575; font-weight: 600;")  # Gray for offline
            self.thread_status_label.setText("0/3 Active")
            self.thread_status_label.setProperty("class", "metric-value status-error")
            self.thread_status_label.setStyleSheet("color: #757575; font-weight: 600;")  # Gray for offline
            self.error_count_label.setText("0")
            self.error_count_label.setStyleSheet("color: #2e7d32; font-weight: 600;")  # Green for no errors
            self.queue_util_label.setText("0%")
            self.session_duration_label.setText("0h 0m")
            self.last_reset_label.setText("Never")

            # Reset port widgets
            if hasattr(self, 'port1_bytes_out'):
                self.port1_bytes_out.setText("0 bytes")
                self.port1_rate_out.setText("0 B/s")
                self.port1_bytes_in.setText("0 bytes")
                self.port1_rate_in.setText("0 B/s")

            if hasattr(self, 'port2_bytes_out'):
                self.port2_bytes_out.setText("0 bytes")
                self.port2_rate_out.setText("0 B/s")
                self.port2_bytes_in.setText("0 bytes")
                self.port2_rate_in.setText("0 B/s")

            if hasattr(self, 'bytes_routed_label'):
                self.bytes_routed_label.setText("0 bytes")
                self.rate_routed_label.setText("0 B/s")
            return
            
        try:
            status = self.router_core.get_status()
            critical_metrics = status.get("critical_metrics", {})
            
            # Update connection diagram state
            self.update_connection_diagram_state()
            
            # Update Critical Metrics Display
            
            # System uptime
            uptime_hours = critical_metrics.get("system_uptime_hours", 0)
            if uptime_hours < 1:
                uptime_minutes = uptime_hours * 60
                self.uptime_label.setText(f"{uptime_minutes:.1f} min")
            elif uptime_hours < 24:
                self.uptime_label.setText(f"{uptime_hours:.1f} hours")
            else:
                uptime_days = uptime_hours / 24
                self.uptime_label.setText(f"{uptime_days:.1f} days")
            
            # Active connections with color coding
            connections_status = critical_metrics.get("active_connections", "0/3")
            self.connections_label.setText(connections_status)
            if connections_status.startswith("3/3"):
                self.connections_label.setProperty("class", "connection-display status-success")
                self.connections_label.setStyleSheet("color: #2e7d32; font-weight: 600;")  # Green
            elif "0/3" in connections_status:
                self.connections_label.setProperty("class", "connection-display status-error")
                self.connections_label.setStyleSheet("color: #d32f2f; font-weight: 600;")  # Red
            else:
                self.connections_label.setProperty("class", "connection-display status-warning")
                self.connections_label.setStyleSheet("color: #f57c00; font-weight: 600;")  # Orange
            
            # Current throughput
            throughput_bps = critical_metrics.get("current_throughput_bps", 0)
            if throughput_bps > 1024:
                self.throughput_label.setText(f"{throughput_bps/1024:.1f} KB/sec")
            else:
                self.throughput_label.setText(f"{throughput_bps:.0f} bytes/sec")
            
            if throughput_bps > 0:
                self.throughput_label.setProperty("class", "throughput-display status-success")
            else:
                self.throughput_label.setProperty("class", "throughput-display status-warning")
            
            # Last activity
            seconds_since_activity = critical_metrics.get("seconds_since_last_activity", float('inf'))
            if seconds_since_activity == float('inf'):
                self.last_activity_label.setText("Never")
                self.last_activity_label.setProperty("class", "activity-display status-error")
            elif seconds_since_activity < 60:
                self.last_activity_label.setText(f"{seconds_since_activity:.1f}s ago")
                self.last_activity_label.setProperty("class", "activity-display status-success")
            elif seconds_since_activity < 3600:
                minutes = seconds_since_activity / 60
                self.last_activity_label.setText(f"{minutes:.1f}m ago")
                self.last_activity_label.setProperty("class", "activity-display status-warning")
            else:
                hours = seconds_since_activity / 3600
                self.last_activity_label.setText(f"{hours:.1f}h ago")
                self.last_activity_label.setProperty("class", "activity-display status-error")
            
            # Data loss events
            data_loss = critical_metrics.get("data_loss_events_24h", 0)
            self.data_loss_label.setText(str(data_loss))
            if data_loss == 0:
                self.data_loss_label.setProperty("class", "data-loss-display status-success")
            else:
                self.data_loss_label.setProperty("class", "data-loss-display status-error")
            
            # Error rate
            error_rate = critical_metrics.get("error_rate_per_hour", 0)
            self.error_rate_label.setText(f"{error_rate:.1f}/hour")
            if error_rate == 0:
                self.error_rate_label.setProperty("class", "error-rate-display status-success")
            elif error_rate < 5:
                self.error_rate_label.setProperty("class", "error-rate-display status-warning")
            else:
                self.error_rate_label.setProperty("class", "error-rate-display status-error")
            
            # Queue utilization with color coding
            queue_util = critical_metrics.get("avg_queue_utilization_percent", 0)
            self.queue_util_label.setText(f"{queue_util:.1f}%")
            if queue_util < 50:
                self.queue_util_label.setProperty("class", "queue-display status-success")
                self.queue_util_label.setStyleSheet("color: #2e7d32; font-weight: 600;")  # Green
            elif queue_util < 80:
                self.queue_util_label.setProperty("class", "queue-display status-warning")
                self.queue_util_label.setStyleSheet("color: #f57c00; font-weight: 600;")  # Orange
            else:
                self.queue_util_label.setProperty("class", "queue-display status-error")
                self.queue_util_label.setStyleSheet("color: #d32f2f; font-weight: 600;")  # Red
            
            # Health status with color coding
            system_health = status.get("system_health", {})
            health_status = system_health.get("overall_health_status", "UNKNOWN")
            self.health_status_label.setText(health_status)

            if health_status == "EXCELLENT":
                self.health_status_label.setProperty("class", "health-display status-excellent")
                self.health_status_label.setStyleSheet("color: #2e7d32; font-weight: 600;")  # Dark green
            elif health_status == "GOOD":
                self.health_status_label.setProperty("class", "health-display status-success")
                self.health_status_label.setStyleSheet("color: #388e3c; font-weight: 600;")  # Green
            elif health_status == "WARNING":
                self.health_status_label.setProperty("class", "health-display status-warning")
                self.health_status_label.setStyleSheet("color: #f57c00; font-weight: 600;")  # Orange
            elif health_status == "CRITICAL":
                self.health_status_label.setProperty("class", "health-display status-error")
                self.health_status_label.setStyleSheet("color: #d32f2f; font-weight: 600;")  # Red
            else:
                self.health_status_label.setProperty("class", "health-display status-unknown")
                self.health_status_label.setStyleSheet("color: #757575; font-weight: 600;")  # Gray
            
            # Legacy Thread health display with color coding
            active_threads = status.get("active_threads", 0)
            self.thread_status_label.setText(f"{active_threads}/3 Active")
            if active_threads == 3:
                self.thread_status_label.setProperty("class", "thread-status status-success")
                self.thread_status_label.setStyleSheet("color: #2e7d32; font-weight: 600;")  # Dark green
            elif active_threads > 0:
                self.thread_status_label.setProperty("class", "thread-status status-warning")
                self.thread_status_label.setStyleSheet("color: #f57c00; font-weight: 600;")  # Orange
            else:
                self.thread_status_label.setProperty("class", "thread-status status-error")
                self.thread_status_label.setStyleSheet("color: #d32f2f; font-weight: 600;")  # Red
                
            # Data flow tracking - Updated for new tree-style UI
            bytes_data = status.get("bytes_transferred", {})
            session_totals = status.get("session_totals", {})
            transfer_rates = status.get("transfer_rates", {})

            # Get the actual incoming port name from status
            incoming_port = status.get("incoming_port", "COM54")

            # Get currently selected outgoing ports
            port1, port2 = self._get_selected_outgoing_ports()

            # Update incoming port header dynamically
            if hasattr(self, 'incoming_header'):
                self.incoming_header.setText(f"└─ Port {incoming_port}")

            # Port headers are static "Port 1" and "Port 2" - no dynamic updates needed

            # Helper function to format bytes
            def format_bytes(count):
                if count > 1_000_000:
                    return f"{count/1_000_000:.1f} MB"
                elif count > 1024:
                    return f"{count/1024:.1f} KB"
                else:
                    return f"{count} bytes"

            # Helper function to format rate
            def format_rate(rate):
                if rate > 1024:
                    return f"{rate/1024:.1f} KB/s"
                else:
                    return f"{rate:.0f} B/s"

            # Update Port 1: Router → Port1 (outbound)
            out1_direction = f"{incoming_port}->{port1.replace('COM', '')}&{port2.replace('COM', '')}"
            out1_bytes = bytes_data.get(out1_direction, 0)
            out1_rate = transfer_rates.get(out1_direction, 0)
            out1_session = session_totals.get(out1_direction, 0)

            if hasattr(self, 'port1_bytes_out'):
                self.port1_bytes_out.setText(format_bytes(out1_bytes))
                self.port1_rate_out.setText(format_rate(out1_rate))
                if out1_session > 0:
                    self.port1_bytes_out.setToolTip(f"Session Total: {format_bytes(out1_session)}")
                else:
                    self.port1_bytes_out.setToolTip("")

            # Update Port 1: Port1 → Router (inbound from client)
            in1_direction = f"{port1}->Incoming"
            in1_bytes = bytes_data.get(in1_direction, 0)
            in1_rate = transfer_rates.get(in1_direction, 0)
            in1_session = session_totals.get(in1_direction, 0)

            if hasattr(self, 'port1_bytes_in'):
                self.port1_bytes_in.setText(format_bytes(in1_bytes))
                self.port1_rate_in.setText(format_rate(in1_rate))
                if in1_session > 0:
                    self.port1_bytes_in.setToolTip(f"Session Total: {format_bytes(in1_session)}")
                else:
                    self.port1_bytes_in.setToolTip("")

            # Update Port 2: Router → Port2 (outbound) - shares same direction as port1
            if hasattr(self, 'port2_bytes_out'):
                self.port2_bytes_out.setText(format_bytes(out1_bytes))
                self.port2_rate_out.setText(format_rate(out1_rate))
                if out1_session > 0:
                    self.port2_bytes_out.setToolTip(f"Session Total: {format_bytes(out1_session)}")
                else:
                    self.port2_bytes_out.setToolTip("")

            # Update Port 2: Port2 → Router (inbound from client)
            in2_direction = f"{port2}->Incoming"
            in2_bytes = bytes_data.get(in2_direction, 0)
            in2_rate = transfer_rates.get(in2_direction, 0)
            in2_session = session_totals.get(in2_direction, 0)

            if hasattr(self, 'port2_bytes_in'):
                self.port2_bytes_in.setText(format_bytes(in2_bytes))
                self.port2_rate_in.setText(format_rate(in2_rate))
                if in2_session > 0:
                    self.port2_bytes_in.setToolTip(f"Session Total: {format_bytes(in2_session)}")
                else:
                    self.port2_bytes_in.setToolTip("")

            # Update Incoming Port: Total routed (same as outbound)
            if hasattr(self, 'bytes_routed_label'):
                self.bytes_routed_label.setText(format_bytes(out1_bytes))
                self.rate_routed_label.setText(format_rate(out1_rate))
                if out1_session > 0:
                    self.bytes_routed_label.setToolTip(f"Session Total: {format_bytes(out1_session)}")
                else:
                    self.bytes_routed_label.setToolTip("")

            # Update session duration
            uptime_hours = critical_metrics.get("system_uptime_hours", 0)
            if uptime_hours < 1:
                uptime_minutes = int(uptime_hours * 60)
                self.session_duration_label.setText(f"{uptime_minutes}m")
            elif uptime_hours < 24:
                hours = int(uptime_hours)
                minutes = int((uptime_hours - hours) * 60)
                self.session_duration_label.setText(f"{hours}h {minutes}m")
            else:
                uptime_days = uptime_hours / 24
                self.session_duration_label.setText(f"{uptime_days:.1f} days")
            
            # Also try to get PortManager specific stats if available
            port_connections = status.get("port_connections", {})
            if port_connections:
                # Calculate total bytes safely (only sum integer values, skip dict stats)
                total_bytes = 0
                for key, value in bytes_data.items():
                    if isinstance(value, int):  # Only sum integer values, skip port_stats dicts
                        total_bytes += value
                
                # Update labels with PortManager data if routing stats are empty
                if total_bytes == 0:
                    # Show PortManager port stats as fallback
                    port1, port2 = self._get_selected_outgoing_ports()
                    for port_name in [incoming_port, port1, port2]:
                        if port_name in port_connections:
                            # This provides additional monitoring even when no data flows
                            pass
                    
            # Error counts - Enhanced with PortManager errors
            error_data = status.get("error_counts", {})
            system_health = status.get("system_health", {})
            
            # Safely sum router errors (only integers, skip any dict values)
            router_errors = 0
            for key, value in error_data.items():
                if isinstance(value, int):
                    router_errors += value
            
            port_errors = system_health.get("total_port_errors", 0)
            total_errors = router_errors + port_errors
            
            self.error_count_label.setText(str(total_errors))
            if total_errors > 0:
                self.error_count_label.setProperty("class", "error-count status-error")
                self.error_count_label.setStyleSheet("color: #d32f2f; font-weight: 600;")  # Red for errors
            else:
                self.error_count_label.setProperty("class", "error-count status-success")
                self.error_count_label.setStyleSheet("color: #2e7d32; font-weight: 600;")  # Green for no errors
                
            # Thread restart counts - Safe sum for mixed data types
            restart_data = status.get("thread_restart_counts", {})
            total_restarts = 0
            for key, value in restart_data.items():
                if isinstance(value, int):
                    total_restarts += value
            self.restart_count_label.setText(str(total_restarts))
            
            # Add connection status indicators using PortManager data
            port_connections = status.get("port_connections", {})
            if port_connections:
                connected_ports = sum(1 for p in port_connections.values() if p.get("connected", False))
                total_ports = len(port_connections)
                
                # Update thread status to show port connections
                if total_ports > 0:
                    connection_status = f" ({connected_ports}/{total_ports} ports)"
                    current_text = self.thread_status_label.text()
                    if "ports)" not in current_text:  # Avoid duplicate status
                        self.thread_status_label.setText(current_text + connection_status)
            
        except Exception as e:
            # More specific error tracking without spamming
            import time
            error_type = type(e).__name__
            if not hasattr(self, '_last_status_error') or self._last_status_error != error_type:
                self.add_log_message(f"Status error ({error_type}): {str(e)[:100]}")
                self._last_status_error = error_type
                self._last_status_error_time = time.time()
            
    def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration from UI controls."""
        outgoing_ports = []
        if hasattr(self, 'outgoing_port1_combo') and hasattr(self, 'outgoing_port2_combo'):
            outgoing_ports = [
                self.outgoing_port1_combo.currentText(),
                self.outgoing_port2_combo.currentText()
            ]
        else:
            outgoing_ports = ["COM131", "COM141"]  # Fallback

        return {
            "incoming_port": self.incoming_port_combo.currentText(),
            "incoming_baud": self.incoming_baud_spin.value(),
            "outgoing_baud": self.outgoing_baud_spin.value(),
            "outgoing_ports": outgoing_ports,
            "timeout": 0.1,
            "retry_delay_max": 30,
            "log_level": "INFO"
        }

    def load_config(self):
        """Load configuration from file with validation."""
        try:
            with open('serial_router_config.json', 'r') as f:
                config = json.load(f)

            # Get list of available com0com ports for validation
            com0com_ports = self.port_enumerator.get_com0com_ports()
            available_port_names = [p.port_name for p in com0com_ports]

            # Apply saved outgoing port 1 with validation
            if 'outgoing_port1' in config and hasattr(self, 'outgoing_port1_combo'):
                port1 = config['outgoing_port1']
                index = self.outgoing_port1_combo.findText(port1)
                if index >= 0:
                    # Port exists in dropdown, apply it
                    self.outgoing_port1_combo.setCurrentIndex(index)
                else:
                    # Port no longer exists
                    self.add_log_message(f"Warning: Saved port {port1} no longer available, using default")

            # Apply saved outgoing port 2 with validation
            if 'outgoing_port2' in config and hasattr(self, 'outgoing_port2_combo'):
                port2 = config['outgoing_port2']
                index = self.outgoing_port2_combo.findText(port2)
                if index >= 0:
                    # Port exists in dropdown, apply it
                    self.outgoing_port2_combo.setCurrentIndex(index)
                else:
                    # Port no longer exists
                    self.add_log_message(f"Warning: Saved port {port2} no longer available, using default")

            self.add_log_message("Configuration loaded from file")

        except FileNotFoundError:
            pass  # No config file yet, use defaults
        except Exception as e:
            self.add_log_message(f"Error loading configuration: {e}")

    def save_config(self):
        """Save current configuration to file."""
        try:
            config = {}
            if hasattr(self, 'outgoing_port1_combo'):
                config['outgoing_port1'] = self.outgoing_port1_combo.currentText()
            if hasattr(self, 'outgoing_port2_combo'):
                config['outgoing_port2'] = self.outgoing_port2_combo.currentText()

            with open('serial_router_config.json', 'w') as f:
                json.dump(config, f, indent=2)

        except Exception as e:
            self.add_log_message(f"Error saving configuration: {e}")
        
            
    def clear_activity_log(self):
        """Clear the activity log."""
        self.activity_log.clear()
        self.add_log_message("Activity log cleared")
        
    def closeEvent(self, event):
        """Handle application close event - minimize to tray if available."""
        if self.tray_icon and self.tray_icon.isVisible():
            # Minimize to tray
            self.hide()
            self.tray_icon.showMessage(
                "SerialRouter",
                "Application minimized to tray",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()
        else:
            # No tray available, perform full shutdown
            self.perform_shutdown()
            event.accept()
            
    def perform_shutdown(self):
        """Perform complete application shutdown."""
        self.add_log_message("Application shutdown initiated...")
        
        # Stop status timer first to prevent updates during shutdown
        self.status_timer.stop()
        
        # Shutdown router if active
        if self.is_routing_active():
            self.add_log_message("Stopping router for shutdown...")
            if self.router_core:
                try:
                    self.router_core.stop()
                    # Give router time to clean up
                    QApplication.processEvents()
                    time.sleep(0.5)
                except Exception as e:
                    self.add_log_message(f"Error during router shutdown: {str(e)}")
                
        # Clean up control thread with force termination if needed
        if self.control_thread and self.control_thread.isRunning():
            self.add_log_message("Waiting for control thread to terminate...")
            self.control_thread.quit()
            if not self.control_thread.wait(5000):  # Wait up to 5 seconds
                self.add_log_message("Force terminating control thread...")
                self.control_thread.terminate()
                self.control_thread.wait(2000)
                
        # Save configuration before exit
        self.save_config()

        # Final cleanup
        self.cleanup_router_core()
        if self.tray_icon:
            self.tray_icon.hide()
        self.add_log_message("Application shutdown complete")
    
    def apply_theme(self):
        """Apply the Windows theme to the application."""
        theme_css = resource_manager.load_theme()
        if theme_css:
            self.setStyleSheet(theme_css)
            # Force style refresh for all widgets with custom properties
            self.style().unpolish(self)
            self.style().polish(self)
            print("Windows theme applied successfully")
        else:
            print("Warning: Could not load Windows theme, using default styling")


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    
    # Set Fusion style for consistent cross-platform appearance
    app.setStyle('Fusion')
    
    # Set application properties
    app.setApplicationName("SerialRouter")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("SerialRouter")
    
    # Set application icon globally
    from src.gui.resources import resource_manager
    app_icon = resource_manager.get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    
    # Create and show main window
    window = SerialRouterMainWindow()
    window.show()
    
    # Add startup message
    window.add_log_message("SerialRouter initialized")
    window.add_log_message("Ready to configure and start serial routing")
    
    # Start application event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
