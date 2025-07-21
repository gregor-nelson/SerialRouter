import sys
import serial
import threading
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QTextEdit, QFrame, QGroupBox, QGridLayout)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import serial.tools.list_ports

class SerialRouterThread(QThread):
    status_update = pyqtSignal(str)
    bytes_update = pyqtSignal(str, int)
    
    def __init__(self, incoming_port, baud_rate):
        super().__init__()
        self.incoming_port_name = incoming_port
        self.baud_rate = baud_rate
        self.running = False
        self.ports = {}
        self.bytes_counters = {
            f"{incoming_port}->131&141": 0,
            "131->incoming": 0,
            "141->incoming": 0
        }
        
    def run(self):
        self.running = True
        try:
            self.status_update.emit("Connecting to ports...")
            
            # Open ports
            self.ports['incoming'] = serial.Serial(self.incoming_port_name, self.baud_rate, timeout=0.1)
            self.ports['131'] = serial.Serial('COM131', 115200, timeout=0.1)
            self.ports['141'] = serial.Serial('COM141', 115200, timeout=0.1)
            
            self.status_update.emit("All ports connected. Routing active.")
            
            # Start routing threads
            thread1 = threading.Thread(target=self.route_data, 
                                     args=(self.ports['incoming'], 
                                          [self.ports['131'], self.ports['141']], 
                                          f"{self.incoming_port_name}->131&141"))
            
            thread2 = threading.Thread(target=self.route_data, 
                                     args=(self.ports['131'], 
                                          [self.ports['incoming']], 
                                          "131->incoming"))
            
            thread3 = threading.Thread(target=self.route_data, 
                                     args=(self.ports['141'], 
                                          [self.ports['incoming']], 
                                          "141->incoming"))
            
            thread1.daemon = True
            thread2.daemon = True
            thread3.daemon = True
            
            thread1.start()
            thread2.start()
            thread3.start()
            
            # Keep thread alive
            while self.running:
                time.sleep(0.1)
                
        except Exception as e:
            self.status_update.emit(f"Error: {str(e)}")
        finally:
            self.cleanup()
    
    def route_data(self, source_port, dest_ports, direction):
        while self.running:
            try:
                if source_port.in_waiting > 0:
                    data = source_port.read(source_port.in_waiting)
                    if data:
                        # Send to all destination ports
                        for dest_port in dest_ports:
                            dest_port.write(data)
                        
                        self.bytes_counters[direction] += len(data)
                        self.bytes_update.emit(direction, len(data))
                        
            except Exception as e:
                if self.running:
                    self.status_update.emit(f"{direction} error: {str(e)}")
                break
            
            time.sleep(0.001)
    
    def stop(self):
        self.running = False
        self.cleanup()
    
    def cleanup(self):
        for port in self.ports.values():
            try:
                port.close()
            except:
                pass
        self.ports.clear()

class SerialRouterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.router_thread = None
        self.bytes_counters = {
            "incoming->131&141": 0,
            "131->incoming": 0,
            "141->incoming": 0
        }
        self.init_ui()
        self.refresh_ports()
        
    def init_ui(self):
        self.setWindowTitle("Serial Router")
        self.setFixedSize(500, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Configuration Section
        config_group = QGroupBox("Configuration")
        config_layout = QGridLayout(config_group)
        
        # Incoming Port
        config_layout.addWidget(QLabel("Incoming Port:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        config_layout.addWidget(self.port_combo, 0, 1)
        
        # Baud Rate
        config_layout.addWidget(QLabel("Baud Rate:"), 1, 0)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud_combo.setCurrentText('115200')
        config_layout.addWidget(self.baud_combo, 1, 1)
        
        # Fixed Destinations
        config_layout.addWidget(QLabel("Destinations:"), 2, 0)
        config_layout.addWidget(QLabel("COM131 & COM141 (115200)"), 2, 1)
        
        # Control Buttons
        button_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Ports")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        button_layout.addWidget(self.refresh_btn)
        
        self.start_btn = QPushButton("Start Routing")
        self.start_btn.clicked.connect(self.start_routing)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Routing")
        self.stop_btn.clicked.connect(self.stop_routing)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        config_layout.addLayout(button_layout, 3, 0, 1, 2)
        layout.addWidget(config_group)
        
        # Status Section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        # Connection Status
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        # Byte Counters
        counters_layout = QGridLayout()
        counters_layout.addWidget(QLabel("Incoming → 131&141:"), 0, 0)
        self.counter1_label = QLabel("0 bytes")
        counters_layout.addWidget(self.counter1_label, 0, 1)
        
        counters_layout.addWidget(QLabel("131 → Incoming:"), 1, 0)
        self.counter2_label = QLabel("0 bytes")
        counters_layout.addWidget(self.counter2_label, 1, 1)
        
        counters_layout.addWidget(QLabel("141 → Incoming:"), 2, 0)
        self.counter3_label = QLabel("0 bytes")
        counters_layout.addWidget(self.counter3_label, 2, 1)
        
        status_layout.addLayout(counters_layout)
        
        # Activity Log
        log_layout = QVBoxLayout()
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Activity Log:"))
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_log)
        log_header.addWidget(self.clear_btn)
        
        log_layout.addLayout(log_header)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setFont(QFont("Courier", 8))
        log_layout.addWidget(self.log_text)
        
        status_layout.addLayout(log_layout)
        layout.addWidget(status_group)
        
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        
        if self.port_combo.count() == 0:
            self.port_combo.addItem("No ports available")
            self.start_btn.setEnabled(False)
        else:
            self.start_btn.setEnabled(True)
    
    def start_routing(self):
        if self.port_combo.currentText() == "No ports available":
            return
            
        incoming_port = self.port_combo.currentText()
        baud_rate = int(self.baud_combo.currentText())
        
        self.router_thread = SerialRouterThread(incoming_port, baud_rate)
        self.router_thread.status_update.connect(self.update_status)
        self.router_thread.bytes_update.connect(self.update_bytes)
        self.router_thread.start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.port_combo.setEnabled(False)
        self.baud_combo.setEnabled(False)
        
    def stop_routing(self):
        if self.router_thread:
            self.router_thread.stop()
            self.router_thread.wait()
            self.router_thread = None
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
    def update_status(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        if "connected" in message.lower() or "active" in message.lower():
            self.status_label.setText("Connected - Routing Active")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        elif "error" in message.lower():
            self.status_label.setText("Error")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
    def update_bytes(self, direction, bytes_count):
        # Update counters
        if "->131&141" in direction:
            self.bytes_counters["incoming->131&141"] += bytes_count
            self.counter1_label.setText(f"{self.bytes_counters['incoming->131&141']} bytes")
        elif "131->incoming" in direction:
            self.bytes_counters["131->incoming"] += bytes_count
            self.counter2_label.setText(f"{self.bytes_counters['131->incoming']} bytes")
        elif "141->incoming" in direction:
            self.bytes_counters["141->incoming"] += bytes_count
            self.counter3_label.setText(f"{self.bytes_counters['141->incoming']} bytes")
        
        # Log activity
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {direction}: {bytes_count} bytes")
        
        # Auto-scroll to bottom
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        
    def clear_log(self):
        self.log_text.clear()
        self.bytes_counters = {
            "incoming->131&141": 0,
            "131->incoming": 0,
            "141->incoming": 0
        }
        self.counter1_label.setText("0 bytes")
        self.counter2_label.setText("0 bytes")
        self.counter3_label.setText("0 bytes")
        
    def closeEvent(self, event):
        if self.router_thread:
            self.router_thread.stop()
            self.router_thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialRouterGUI()
    window.show()
    sys.exit(app.exec())