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
import time
from datetime import datetime
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QTextEdit, QFrame, QGroupBox, 
    QGridLayout, QSpinBox, QProgressBar, QSplitter
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QPalette

import serial.tools.list_ports
from src.core.router_engine import SerialRouterCore


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
                self.router_core.start()
                self.operation_complete.emit(True, "Router started successfully")
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
        self.load_configuration()
        self.refresh_available_ports()
        
        # Connect log signal to handler
        self.log_message_signal.connect(self.add_log_message)
        
        # Start status monitoring
        self.status_timer.start(1000)  # 1 second updates
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("SerialRouter v2.0 - Production Control")
        self.setFixedSize(650, 750)
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)
        
        # Top section - Configuration and Control
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # Configuration Group
        self.create_configuration_group(top_layout)
        
        # Process Control Group  
        self.create_control_group(top_layout)
        
        # Status Monitoring Group
        self.create_monitoring_group(top_layout)
        
        splitter.addWidget(top_widget)
        
        # Bottom section - Activity Log
        self.create_activity_log_group(splitter)
        
        # Set splitter proportions (70% top, 30% bottom)
        splitter.setSizes([525, 225])
        
    def create_configuration_group(self, parent_layout):
        """Create the port configuration group."""
        config_group = QGroupBox("Port Configuration")
        config_layout = QGridLayout(config_group)
        
        # Incoming Port Selection
        config_layout.addWidget(QLabel("Incoming Port:"), 0, 0)
        self.incoming_port_combo = QComboBox()
        self.incoming_port_combo.setMinimumWidth(120)
        config_layout.addWidget(self.incoming_port_combo, 0, 1)
        
        self.refresh_ports_btn = QPushButton("Refresh")
        self.refresh_ports_btn.clicked.connect(self.refresh_available_ports)
        config_layout.addWidget(self.refresh_ports_btn, 0, 2)
        
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
        outgoing_label.setStyleSheet("color: #555; font-style: italic;")
        config_layout.addWidget(outgoing_label, 2, 1)
        
        # Outgoing Port Baud Rate
        config_layout.addWidget(QLabel("Outgoing Baud:"), 3, 0)
        self.outgoing_baud_spin = QSpinBox()
        self.outgoing_baud_spin.setRange(1200, 921600) 
        self.outgoing_baud_spin.setValue(115200)
        self.outgoing_baud_spin.setSingleStep(1200)
        config_layout.addWidget(self.outgoing_baud_spin, 3, 1)
        
        parent_layout.addWidget(config_group)
        
    def create_control_group(self, parent_layout):
        """Create the process control group."""
        control_group = QGroupBox("Process Control")
        control_layout = QHBoxLayout(control_group)
        
        # Start Button
        self.start_btn = QPushButton("Start Routing")
        self.start_btn.clicked.connect(self.start_routing)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        control_layout.addWidget(self.start_btn)
        
        # Stop Button
        self.stop_btn = QPushButton("Stop Routing")
        self.stop_btn.clicked.connect(self.stop_routing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        control_layout.addWidget(self.stop_btn)
        
        # Status Indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: red; font-size: 24px; font-weight: bold;")
        control_layout.addWidget(self.status_indicator)
        
        self.status_text = QLabel("Disconnected")
        self.status_text.setStyleSheet("font-weight: bold; color: red;")
        control_layout.addWidget(self.status_text)
        
        control_layout.addStretch()
        
        # Configuration Actions
        self.save_config_btn = QPushButton("Save Config")
        self.save_config_btn.clicked.connect(self.save_configuration)
        control_layout.addWidget(self.save_config_btn)
        
        self.load_config_btn = QPushButton("Load Config") 
        self.load_config_btn.clicked.connect(self.load_configuration)
        control_layout.addWidget(self.load_config_btn)
        
        parent_layout.addWidget(control_group)
        
    def create_monitoring_group(self, parent_layout):
        """Create the real-time monitoring group."""
        monitor_group = QGroupBox("Live Monitoring")
        monitor_layout = QGridLayout(monitor_group)
        
        # Thread Health
        monitor_layout.addWidget(QLabel("Thread Health:"), 0, 0)
        self.thread_status_label = QLabel("0/3 Active")
        self.thread_status_label.setStyleSheet("font-weight: bold;")
        monitor_layout.addWidget(self.thread_status_label, 0, 1)
        
        # Bytes Transferred
        monitor_layout.addWidget(QLabel("Data Transfer:"), 1, 0)
        
        # Incoming -> Outgoing
        monitor_layout.addWidget(QLabel("IN → OUT:"), 2, 0)
        self.bytes_in_out_label = QLabel("0 bytes")
        monitor_layout.addWidget(self.bytes_in_out_label, 2, 1)
        
        # COM131 -> Incoming
        monitor_layout.addWidget(QLabel("131 → IN:"), 3, 0)
        self.bytes_131_in_label = QLabel("0 bytes")
        monitor_layout.addWidget(self.bytes_131_in_label, 3, 1)
        
        # COM141 -> Incoming  
        monitor_layout.addWidget(QLabel("141 → IN:"), 4, 0)
        self.bytes_141_in_label = QLabel("0 bytes")
        monitor_layout.addWidget(self.bytes_141_in_label, 4, 1)
        
        # Error Counts
        monitor_layout.addWidget(QLabel("Total Errors:"), 5, 0)
        self.error_count_label = QLabel("0")
        self.error_count_label.setStyleSheet("font-weight: bold;")
        monitor_layout.addWidget(self.error_count_label, 5, 1)
        
        # Thread Restarts
        monitor_layout.addWidget(QLabel("Thread Restarts:"), 6, 0)
        self.restart_count_label = QLabel("0")
        monitor_layout.addWidget(self.restart_count_label, 6, 1)
        
        parent_layout.addWidget(monitor_group)
        
    def create_activity_log_group(self, parent_widget):
        """Create the activity log group."""
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)
        
        # Log controls
        log_controls = QHBoxLayout()
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_activity_log)
        log_controls.addWidget(self.clear_log_btn)
        log_controls.addStretch()
        log_layout.addLayout(log_controls)
        
        # Log display
        self.activity_log = QTextEdit()
        self.activity_log.setFont(QFont("Courier", 9))
        self.activity_log.setReadOnly(True)
        log_layout.addWidget(self.activity_log)
        
        parent_widget.addWidget(log_group)
        
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
                self.start_btn.setEnabled(not self.is_routing_active())
            else:
                self.incoming_port_combo.addItem("COM54")
                self.start_btn.setEnabled(not self.is_routing_active())
                
            self.add_log_message(f"Found {len(port_names)} COM ports: {', '.join(port_names) if port_names else 'None'} (COM54 hardcoded for testing)")
            
        except Exception as e:
            self.add_log_message(f"Error refreshing ports: {str(e)}")
            self.incoming_port_combo.addItem("COM54")
            self.start_btn.setEnabled(not self.is_routing_active())
            
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
            
            # Initialize router core with config
            self.router_core = SerialRouterCore("config/serial_router_config.json")
            
            # Update router config
            self.router_core.incoming_port = config["incoming_port"]
            self.router_core.incoming_baud = config["incoming_baud"] 
            self.router_core.outgoing_baud = config["outgoing_baud"]
            
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
            # Operation failed, restore UI to stopped state
            self.set_ui_state_stopped()
            if self.router_core and self.log_handler:
                self.router_core.logger.removeHandler(self.log_handler)
            self.router_core = None
            
    def set_ui_state_starting(self):
        """Set UI to starting state."""
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Starting...")
        self.stop_btn.setEnabled(False)
        self.status_indicator.setStyleSheet("color: orange; font-size: 24px; font-weight: bold;")
        self.status_text.setText("Starting...")
        self.status_text.setStyleSheet("font-weight: bold; color: orange;")
        
    def set_ui_state_running(self):
        """Set UI to running state."""
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Start Routing")
        self.stop_btn.setEnabled(True)
        self.status_indicator.setStyleSheet("color: green; font-size: 24px; font-weight: bold;")
        self.status_text.setText("Routing Active")
        self.status_text.setStyleSheet("font-weight: bold; color: green;")
        
    def set_ui_state_stopping(self):
        """Set UI to stopping state."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("Stopping...")
        self.status_indicator.setStyleSheet("color: orange; font-size: 24px; font-weight: bold;")
        self.status_text.setText("Stopping...")
        self.status_text.setStyleSheet("font-weight: bold; color: orange;")
        
    def set_ui_state_stopped(self):
        """Set UI to stopped state."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Start Routing")
        self.stop_btn.setEnabled(False) 
        self.stop_btn.setText("Stop Routing")
        self.status_indicator.setStyleSheet("color: red; font-size: 24px; font-weight: bold;")
        self.status_text.setText("Disconnected")
        self.status_text.setStyleSheet("font-weight: bold; color: red;")
        
    def update_status_display(self):
        """Update the real-time status display."""
        if not self.router_core:
            # Reset displays when not running
            self.thread_status_label.setText("0/3 Active")
            self.thread_status_label.setStyleSheet("font-weight: bold; color: red;")
            self.bytes_in_out_label.setText("0 bytes")
            self.bytes_131_in_label.setText("0 bytes") 
            self.bytes_141_in_label.setText("0 bytes")
            self.error_count_label.setText("0")
            self.restart_count_label.setText("0")
            return
            
        try:
            status = self.router_core.get_status()
            
            # Thread health
            active_threads = status.get("active_threads", 0)
            self.thread_status_label.setText(f"{active_threads}/3 Active")
            if active_threads == 3:
                self.thread_status_label.setStyleSheet("font-weight: bold; color: green;")
            elif active_threads > 0:
                self.thread_status_label.setStyleSheet("font-weight: bold; color: orange;")
            else:
                self.thread_status_label.setStyleSheet("font-weight: bold; color: red;")
                
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
                self.error_count_label.setStyleSheet("font-weight: bold; color: red;")
            else:
                self.error_count_label.setStyleSheet("font-weight: bold; color: green;")
                
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
        
    def save_configuration(self):
        """Save current configuration to JSON file."""
        try:
            config = self.get_current_config()
            with open("config/serial_router_config.json", "w") as f:
                json.dump(config, f, indent=2)
            self.add_log_message("Configuration saved to serial_router_config.json")
        except Exception as e:
            self.add_log_message(f"Failed to save configuration: {str(e)}")
            
    def load_configuration(self):
        """Load configuration from JSON file."""
        try:
            with open("config/serial_router_config.json", "r") as f:
                config = json.load(f)
                
            # Update UI controls
            if "incoming_port" in config:
                port_name = config["incoming_port"]
                index = self.incoming_port_combo.findText(port_name)
                if index >= 0:
                    self.incoming_port_combo.setCurrentIndex(index)
                    
            if "incoming_baud" in config:
                self.incoming_baud_spin.setValue(config["incoming_baud"])
                
            if "outgoing_baud" in config:
                self.outgoing_baud_spin.setValue(config["outgoing_baud"])
                
            self.add_log_message("Configuration loaded from serial_router_config.json")
            
        except FileNotFoundError:
            self.add_log_message("Configuration file not found, using defaults")
        except Exception as e:
            self.add_log_message(f"Failed to load configuration: {str(e)}")
            
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


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("SerialRouter")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("SerialRouter")
    
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