"""
SerialRouter GUI v2.0 - Production Integration
PyQt6 GUI wrapper for the production-hardened SerialRouterCore backend.

Features:
- Direct integration with SerialRouterCore
- Real-time monitoring and status updates
- Configuration management with JSON persistence
- Robust error handling and graceful shutdown
- Activity logging with custom log handler
"""

import sys
import json
import logging
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QTextEdit, QFrame, QGroupBox, 
    QGridLayout, QSpinBox, QProgressBar, QSplitter
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QIcon

import serial.tools.list_ports
from src.core.router_engine import SerialRouterCore
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
        
        # Monitoring
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        
        # Statistics tracking
        self.last_bytes_transferred = {}
        self.last_update_time = datetime.now()
        
        # Initialize UI
        self.init_ui()
        self.setup_logging()
        self.apply_theme()
        self.refresh_available_ports()
        
        # Connect log signal to handler
        self.log_message_signal.connect(self.add_log_message)
        
        # Start status monitoring
        self.status_timer.start(1000)  # 1 second updates
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("SerialRouter v2.0 - Production Control")
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
        
        # Outgoing Ports (Fixed)
        config_layout.addWidget(QLabel("Outgoing Ports:"), 2, 0)
        outgoing_label = QLabel("COM131, COM141 (Fixed)")
        outgoing_label.setProperty("class", "description")
        config_layout.addWidget(outgoing_label, 2, 1)
        
        # Outgoing Port Baud Rate
        config_layout.addWidget(QLabel("Outgoing Baud:"), 3, 0)
        self.outgoing_baud_spin = QSpinBox()
        self.outgoing_baud_spin.setRange(1200, 921600) 
        self.outgoing_baud_spin.setValue(115200)
        self.outgoing_baud_spin.setSingleStep(1200)
        config_layout.addWidget(self.outgoing_baud_spin, 3, 1)
        
        # Add control buttons at bottom of configuration panel
        control_frame = QFrame()
        control_layout = QVBoxLayout(control_frame)
        control_layout.setSpacing(15)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # Enhanced Status display
        status_group = QGroupBox("Router Status")
        status_layout = QVBoxLayout(status_group)
        
        # Enhanced status widget
        self.enhanced_status = EnhancedStatusWidget()
        status_layout.addWidget(self.enhanced_status)
        
        control_layout.addWidget(status_group)
        
        # Connection diagram
        diagram_group = QGroupBox("Port Connections")
        diagram_layout = QVBoxLayout(diagram_group)
        
        # Connection diagram widget
        self.connection_diagram = ConnectionDiagramWidget()
        diagram_layout.addWidget(self.connection_diagram)
        
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
        """Launch com0com setup utility."""
        try:
            subprocess.Popen([r"C:\Program Files (x86)\com0com\setupg.exe"], 
                            creationflags=subprocess.DETACHED_PROCESS)
            self.add_log_message("Launched com0com setup utility")
        except Exception as e:
            self.add_log_message(f"Could not launch setup utility: {str(e)}")
    
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
        self.add_log_message("╔══════════════════════════════════════════════════════════════════╗")
        self.add_log_message("║                   SerialRouter v2.0 - Operation Guide            ║")
        self.add_log_message("╠══════════════════════════════════════════════════════════════════╣")
        self.add_log_message("║ • Routes incoming port to COM131 & COM141 (virtual port pairs)   ║")
        self.add_log_message("║ • Connect applications to COM132 & COM142 (paired endpoints)     ║")
        self.add_log_message("║ • Select START ROUTING to begin, STOP ROUTING to end             ║")
        self.add_log_message("║ • Configure incoming port before starting operations             ║")
        self.add_log_message("╚══════════════════════════════════════════════════════════════════╝")
    
    def on_incoming_port_changed(self, port_name: str):
        """Handle incoming port selection changes."""
        if hasattr(self, 'connection_diagram') and port_name:
            self.connection_diagram.set_incoming_port(port_name)
    
    def create_control_group(self, parent_layout):
        """Legacy method - functionality moved to configuration panel."""
        pass
        
    def create_monitoring_group(self, parent_layout):
        """Create the real-time monitoring group with advanced metrics."""
        monitor_group = QGroupBox("Live Monitoring")
        monitor_layout = QGridLayout(monitor_group)
        
        # Critical System Status (Row 0)
        monitor_layout.addWidget(QLabel("System Uptime:"), 0, 0)
        self.uptime_label = QLabel("0 hours")
        self.uptime_label.setProperty("class", "uptime-display")
        monitor_layout.addWidget(self.uptime_label, 0, 1)
        
        monitor_layout.addWidget(QLabel("Active Connections:"), 0, 2)
        self.connections_label = QLabel("0/3")
        self.connections_label.setProperty("class", "connection-display")
        monitor_layout.addWidget(self.connections_label, 0, 3)
        
        # Throughput Metrics (Row 1)
        monitor_layout.addWidget(QLabel("Current Throughput:"), 1, 0)
        self.throughput_label = QLabel("0 bytes/sec")
        self.throughput_label.setProperty("class", "throughput-display")
        monitor_layout.addWidget(self.throughput_label, 1, 1)
        
        monitor_layout.addWidget(QLabel("Last Activity:"), 1, 2)
        self.last_activity_label = QLabel("N/A")
        self.last_activity_label.setProperty("class", "activity-display")
        monitor_layout.addWidget(self.last_activity_label, 1, 3)
        
        # Data Loss and Errors (Row 2)
        monitor_layout.addWidget(QLabel("Data Loss Events:"), 2, 0)
        self.data_loss_label = QLabel("0")
        self.data_loss_label.setProperty("class", "data-loss-display")
        monitor_layout.addWidget(self.data_loss_label, 2, 1)
        
        monitor_layout.addWidget(QLabel("Error Rate:"), 2, 2)
        self.error_rate_label = QLabel("0.0/hour")
        self.error_rate_label.setProperty("class", "error-rate-display")
        monitor_layout.addWidget(self.error_rate_label, 2, 3)
        
        # Queue and Performance (Row 3)
        monitor_layout.addWidget(QLabel("Queue Utilization:"), 3, 0)
        self.queue_util_label = QLabel("0%")
        self.queue_util_label.setProperty("class", "queue-display")
        monitor_layout.addWidget(self.queue_util_label, 3, 1)
        
        monitor_layout.addWidget(QLabel("Health Status:"), 3, 2)
        self.health_status_label = QLabel("Unknown")
        self.health_status_label.setProperty("class", "health-display")
        monitor_layout.addWidget(self.health_status_label, 3, 3)
        
        # Legacy Data Transfer Section (Rows 4-7)
        separator = QLabel("─" * 40)
        separator.setProperty("class", "separator")
        monitor_layout.addWidget(separator, 4, 0, 1, 4)
        
        monitor_layout.addWidget(QLabel("Data Transfer Details:"), 5, 0, 1, 4)
        
        # Incoming -> Outgoing
        monitor_layout.addWidget(QLabel("IN → OUT:"), 6, 0)
        self.bytes_in_out_label = QLabel("0 bytes")
        monitor_layout.addWidget(self.bytes_in_out_label, 6, 1)
        
        # COM131 -> Incoming
        monitor_layout.addWidget(QLabel("131 → IN:"), 6, 2)
        self.bytes_131_in_label = QLabel("0 bytes")
        monitor_layout.addWidget(self.bytes_131_in_label, 6, 3)
        
        # COM141 -> Incoming  
        monitor_layout.addWidget(QLabel("141 → IN:"), 7, 0)
        self.bytes_141_in_label = QLabel("0 bytes")
        monitor_layout.addWidget(self.bytes_141_in_label, 7, 1)
        
        # Thread Status
        monitor_layout.addWidget(QLabel("Thread Health:"), 7, 2)
        self.thread_status_label = QLabel("0/3 Active")
        self.thread_status_label.setProperty("class", "thread-status")
        monitor_layout.addWidget(self.thread_status_label, 7, 3)
        
        # Legacy Error and Restart Counts (Row 8)
        monitor_layout.addWidget(QLabel("Total Errors:"), 8, 0)
        self.error_count_label = QLabel("0")
        self.error_count_label.setProperty("class", "error-count")
        monitor_layout.addWidget(self.error_count_label, 8, 1)
        
        monitor_layout.addWidget(QLabel("Thread Restarts:"), 8, 2)
        self.restart_count_label = QLabel("0")
        monitor_layout.addWidget(self.restart_count_label, 8, 3)
        
        # Add stretch within the monitor_group to expand whitespace below stats
        monitor_layout.addWidget(QWidget(), 9, 0, 1, 4)  # Empty widget as spacer
        monitor_layout.setRowStretch(9, 1)  # Make row 9 expandable
        
        parent_layout.addWidget(monitor_group)
        
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
        """Refresh the list of available COM ports."""
        current_port = self.incoming_port_combo.currentText()
        self.incoming_port_combo.clear()
        
        try:
            ports = serial.tools.list_ports.comports()
            port_names = [port.device for port in sorted(ports, key=lambda x: x.device)]
            
            # Always include COM54 as the hardcoded incoming port for testing
            if "COM54" not in port_names:
                port_names.insert(0, "COM54")
            
            if port_names:
                self.incoming_port_combo.addItems(port_names)
                # Always set COM54 as the default selection
                self.incoming_port_combo.setCurrentText("COM54")
            else:
                self.incoming_port_combo.addItem("COM54")
                
            self.add_log_message(f"Found {len(port_names)} COM ports: {', '.join(port_names) if port_names else 'None'} (COM54 hardcoded for testing)")
            
        except Exception as e:
            self.add_log_message(f"Error refreshing ports: {str(e)}")
            self.incoming_port_combo.addItem("COM54")
            
    def is_routing_active(self) -> bool:
        """Check if routing is currently active."""
        return self.router_core is not None and self.router_core.running
        
    def start_routing(self):
        """Start the serial routing process."""
        if self.incoming_port_combo.currentText() in ["No COM ports available", "Error reading ports"]:
            self.add_log_message("Cannot start: No valid COM ports available")
            return
            
        try:
            # Apply current configuration
            config = self.get_current_config()
            
            # Initialize router core with GUI values
            self.router_core = SerialRouterCore(
                incoming_port=config["incoming_port"],
                incoming_baud=config["incoming_baud"],
                outgoing_baud=config["outgoing_baud"]
            )
            
            # Setup logging integration
            if self.log_handler:
                self.router_core.logger.addHandler(self.log_handler)
                
            self.add_log_message(f"Starting router: {config['incoming_port']} <-> COM131 & COM141")
            
            # Start router in background thread
            self.control_thread = RouterControlThread()
            self.control_thread.operation_complete.connect(self.on_operation_complete)
            self.control_thread.set_operation('start', self.router_core)
            self.control_thread.start()
            
            # Update UI state
            self.set_ui_state_starting()
            
        except Exception as e:
            self.add_log_message(f"Failed to start routing: {str(e)}")
            
    def stop_routing(self):
        """Stop the serial routing process."""
        if not self.router_core:
            return
            
        self.add_log_message("Stopping serial routing...")
        
        try:
            # Stop router in background thread
            self.control_thread = RouterControlThread()
            self.control_thread.operation_complete.connect(self.on_operation_complete)
            self.control_thread.set_operation('stop', self.router_core)
            self.control_thread.start()
            
            # Update UI state
            self.set_ui_state_stopping()
            
        except Exception as e:
            self.add_log_message(f"Error stopping routing: {str(e)}")
            
    def on_operation_complete(self, success: bool, message: str):
        """Handle completion of router operations."""
        self.add_log_message(message)
        
        if success:
            if "started" in message.lower():
                self.set_ui_state_running()
            elif "stopped" in message.lower():
                self.set_ui_state_stopped()
                # Remove logging handler
                if self.router_core and self.log_handler:
                    self.router_core.logger.removeHandler(self.log_handler)
                self.router_core = None
        else:
            # Operation failed, show error state then transition to stopped
            self.enhanced_status.set_state(EnhancedStatusWidget.STATE_ERROR)
            # After a brief delay, transition to stopped state
            QTimer.singleShot(2000, self.set_ui_state_stopped)
            if self.router_core and self.log_handler:
                self.router_core.logger.removeHandler(self.log_handler)
            self.router_core = None
            
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
        
        # Reset connection diagram to inactive state
        self.connection_diagram.set_connection_states({
            "COM131": False,
            "COM141": False
        })
        
    def update_connection_diagram_state(self):
        """Update connection diagram based on current router status."""
        if not self.router_core:
            return
            
        try:
            status = self.router_core.get_status()
            port_connections = status.get("port_connections", {})
            
            # Update connection states based on actual port status
            connection_states = {}
            for port in ["COM131", "COM141"]:
                if port in port_connections:
                    connection_states[port] = port_connections[port].get("connected", False)
                else:
                    connection_states[port] = False
                    
            self.connection_diagram.set_connection_states(connection_states)
            
        except Exception as e:
            # Fallback to basic active state
            self.connection_diagram.set_connection_states({
                "COM131": True,
                "COM141": True
            })
        
    def update_status_display(self):
        """Update the real-time status display with advanced metrics."""
        if not self.router_core:
            # Reset displays when not running
            self.uptime_label.setText("0 hours")
            self.connections_label.setText("0/3")
            self.throughput_label.setText("0 bytes/sec")
            self.last_activity_label.setText("N/A")
            self.data_loss_label.setText("0")
            self.error_rate_label.setText("0.0/hour")
            self.queue_util_label.setText("0%")
            self.health_status_label.setText("Offline")
            self.health_status_label.setProperty("class", "health-display status-error")
            
            # Legacy displays
            self.thread_status_label.setText("0/3 Active")
            self.thread_status_label.setProperty("class", "thread-status status-error")
            self.bytes_in_out_label.setText("0 bytes")
            self.bytes_131_in_label.setText("0 bytes") 
            self.bytes_141_in_label.setText("0 bytes")
            self.error_count_label.setText("0")
            self.restart_count_label.setText("0")
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
            
            # Active connections
            connections_status = critical_metrics.get("active_connections", "0/3")
            self.connections_label.setText(connections_status)
            if connections_status.startswith("3/3"):
                self.connections_label.setProperty("class", "connection-display status-success")
            elif "0/3" in connections_status:
                self.connections_label.setProperty("class", "connection-display status-error")
            else:
                self.connections_label.setProperty("class", "connection-display status-warning")
            
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
            
            # Queue utilization
            queue_util = critical_metrics.get("avg_queue_utilization_percent", 0)
            self.queue_util_label.setText(f"{queue_util:.1f}%")
            if queue_util < 50:
                self.queue_util_label.setProperty("class", "queue-display status-success")
            elif queue_util < 80:
                self.queue_util_label.setProperty("class", "queue-display status-warning")
            else:
                self.queue_util_label.setProperty("class", "queue-display status-error")
            
            # Health status
            system_health = status.get("system_health", {})
            health_status = system_health.get("overall_health_status", "UNKNOWN")
            self.health_status_label.setText(health_status)
            
            if health_status == "EXCELLENT":
                self.health_status_label.setProperty("class", "health-display status-excellent")
            elif health_status == "GOOD":
                self.health_status_label.setProperty("class", "health-display status-success")
            elif health_status == "WARNING":
                self.health_status_label.setProperty("class", "health-display status-warning")
            elif health_status == "CRITICAL":
                self.health_status_label.setProperty("class", "health-display status-error")
            else:
                self.health_status_label.setProperty("class", "health-display status-unknown")
            
            # Legacy Thread health display
            active_threads = status.get("active_threads", 0)
            self.thread_status_label.setText(f"{active_threads}/3 Active")
            if active_threads == 3:
                self.thread_status_label.setProperty("class", "thread-status status-success")
            elif active_threads > 0:
                self.thread_status_label.setProperty("class", "thread-status status-warning")
            else:
                self.thread_status_label.setProperty("class", "thread-status status-error")
                
            # Bytes transferred - Updated for new PortManager architecture
            bytes_data = status.get("bytes_transferred", {})
            
            # Get the actual incoming port name from status
            incoming_port = status.get("incoming_port", "COM54")
            
            # Format byte counts with dynamic port names
            directions_and_labels = [
                (f"{incoming_port}->131&141", self.bytes_in_out_label),
                ("COM131->Incoming", self.bytes_131_in_label), 
                ("COM141->Incoming", self.bytes_141_in_label)
            ]
            
            for direction, label in directions_and_labels:
                count = bytes_data.get(direction, 0)
                if count > 1024:
                    label.setText(f"{count:,} bytes ({count/1024:.1f} KB)")
                else:
                    label.setText(f"{count} bytes")
            
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
                    for port_name in [incoming_port, "COM131", "COM141"]:
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
            else:
                self.error_count_label.setProperty("class", "error-count status-success")
                
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
            # Log status update errors for debugging (but don't spam GUI)
            import time
            if not hasattr(self, '_last_status_error_time') or (time.time() - self._last_status_error_time) > 30:
                self.add_log_message(f"Status update error: {str(e)}")
                self._last_status_error_time = time.time()
            
    def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration from UI controls."""
        return {
            "incoming_port": self.incoming_port_combo.currentText(),  # Use actual selected port
            "incoming_baud": self.incoming_baud_spin.value(),
            "outgoing_baud": self.outgoing_baud_spin.value(),
            "timeout": 0.1,
            "retry_delay_max": 30,
            "log_level": "INFO"
        }
        
            
    def clear_activity_log(self):
        """Clear the activity log."""
        self.activity_log.clear()
        self.add_log_message("Activity log cleared")
        
    def closeEvent(self, event):
        """Handle application close event."""
        if self.is_routing_active():
            self.add_log_message("Shutting down router...")
            if self.router_core:
                self.router_core.stop()
                
        # Stop status timer
        self.status_timer.stop()
        
        # Clean up threads
        if self.control_thread and self.control_thread.isRunning():
            self.control_thread.wait(3000)  # Wait up to 3 seconds
            
        event.accept()
    
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
    window.add_log_message("SerialRouter GUI v2.0 initialized")
    window.add_log_message("Ready to configure and start serial routing")
    
    # Start application event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())