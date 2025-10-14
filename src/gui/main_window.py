
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
    QGridLayout, QSpinBox, QProgressBar, QSplitter, QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt, QSharedMemory, QUrl
from PyQt6.QtGui import QFont, QPalette, QIcon, QAction, QDesktopServices

import serial.tools.list_ports
from src.core.router_engine import SerialRouterCore
from src.core.port_enumerator import PortEnumerator, PortType
from src.gui.resources import resource_manager
from src.gui.components import RibbonToolbar, ConnectionDiagramWidget, EnhancedStatusWidget, DataFlowMonitorWidget
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
        self.tray_icon.setToolTip("Serial Router v1.0.2")
        
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
        # Use QWidget with title label (no border)
        config_group = QWidget()
        outer_layout = QVBoxLayout(config_group)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(5)

        # Add title label
        title_label = QLabel("Port Configuration")
        title_label.setStyleSheet("font-weight: bold;")
        outer_layout.addWidget(title_label)

        # Create container for configuration content
        config_content = QWidget()
        config_layout = QGridLayout(config_content)
        config_layout.setContentsMargins(0, 0, 0, 0)
        
        # Minimal combobox stylesheet - transparent background blending with UI
        minimal_combo_style = """
            QComboBox {
                background-color: transparent;
                border: 1px solid palette(mid);
                border-radius: 3px;
                padding: 3px 8px;
            }
            QComboBox:hover {
                border: 1px solid palette(highlight);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 2px solid transparent;
                border-right: 2px solid transparent;
                border-top: 2px solid palette(text);
                margin-right: 4px;
            }
        """

        # Incoming Port Selection
        config_layout.addWidget(QLabel("Incoming Port:"), 0, 0)
        self.incoming_port_combo = QComboBox()
        self.incoming_port_combo.setMinimumWidth(120)
        self.incoming_port_combo.setStyleSheet(minimal_combo_style)
        # Connect port selection changes to diagram updates
        self.incoming_port_combo.currentTextChanged.connect(self.on_incoming_port_changed)
        config_layout.addWidget(self.incoming_port_combo, 0, 1)

        # Baud Rate (applies to both incoming and outgoing)
        config_layout.addWidget(QLabel("Baud Rate:"), 1, 0)
        self.baud_spin = QComboBox()
        self.baud_spin.addItems(['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200', '230400', '460800', '921600'])
        self.baud_spin.setCurrentText('115200')
        self.baud_spin.setMinimumWidth(120)
        self.baud_spin.setStyleSheet(minimal_combo_style)
        config_layout.addWidget(self.baud_spin, 1, 1)

        # Outgoing Port 1
        config_layout.addWidget(QLabel("Outgoing Port 1:"), 2, 0)
        self.outgoing_port1_combo = QComboBox()
        self.outgoing_port1_combo.setMinimumWidth(120)
        self.outgoing_port1_combo.setStyleSheet(minimal_combo_style)
        self.outgoing_port1_combo.currentTextChanged.connect(self.on_outgoing_port_changed)
        config_layout.addWidget(self.outgoing_port1_combo, 2, 1)

        # Outgoing Port 2
        config_layout.addWidget(QLabel("Outgoing Port 2:"), 3, 0)
        self.outgoing_port2_combo = QComboBox()
        self.outgoing_port2_combo.setMinimumWidth(120)
        self.outgoing_port2_combo.setStyleSheet(minimal_combo_style)
        self.outgoing_port2_combo.currentTextChanged.connect(self.on_outgoing_port_changed)
        config_layout.addWidget(self.outgoing_port2_combo, 3, 1)

        # Add config content to outer layout
        outer_layout.addWidget(config_content)

        # Add control buttons at bottom of configuration panel
        control_frame = QFrame()
        control_layout = QVBoxLayout(control_frame)
        control_layout.setSpacing(15)
        control_layout.setContentsMargins(0, 0, 0, 0)

        # Enhanced Status display (borderless)
        status_group = QWidget()
        status_outer_layout = QVBoxLayout(status_group)
        status_outer_layout.setContentsMargins(0, 0, 0, 0)
        status_outer_layout.setSpacing(5)

        # Add title label
        status_title = QLabel("Router Status")
        status_title.setStyleSheet("font-weight: bold;")
        status_outer_layout.addWidget(status_title)

        # Create container for status content
        status_content = QWidget()
        status_layout = QVBoxLayout(status_content)
        status_layout.setContentsMargins(5, 5, 5, 0)  # Remove bottom margin

        # Enhanced status widget
        self.enhanced_status = EnhancedStatusWidget()
        status_layout.addWidget(self.enhanced_status)

        # Add status content to outer layout
        status_outer_layout.addWidget(status_content)

        control_layout.addWidget(status_group)

        # Connection diagram (borderless)
        diagram_group = QWidget()
        diagram_outer_layout = QVBoxLayout(diagram_group)
        diagram_outer_layout.setContentsMargins(0, 0, 0, 0)
        diagram_outer_layout.setSpacing(5)

        # Add title label
        diagram_title = QLabel("Port Connections")
        diagram_title.setStyleSheet("font-weight: bold;")
        diagram_outer_layout.addWidget(diagram_title)

        # Create container for diagram content
        diagram_content = QWidget()
        diagram_layout = QVBoxLayout(diagram_content)

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

        # Add diagram content to outer layout
        diagram_outer_layout.addWidget(diagram_content)

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
        self.data_flow_monitor = DataFlowMonitorWidget()
        monitoring_layout.addWidget(self.data_flow_monitor)
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
        self.ribbon.launch_terminal.connect(self.launch_terminal)
        self.ribbon.refresh_ports.connect(self.refresh_available_ports)
        self.ribbon.view_stats.connect(self.show_routing_stats)
        self.ribbon.clear_log.connect(self.clear_activity_log)
        self.ribbon.show_help.connect(self.show_help_information)
        self.ribbon.show_about.connect(self.show_about_dialog)
    
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

    def launch_terminal(self):
        """Launch serial terminal application."""
        try:
            subprocess.Popen([r"C:\Program Files (x86)\com0com\SerialTerminal\Serial Terminal.exe"],
                            creationflags=subprocess.DETACHED_PROCESS)
            self.add_log_message("Launched serial terminal")
        except Exception as e:
            self.add_log_message(f"Could not launch serial terminal: {str(e)}")
    
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
        """Show help dialog with user choice."""
        # Show dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Choose Help Type")
        msg_box.setText("How would you like to view help information?")
        msg_box.setIcon(QMessageBox.Icon.Question)

        pdf_button = msg_box.addButton("Open PDF Guide", QMessageBox.ButtonRole.YesRole)
        console_button = msg_box.addButton("Console Help", QMessageBox.ButtonRole.NoRole)
        cancel_button = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

        msg_box.setDefaultButton(pdf_button)
        msg_box.exec()

        clicked_button = msg_box.clickedButton()

        if clicked_button == pdf_button:
            self.open_pdf_guide()
        elif clicked_button == console_button:
            self.show_console_help()
        # Cancel - do nothing

    def open_pdf_guide(self):
        """Open the PDF guide with system default viewer."""
        guide_path = resource_manager.get_guide_path("guide.pdf")

        if guide_path and guide_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide_path)))
        else:
            QMessageBox.warning(
                self,
                "Guide Not Found",
                "The operation guide PDF could not be found.\n\n"
                "Expected location: guide/guide.pdf"
            )

    def show_console_help(self):
        """Show help information in console (current behavior)."""
        port1, port2 = self._get_selected_outgoing_ports()
        self.add_log_message(" ╔══════════════════════════════════════════════════════════════════╗")
        self.add_log_message(" ║                 Serial Router - Operational Guide                ║")
        self.add_log_message(" ╠══════════════════════════════════════════════════════════════════╣")
        self.add_log_message(" ║ • Routes incoming port to COM131 & COM41 (Default port pairs)    ║")
        self.add_log_message(" ║ • Connect applications to paired endpoints (COM132 & COM142)     ║")
        self.add_log_message(" ║ • Select START ROUTING to begin, STOP ROUTING to end             ║")
        self.add_log_message(" ║ • Configure incoming port before starting operations             ║")
        self.add_log_message(" ╚══════════════════════════════════════════════════════════════════╝")

    def show_about_dialog(self):
        """Show the About dialog."""
        AboutDialog.show_about(self)

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
        

    def create_activity_log_panel(self, parent_widget):
        """Create the activity log panel for the right pane."""
        layout = QVBoxLayout(parent_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Activity Log (borderless)
        log_group = QWidget()
        log_outer_layout = QVBoxLayout(log_group)
        log_outer_layout.setContentsMargins(0, 0, 0, 0)
        log_outer_layout.setSpacing(5)

        # Add title label
        log_title = QLabel("Activity Log")
        log_title.setStyleSheet("font-weight: bold;")
        log_outer_layout.addWidget(log_title)

        # Create container for log content
        log_content = QWidget()
        log_layout = QVBoxLayout(log_content)

        # Log display
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)

        # Set monospace font for proper Unicode box-drawing character alignment
        # Windows-optimized font stack for clean, modern appearance
        monospace_font = QFont("Cascadia Code, Cascadia Mono, Consolas, 'Courier New', monospace")
        monospace_font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.activity_log.setFont(monospace_font)

        # Ultra clean minimal design - match main window background, no border
        self.activity_log.setStyleSheet("""
            QTextEdit {
                background-color: palette(window);
                border: none;
            }
        """)

        log_layout.addWidget(self.activity_log)

        # Add log content to outer layout
        log_outer_layout.addWidget(log_content)

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
        # Suppress validation warnings while repopulating combo boxes
        self._initializing = True

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
                # No ports available - show placeholder and inform user
                self.incoming_port_combo.addItem("(No COM ports detected)")
                self.add_log_message("No COM ports found - connect device and click Refresh Ports")
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

                # Smart selection: previous selection > first port
                if current_port and current_port in port_items:
                    self.incoming_port_combo.setCurrentText(current_port)
                else:
                    # Auto-select first available port
                    self.incoming_port_combo.setCurrentIndex(0)
            else:
                # No ports found - show placeholder
                self.incoming_port_combo.addItem("(No COM ports detected)")
            
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
            # Show error state - user must fix and refresh
            self.incoming_port_combo.addItem("(Port scan failed)")
            self.add_log_message("Port scan failed - click Refresh Ports to retry")
        finally:
            # Re-enable validation warnings after refresh is complete
            self._initializing = False

    def validate_selected_port(self) -> bool:
        """Enhanced port validation using port enumerator with exclusion checks."""
        port = self.incoming_port_combo.currentText()
        # Check for empty, placeholder, or error states
        if not port or port.startswith("("):
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
        # Check if incoming port is selected
        incoming_port = self.incoming_port_combo.currentText()
        if not incoming_port or incoming_port.startswith("("):
            self.add_log_message("Cannot start: Please select an incoming COM port")
            return

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
            self.data_flow_monitor.reset_display()
            return

        try:
            status = self.router_core.get_status()

            # Update connection diagram state (stays in main_window)
            self.update_connection_diagram_state()

            # Delegate all stats display to monitor widget
            incoming_port = self.incoming_port_combo.currentText()
            port1, port2 = self._get_selected_outgoing_ports()
            self.data_flow_monitor.update_display(status, incoming_port, port1, port2)

        except Exception as e:
            # Log critical errors
            self.add_log_message(f"Status update error: {str(e)}")
            
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
            "incoming_baud": int(self.baud_spin.currentText()),
            "outgoing_baud": int(self.baud_spin.currentText()),
            "outgoing_ports": outgoing_ports,
            "timeout": 0.1,
            "retry_delay_max": 30,
            "log_level": "INFO"
        }

    def load_config(self):
        """Load configuration from file with validation."""
        try:
            with open('serial_router_config.json', 'r') as f:
                self.config = json.load(f)  # Store as instance variable

            # Get list of available com0com ports for validation
            com0com_ports = self.port_enumerator.get_com0com_ports()
            available_port_names = [p.port_name for p in com0com_ports]

            # Apply saved outgoing port 1 with validation
            if 'outgoing_port1' in self.config and hasattr(self, 'outgoing_port1_combo'):
                port1 = self.config['outgoing_port1']
                index = self.outgoing_port1_combo.findText(port1)
                if index >= 0:
                    # Port exists in dropdown, apply it
                    self.outgoing_port1_combo.setCurrentIndex(index)
                else:
                    # Port no longer exists
                    self.add_log_message(f"Warning: Saved port {port1} no longer available, using default")

            # Apply saved outgoing port 2 with validation
            if 'outgoing_port2' in self.config and hasattr(self, 'outgoing_port2_combo'):
                port2 = self.config['outgoing_port2']
                index = self.outgoing_port2_combo.findText(port2)
                if index >= 0:
                    # Port exists in dropdown, apply it
                    self.outgoing_port2_combo.setCurrentIndex(index)
                else:
                    # Port no longer exists
                    self.add_log_message(f"Warning: Saved port {port2} no longer available, using default")

            self.add_log_message("Configuration loaded from file")

        except FileNotFoundError:
            self.config = {}  # Initialize empty config
        except Exception as e:
            self.add_log_message(f"Error loading configuration: {e}")
            self.config = {}  # Initialize empty config on error

    def save_config(self):
        """Save current configuration to file."""
        try:
            if not hasattr(self, 'config'):
                self.config = {}

            # Update port configs
            if hasattr(self, 'outgoing_port1_combo'):
                self.config['outgoing_port1'] = self.outgoing_port1_combo.currentText()
            if hasattr(self, 'outgoing_port2_combo'):
                self.config['outgoing_port2'] = self.outgoing_port2_combo.currentText()

            with open('serial_router_config.json', 'w') as f:
                json.dump(self.config, f, indent=2)

        except Exception as e:
            self.add_log_message(f"Error saving configuration: {e}")
        
            
    def clear_activity_log(self):
        """Clear the activity log."""
        self.activity_log.clear()
        self.add_log_message("Activity log cleared")
        
    def closeEvent(self, event):
        """Handle application close event - minimize to tray or quit based on user choice."""
        # CRITICAL FIX: Add confirmation dialog to allow proper closing
        # Holding Shift while closing will quit directly without prompting
        if event.spontaneous() and self.tray_icon and self.tray_icon.isVisible():
            # Check if Shift key is held - if so, quit directly
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                # Shift held - quit directly
                self.perform_shutdown()
                event.accept()
                QApplication.quit()
                return

            # Ask user what they want to do with custom button labels
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Close Serial Router")
            msg_box.setText("What would you like to do?")
            msg_box.setInformativeText("Tip: Hold Shift while closing to quit directly without this prompt.")
            msg_box.setIcon(QMessageBox.Icon.Question)

            # Add custom buttons with clear labels
            minimize_button = msg_box.addButton("Minimize to Tray", QMessageBox.ButtonRole.YesRole)
            quit_button = msg_box.addButton("Quit Completely", QMessageBox.ButtonRole.NoRole)
            cancel_button = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

            msg_box.setDefaultButton(minimize_button)
            msg_box.exec()

            clicked_button = msg_box.clickedButton()

            if clicked_button == minimize_button:
                # Minimize to tray
                self.hide()
                self.tray_icon.showMessage(
                    "Serial Router",
                    "Application minimized to tray. Use tray menu to quit.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
                event.ignore()
            elif clicked_button == quit_button:
                # Quit completely
                self.perform_shutdown()
                event.accept()
                QApplication.quit()
            else:
                # Cancel - Do nothing
                event.ignore()
        else:
            # No tray available or programmatic close, perform full shutdown
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

    # CRITICAL FIX: Singleton check - prevent multiple instances
    shared_memory = QSharedMemory("SerialRouterSingleton_v1_0_2")

    # Try to create shared memory segment
    if not shared_memory.create(1):
        # Shared memory already exists - another instance is running
        QMessageBox.warning(
            None,
            "Serial Router Already Running",
            "Serial Router is already running.\n\n"
            "Please check your system tray or minimize the existing window.",
            QMessageBox.StandardButton.Ok
        )
        return 1

    # Set Fusion style for consistent cross-platform appearance
    app.setStyle('Fusion')

    # Set application properties
    app.setApplicationName("Serial Router")
    app.setApplicationVersion("1.0.2")
    app.setOrganizationName("Serial Router")

    # Set application icon globally
    from src.gui.resources import resource_manager
    app_icon = resource_manager.get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Create and show main window
    window = SerialRouterMainWindow()
    window.show()

    # Add startup message
    window.add_log_message("Serial Router initialized")
    window.add_log_message("Ready to configure and start serial routing")

    # Start application event loop
    exit_code = app.exec()

    # Cleanup shared memory on exit
    shared_memory.detach()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
