"""
SerialRouter - Production Hardened Version
Robust serial port routing for offshore environments with minimal complexity.

Architecture:
- One incoming port (configurable) → Two fixed outgoing ports (COM131, COM141)
- Two return paths: COM131 → incoming, COM141 → incoming
- Auto-reconnection with exponential backoff
- Thread health monitoring and auto-restart
- Basic file logging with rotation
- Memory leak prevention for long-term operation
"""

import serial
import threading
import time
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import signal
import queue
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
import traceback
from collections import deque


class PortManager:
    """Centralized, thread-safe serial port connection manager.
    
    Ensures only one thread can access each physical port, preventing the
    'Access is denied' errors caused by multiple threads trying to open
    the same port simultaneously.
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
        # Core connection management
        self.connections: Dict[str, Optional[serial.Serial]] = {}
        self.connection_locks: Dict[str, threading.RLock] = {}
        self.port_owners: Dict[str, str] = {}  # port -> thread_name mapping
        self.active_ports: Set[str] = set()
        
        # Data distribution system
        self.data_queues: Dict[str, queue.Queue] = {}
        self.queue_locks: Dict[str, threading.Lock] = {}
        
        # Health and monitoring
        self.port_stats: Dict[str, Dict[str, int]] = {}
        self.last_activity: Dict[str, datetime] = {}
        self.error_counts: Dict[str, int] = {}
        
        # Advanced monitoring - throughput calculation
        self.throughput_history: Dict[str, deque] = {}  # Port -> deque of (timestamp, bytes) tuples
        self.throughput_window_seconds = 60  # Calculate rates over 60 seconds
        
        # Advanced monitoring - connection tracking
        self.connection_attempts: Dict[str, int] = {}
        self.connection_successes: Dict[str, int] = {}
        self.connection_start_times: Dict[str, datetime] = {}
        self.total_downtime: Dict[str, float] = {}  # Seconds
        self.last_disconnect_time: Dict[str, Optional[datetime]] = {}
        
        # Advanced monitoring - error tracking
        self.error_history: Dict[str, deque] = {}  # Port -> deque of error timestamps
        self.error_window_seconds = 3600  # Track errors over 1 hour
        
        # Advanced monitoring - queue latency
        self.queue_latency_samples: Dict[str, deque] = {}  # Port -> deque of latency samples
        self.queue_latency_window = 100  # Keep last 100 samples
        
        # System startup time for uptime calculation
        self.system_start_time = datetime.now()
        
        # Configuration
        self.connection_timeout = 0.1
        self.max_queue_size = 1000
        
        # Master lock for port manager operations
        self._manager_lock = threading.RLock()
        
        self.logger.info("PortManager initialized with advanced monitoring")
    
    def acquire_port(self, port_name: str, baud_rate: int, owner_thread: str, timeout: float = 30.0) -> bool:
        """Thread-safe port acquisition with ownership tracking.
        
        Args:
            port_name: Serial port name (e.g., 'COM54')
            baud_rate: Baud rate for the connection
            owner_thread: Name of the thread requesting ownership
            timeout: Maximum time to wait for port availability
            
        Returns:
            True if port was successfully acquired, False otherwise
        """
        with self._manager_lock:
            # Check if port is already owned by this thread
            if port_name in self.port_owners:
                if self.port_owners[port_name] == owner_thread:
                    self.logger.debug(f"Port {port_name} already owned by {owner_thread}")
                    return True
                else:
                    self.logger.warning(f"Port {port_name} owned by {self.port_owners[port_name]}, denied to {owner_thread}")
                    return False
            
            # Initialize port structures if first time
            if port_name not in self.connection_locks:
                self.connection_locks[port_name] = threading.RLock()
                self.data_queues[port_name] = queue.Queue(maxsize=self.max_queue_size)
                self.queue_locks[port_name] = threading.Lock()
                self.port_stats[port_name] = {
                    'bytes_read': 0, 'bytes_written': 0, 'errors': 0, 'reconnects': 0
                }
                # Initialize advanced monitoring structures
                self.throughput_history[port_name] = deque()
                self.error_history[port_name] = deque()
                self.queue_latency_samples[port_name] = deque()
                self.connection_attempts[port_name] = 0
                self.connection_successes[port_name] = 0
                self.total_downtime[port_name] = 0.0
                self.last_disconnect_time[port_name] = None
            
            # Attempt to open the port
            try:
                self.connection_attempts[port_name] += 1
                self.logger.info(f"Opening port {port_name} for owner {owner_thread}")
                port = serial.Serial(port_name, baud_rate, timeout=self.connection_timeout)
                
                # Success - record ownership and connection
                self.connections[port_name] = port
                self.port_owners[port_name] = owner_thread
                self.active_ports.add(port_name)
                current_time = datetime.now()
                self.last_activity[port_name] = current_time
                self.connection_start_times[port_name] = current_time
                self.connection_successes[port_name] += 1
                
                # Calculate downtime if we were previously disconnected
                if self.last_disconnect_time[port_name]:
                    downtime = (current_time - self.last_disconnect_time[port_name]).total_seconds()
                    self.total_downtime[port_name] += downtime
                    self.last_disconnect_time[port_name] = None
                
                self.logger.info(f"Port {port_name} successfully acquired by {owner_thread}")
                return True
                
            except Exception as e:
                self.error_counts[port_name] = self.error_counts.get(port_name, 0) + 1
                self._record_error(port_name)
                self.logger.error(f"Failed to open port {port_name} for {owner_thread}: {e}")
                return False
    
    def release_port(self, port_name: str, owner_thread: str) -> bool:
        """Release port ownership and close connection.
        
        Args:
            port_name: Serial port name to release
            owner_thread: Name of the thread releasing the port
            
        Returns:
            True if port was successfully released, False otherwise
        """
        with self._manager_lock:
            # Verify ownership
            if port_name not in self.port_owners:
                self.logger.warning(f"Attempted to release unowned port {port_name} by {owner_thread}")
                return False
            
            if self.port_owners[port_name] != owner_thread:
                self.logger.warning(f"Port {port_name} owned by {self.port_owners[port_name]}, cannot release by {owner_thread}")
                return False
            
            # Close the connection safely
            try:
                if port_name in self.connections and self.connections[port_name]:
                    self.connections[port_name].close()
                    self.logger.info(f"Port {port_name} connection closed by {owner_thread}")
            except Exception as e:
                self.logger.error(f"Error closing port {port_name}: {e}")
            
            # Clear ownership and tracking
            del self.port_owners[port_name]
            self.connections[port_name] = None
            self.active_ports.discard(port_name)
            
            # Record disconnect time for downtime calculation
            self.last_disconnect_time[port_name] = datetime.now()
            
            self.logger.info(f"Port {port_name} released by {owner_thread}")
            return True
    
    def write_data(self, port_name: str, data: bytes, owner_thread: str) -> bool:
        """Thread-safe write operation with ownership verification.
        
        Args:
            port_name: Target port name
            data: Data bytes to write
            owner_thread: Name of the thread attempting write
            
        Returns:
            True if data was successfully written, False otherwise
        """
        # Verify ownership
        if port_name not in self.port_owners or self.port_owners[port_name] != owner_thread:
            self.logger.error(f"Write denied: port {port_name} not owned by {owner_thread}")
            return False
        
        if port_name not in self.connections or not self.connections[port_name]:
            self.logger.error(f"Write failed: port {port_name} not connected")
            return False
        
        # Perform thread-safe write
        with self.connection_locks[port_name]:
            try:
                self.connections[port_name].write(data)
                current_time = datetime.now()
                self.port_stats[port_name]['bytes_written'] += len(data)
                self.last_activity[port_name] = current_time
                
                # Update throughput tracking
                self._update_throughput(port_name, len(data), current_time, 'write')
                
                return True
                
            except Exception as e:
                self.port_stats[port_name]['errors'] += 1
                self._record_error(port_name)
                self.logger.error(f"Write error on port {port_name}: {e}")
                return False
    
    def read_available(self, port_name: str, owner_thread: str) -> Optional[bytes]:
        """Thread-safe read operation with ownership verification.
        
        Args:
            port_name: Source port name
            owner_thread: Name of the thread attempting read
            
        Returns:
            Data bytes if available, None if no data or error
        """
        # Verify ownership
        if port_name not in self.port_owners or self.port_owners[port_name] != owner_thread:
            return None
        
        if port_name not in self.connections or not self.connections[port_name]:
            return None
        
        # Perform thread-safe read
        with self.connection_locks[port_name]:
            try:
                if self.connections[port_name].in_waiting > 0:
                    data = self.connections[port_name].read(self.connections[port_name].in_waiting)
                    if data:
                        current_time = datetime.now()
                        self.port_stats[port_name]['bytes_read'] += len(data)
                        self.last_activity[port_name] = current_time
                        
                        # Update throughput tracking
                        self._update_throughput(port_name, len(data), current_time, 'read')
                        
                        return data
                return None
                
            except Exception as e:
                self.port_stats[port_name]['errors'] += 1
                self._record_error(port_name)
                self.logger.error(f"Read error on port {port_name}: {e}")
                return None
    
    def queue_data_for_port(self, target_port: str, data: bytes, source_thread: str) -> bool:
        """Queue data for delivery to a specific port.
        
        Args:
            target_port: Port that should receive this data
            data: Data bytes to queue
            source_thread: Thread that generated this data
            
        Returns:
            True if data was successfully queued, False if queue is full
        """
        if target_port not in self.data_queues:
            self.logger.error(f"No queue exists for target port {target_port}")
            return False
        
        try:
            with self.queue_locks[target_port]:
                # Record queue entry time for latency tracking
                queue_entry = (data, datetime.now())
                self.data_queues[target_port].put_nowait(queue_entry)
                return True
                
        except queue.Full:
            self.logger.warning(f"Queue full for port {target_port}, dropping data from {source_thread}")
            return False
    
    def get_queued_data(self, port_name: str, timeout: float = 0.001) -> Optional[bytes]:
        """Get queued data for a specific port.
        
        Args:
            port_name: Port to get data for
            timeout: Maximum time to wait for data
            
        Returns:
            Data bytes if available, None if no data or timeout
        """
        if port_name not in self.data_queues:
            return None
        
        try:
            with self.queue_locks[port_name]:
                queue_entry = self.data_queues[port_name].get(timeout=timeout)
                if queue_entry:
                    data, queue_time = queue_entry
                    # Calculate and record queue latency
                    latency_ms = (datetime.now() - queue_time).total_seconds() * 1000
                    self._record_queue_latency(port_name, latency_ms)
                    return data
                return None
        except queue.Empty:
            return None
    
    def get_port_status(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive status of all managed ports.
        
        Returns:
            Dictionary with detailed status information for each port
        """
        with self._manager_lock:
            status = {}
            
            for port_name in self.connections:
                is_connected = (port_name in self.active_ports and 
                              self.connections[port_name] is not None)
                
                # Get advanced metrics
                throughput_metrics = self.get_throughput_metrics(port_name)
                connection_metrics = self.get_connection_metrics(port_name)
                error_metrics = self.get_error_rate_metrics(port_name)
                queue_metrics = self.get_queue_metrics(port_name)
                
                status[port_name] = {
                    # Basic status
                    'connected': is_connected,
                    'owner': self.port_owners.get(port_name, None),
                    'stats': self.port_stats.get(port_name, {}),
                    'last_activity': self.last_activity.get(port_name),
                    'queue_size': self.data_queues[port_name].qsize() if port_name in self.data_queues else 0,
                    'error_count': self.error_counts.get(port_name, 0),
                    
                    # Advanced metrics
                    'throughput': throughput_metrics,
                    'connection_reliability': connection_metrics,
                    'error_metrics': error_metrics,
                    'queue_performance': queue_metrics
                }
            
            return status
    
    def cleanup_all_ports(self) -> None:
        """Emergency cleanup of all ports and resources."""
        with self._manager_lock:
            self.logger.info("PortManager cleanup initiated")
            
            # Close all connections
            for port_name, connection in self.connections.items():
                if connection:
                    try:
                        connection.close()
                        self.logger.info(f"Closed connection to {port_name}")
                    except Exception as e:
                        self.logger.error(f"Error closing {port_name}: {e}")
            
            # Clear all tracking
            self.connections.clear()
            self.port_owners.clear()
            self.active_ports.clear()
            
            # Clear queues
            for queue_obj in self.data_queues.values():
                try:
                    while not queue_obj.empty():
                        queue_obj.get_nowait()
                except:
                    pass
            
            self.logger.info("PortManager cleanup completed")
    
    def _update_throughput(self, port_name: str, bytes_count: int, timestamp: datetime, operation: str):
        """Update throughput tracking for a port."""
        if port_name not in self.throughput_history:
            self.throughput_history[port_name] = deque()
        
        # Add new data point
        self.throughput_history[port_name].append((timestamp, bytes_count, operation))
        
        # Remove old data points outside the window
        cutoff_time = timestamp - timedelta(seconds=self.throughput_window_seconds)
        while (self.throughput_history[port_name] and 
               self.throughput_history[port_name][0][0] < cutoff_time):
            self.throughput_history[port_name].popleft()
    
    def _record_error(self, port_name: str):
        """Record an error timestamp for error rate calculation."""
        if port_name not in self.error_history:
            self.error_history[port_name] = deque()
        
        current_time = datetime.now()
        self.error_history[port_name].append(current_time)
        
        # Remove old error records outside the window
        cutoff_time = current_time - timedelta(seconds=self.error_window_seconds)
        while (self.error_history[port_name] and 
               self.error_history[port_name][0] < cutoff_time):
            self.error_history[port_name].popleft()
    
    def _record_queue_latency(self, port_name: str, latency_ms: float):
        """Record queue latency sample."""
        if port_name not in self.queue_latency_samples:
            self.queue_latency_samples[port_name] = deque()
        
        self.queue_latency_samples[port_name].append(latency_ms)
        
        # Keep only recent samples
        while len(self.queue_latency_samples[port_name]) > self.queue_latency_window:
            self.queue_latency_samples[port_name].popleft()
    
    def get_throughput_metrics(self, port_name: str) -> Dict[str, float]:
        """Calculate current throughput metrics for a port."""
        if port_name not in self.throughput_history:
            return {'bytes_per_second': 0.0, 'read_bps': 0.0, 'write_bps': 0.0}
        
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=self.throughput_window_seconds)
        
        total_bytes = 0
        read_bytes = 0
        write_bytes = 0
        
        for timestamp, bytes_count, operation in self.throughput_history[port_name]:
            if timestamp >= cutoff_time:
                total_bytes += bytes_count
                if operation == 'read':
                    read_bytes += bytes_count
                else:
                    write_bytes += bytes_count
        
        # Calculate bytes per second
        time_window = min(self.throughput_window_seconds, 
                         (current_time - self.throughput_history[port_name][0][0]).total_seconds()
                         if self.throughput_history[port_name] else 1)
        
        return {
            'bytes_per_second': total_bytes / max(time_window, 1),
            'read_bps': read_bytes / max(time_window, 1),
            'write_bps': write_bytes / max(time_window, 1)
        }
    
    def get_connection_metrics(self, port_name: str) -> Dict[str, Any]:
        """Calculate connection reliability metrics for a port."""
        if port_name not in self.connection_attempts:
            return {}
        
        current_time = datetime.now()
        
        # Calculate connection success rate
        attempts = self.connection_attempts[port_name]
        successes = self.connection_successes[port_name]
        success_rate = (successes / attempts * 100) if attempts > 0 else 0
        
        # Calculate uptime percentage
        total_time = (current_time - self.system_start_time).total_seconds()
        downtime = self.total_downtime[port_name]
        if self.last_disconnect_time[port_name]:  # Currently disconnected
            downtime += (current_time - self.last_disconnect_time[port_name]).total_seconds()
        
        uptime_percentage = ((total_time - downtime) / total_time * 100) if total_time > 0 else 0
        
        # Calculate MTBF (Mean Time Between Failures)
        failures = attempts - successes
        mtbf_hours = (total_time / 3600 / failures) if failures > 0 else float('inf')
        
        # Time since last activity
        last_activity = self.last_activity.get(port_name)
        seconds_since_activity = (current_time - last_activity).total_seconds() if last_activity else float('inf')
        
        return {
            'connection_success_rate': round(success_rate, 2),
            'uptime_percentage': round(uptime_percentage, 2),
            'mtbf_hours': round(mtbf_hours, 2) if mtbf_hours != float('inf') else None,
            'seconds_since_last_activity': round(seconds_since_activity, 1),
            'total_connection_attempts': attempts,
            'successful_connections': successes,
            'is_currently_connected': port_name in self.active_ports
        }
    
    def get_error_rate_metrics(self, port_name: str) -> Dict[str, float]:
        """Calculate error rate metrics for a port."""
        if port_name not in self.error_history:
            return {'errors_per_hour': 0.0, 'error_trend': 'stable'}
        
        current_time = datetime.now()
        
        # Count errors in the last hour
        recent_errors = len(self.error_history[port_name])
        errors_per_hour = recent_errors
        
        # Simple trend analysis - compare last 30 minutes to previous 30 minutes
        half_window = self.error_window_seconds // 2
        half_cutoff = current_time - timedelta(seconds=half_window)
        
        recent_half_errors = sum(1 for error_time in self.error_history[port_name] 
                                if error_time >= half_cutoff)
        older_half_errors = recent_errors - recent_half_errors
        
        if older_half_errors == 0 and recent_half_errors == 0:
            trend = 'stable'
        elif older_half_errors == 0:
            trend = 'increasing'
        elif recent_half_errors == 0:
            trend = 'decreasing'
        else:
            ratio = recent_half_errors / older_half_errors
            if ratio > 1.5:
                trend = 'increasing'
            elif ratio < 0.5:
                trend = 'decreasing'
            else:
                trend = 'stable'
        
        return {
            'errors_per_hour': errors_per_hour,
            'error_trend': trend
        }
    
    def get_queue_metrics(self, port_name: str) -> Dict[str, Any]:
        """Calculate queue performance metrics for a port."""
        if port_name not in self.data_queues:
            return {}
        
        current_queue_size = self.data_queues[port_name].qsize()
        queue_utilization = (current_queue_size / self.max_queue_size * 100)
        
        # Calculate latency statistics
        latency_stats = {}
        if port_name in self.queue_latency_samples and self.queue_latency_samples[port_name]:
            samples = list(self.queue_latency_samples[port_name])
            latency_stats = {
                'avg_latency_ms': round(sum(samples) / len(samples), 2),
                'max_latency_ms': round(max(samples), 2),
                'min_latency_ms': round(min(samples), 2)
            }
        else:
            latency_stats = {
                'avg_latency_ms': 0.0,
                'max_latency_ms': 0.0,
                'min_latency_ms': 0.0
            }
        
        return {
            'current_queue_size': current_queue_size,
            'queue_utilization_percent': round(queue_utilization, 1),
            'max_queue_size': self.max_queue_size,
            **latency_stats
        }


class SerialRouterCore:
    """Production-hardened serial router core with auto-recovery capabilities."""
    
    def __init__(self, incoming_port: str = "COM54", incoming_baud: int = 115200, outgoing_baud: int = 115200):
        # Hardcoded static configuration
        self.timeout: float = 0.1
        self.retry_delay_max: int = 30
        self.log_level: str = "INFO"
        
        # Dynamic configuration from GUI
        self.incoming_port: str = incoming_port
        self.incoming_baud: int = incoming_baud
        self.outgoing_baud: int = outgoing_baud
        
        # Fixed outgoing ports
        self.outgoing_ports = ["COM131", "COM141"]
        
        # Runtime state
        self.running = False
        self.shutdown_requested = False
        self.serial_connections: Dict[str, Optional[serial.Serial]] = {}
        self.routing_threads: List[threading.Thread] = []
        self.thread_heartbeats: Dict[str, datetime] = {}
        self.watchdog_thread: Optional[threading.Thread] = None
        
        # Statistics and monitoring
        self.bytes_transferred: Dict[str, int] = {}
        self.error_counts: Dict[str, int] = {}
        self.last_counter_reset = datetime.now()
        
        # Thread restart tracking
        self.thread_restart_counts: Dict[str, int] = {}
        self.thread_restart_window_start = datetime.now()
        
        # System-level monitoring
        self.router_start_time: Optional[datetime] = None
        self.data_loss_events = 0
        self.peak_throughput = 0.0
        
        # Setup logging
        self._setup_logging()
        
        # Initialize centralized port manager
        self.port_manager = PortManager(self.logger)
        
        self.logger.info(f"SerialRouter initialized - Port: {self.incoming_port}, Baud: {self.incoming_baud}/{self.outgoing_baud}")
    
    def _setup_logging(self):
        """Setup file logging with rotation."""
        self.logger = logging.getLogger('SerialRouter')
        self.logger.setLevel(getattr(logging, self.log_level))
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Console handler for current testing
        console_handler = logging.StreamHandler()
        console_format = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation
        try:
            file_handler = RotatingFileHandler(
                'serial_router.log',
                maxBytes=10*1024*1024,  # 10MB
                backupCount=1
            )
            file_format = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")
    
    def _connect_port(self, port_name: str, baud_rate: int, retry_count: int = 0) -> Optional[serial.Serial]:
        """Connect to serial port with exponential backoff retry."""
        max_retries = 100
        
        while retry_count < max_retries and not self.shutdown_requested:
            try:
                self.logger.info(f"Attempting to connect to {port_name} (attempt {retry_count + 1})")
                port = serial.Serial(port_name, baud_rate, timeout=self.timeout)
                self.logger.info(f"Successfully connected to {port_name}")
                return port
                
            except Exception as e:
                self.error_counts[port_name] = self.error_counts.get(port_name, 0) + 1
                retry_delay = min(2 ** retry_count, self.retry_delay_max)
                
                if retry_count < 5:  # Log first few attempts as INFO
                    self.logger.info(f"Failed to connect to {port_name}: {e}. Retrying in {retry_delay}s")
                elif retry_count % 10 == 0:  # Log every 10th attempt after that
                    self.logger.warn(f"Still unable to connect to {port_name} after {retry_count + 1} attempts: {e}")
                
                time.sleep(retry_delay)
                retry_count += 1
        
        if retry_count >= max_retries:
            self.logger.error(f"Failed to connect to {port_name} after {max_retries} attempts")
        
        return None
    
    def _incoming_port_handler(self):
        """Handle incoming port: read data and distribute to both outgoing ports.
        
        This thread owns the incoming port exclusively and reads all data from it.
        Data is then queued for both outgoing ports via the PortManager.
        """
        thread_name = threading.current_thread().name
        direction = f"{self.incoming_port}->131&141"
        
        self.logger.info(f"Starting incoming port handler: {direction}")
        
        consecutive_errors = 0
        while not self.shutdown_requested:
            try:
                # Update heartbeat
                self.thread_heartbeats[thread_name] = datetime.now()
                
                # Read data from owned incoming port
                data = self.port_manager.read_available(self.incoming_port, thread_name)
                if data:
                    # Queue data for both outgoing ports
                    success_131 = self.port_manager.queue_data_for_port("COM131", data, thread_name)
                    success_141 = self.port_manager.queue_data_for_port("COM141", data, thread_name)
                    
                    if success_131 and success_141:
                        # Update statistics
                        self.bytes_transferred[direction] = self.bytes_transferred.get(direction, 0) + len(data)
                        
                        # Reset counter if needed (prevent overflow)
                        if self.bytes_transferred[direction] > 1000000:  # 1M bytes
                            self.logger.info(f"{direction}: Resetting byte counter at {self.bytes_transferred[direction]} bytes")
                            self.bytes_transferred[direction] = 0
                        
                        self.logger.debug(f"{direction}: {len(data)} bytes distributed")
                        consecutive_errors = 0
                    else:
                        self.logger.warning(f"{direction}: Failed to queue data to one or both outgoing ports")
                
                # Check for queued data to write to incoming port (from outgoing ports)
                queued_data = self.port_manager.get_queued_data(self.incoming_port)
                if queued_data:
                    if self.port_manager.write_data(self.incoming_port, queued_data, thread_name):
                        self.logger.debug(f"Wrote {len(queued_data)} bytes to {self.incoming_port}")
                    else:
                        self.logger.warning(f"Failed to write queued data to {self.incoming_port}")
                
                time.sleep(0.001)  # 1ms delay
                
            except Exception as e:
                consecutive_errors += 1
                self.error_counts[direction] = self.error_counts.get(direction, 0) + 1
                
                if consecutive_errors <= 3:
                    self.logger.warn(f"{direction} handler error: {e}")
                elif consecutive_errors % 10 == 0:
                    self.logger.error(f"{direction} handler: {consecutive_errors} consecutive errors")
                
                time.sleep(0.01)  # Brief pause on error
        
        self.logger.info(f"{direction} handler shutting down")
    
    def _outgoing_port_handler(self, port_name: str):
        """Handle outgoing port: read data and queue for incoming port.
        
        This thread owns one outgoing port exclusively and reads all data from it.
        Data is then queued for the incoming port via the PortManager.
        
        Args:
            port_name: The outgoing port name (COM131 or COM141)
        """
        thread_name = threading.current_thread().name
        direction = f"{port_name}->Incoming"
        
        self.logger.info(f"Starting outgoing port handler: {direction}")
        
        consecutive_errors = 0
        while not self.shutdown_requested:
            try:
                # Update heartbeat
                self.thread_heartbeats[thread_name] = datetime.now()
                
                # Read data from owned outgoing port
                data = self.port_manager.read_available(port_name, thread_name)
                if data:
                    # Queue data for incoming port
                    if self.port_manager.queue_data_for_port(self.incoming_port, data, thread_name):
                        # Update statistics
                        self.bytes_transferred[direction] = self.bytes_transferred.get(direction, 0) + len(data)
                        
                        # Reset counter if needed (prevent overflow)
                        if self.bytes_transferred[direction] > 1000000:  # 1M bytes
                            self.logger.info(f"{direction}: Resetting byte counter at {self.bytes_transferred[direction]} bytes")
                            self.bytes_transferred[direction] = 0
                        
                        self.logger.debug(f"{direction}: {len(data)} bytes queued")
                        consecutive_errors = 0
                    else:
                        self.logger.warning(f"{direction}: Failed to queue data for incoming port")
                
                # Check for queued data to write to this outgoing port (from incoming port)
                queued_data = self.port_manager.get_queued_data(port_name)
                if queued_data:
                    if self.port_manager.write_data(port_name, queued_data, thread_name):
                        self.logger.debug(f"Wrote {len(queued_data)} bytes to {port_name}")
                    else:
                        self.logger.warning(f"Failed to write queued data to {port_name}")
                
                time.sleep(0.001)  # 1ms delay
                
            except Exception as e:
                consecutive_errors += 1
                self.error_counts[direction] = self.error_counts.get(direction, 0) + 1
                
                if consecutive_errors <= 3:
                    self.logger.warn(f"{direction} handler error: {e}")
                elif consecutive_errors % 10 == 0:
                    self.logger.error(f"{direction} handler: {consecutive_errors} consecutive errors")
                
                time.sleep(0.01)  # Brief pause on error
        
        self.logger.info(f"{direction} handler shutting down")
    
    def _start_routing_threads(self):
        """Start all routing threads with centralized port management."""
        self.routing_threads.clear()
        self.thread_heartbeats.clear()
        
        # Pre-acquire all ports with proper ownership to prevent conflicts
        self.logger.info("Acquiring port ownership for all routing threads...")
        
        # Acquire ports in sequence to prevent race conditions
        ports_to_acquire = [
            (self.incoming_port, self.incoming_baud, "IncomingPortOwner"),
            ("COM131", self.outgoing_baud, "Port131Owner"),
            ("COM141", self.outgoing_baud, "Port141Owner")
        ]
        
        acquired_ports = []
        for port_name, baud_rate, owner_name in ports_to_acquire:
            if self.port_manager.acquire_port(port_name, baud_rate, owner_name):
                acquired_ports.append((port_name, owner_name))
                self.logger.info(f"Successfully acquired {port_name} for {owner_name}")
            else:
                self.logger.error(f"Failed to acquire {port_name} for {owner_name}")
                # Release any previously acquired ports
                for prev_port, prev_owner in acquired_ports:
                    self.port_manager.release_port(prev_port, prev_owner)
                return False
        
        # All ports acquired successfully, now start threads
        self.logger.info("All ports acquired, starting routing threads...")
        
        # Thread 1: Owns incoming port, reads data and distributes
        thread1 = threading.Thread(
            target=self._incoming_port_handler,
            name="IncomingPortOwner"
        )
        
        # Thread 2: Owns COM131, reads data and routes to incoming
        thread2 = threading.Thread(
            target=self._outgoing_port_handler,
            args=("COM131",),
            name="Port131Owner"
        )
        
        # Thread 3: Owns COM141, reads data and routes to incoming
        thread3 = threading.Thread(
            target=self._outgoing_port_handler,
            args=("COM141",),
            name="Port141Owner"
        )
        
        for thread in [thread1, thread2, thread3]:
            thread.daemon = True
            thread.start()
            self.routing_threads.append(thread)
            self.thread_heartbeats[thread.name] = datetime.now()
        
        self.logger.info(f"Started {len(self.routing_threads)} routing threads with centralized port management")
        return True
    
    def _watchdog_monitor(self):
        """Monitor thread health and restart dead threads."""
        self.logger.info("Watchdog monitor started")
        
        while not self.shutdown_requested:
            try:
                current_time = datetime.now()
                
                for thread in self.routing_threads[:]:  # Copy list for safe iteration
                    if not thread.is_alive():
                        self.logger.error(f"Thread {thread.name} is dead, restarting")
                        self._restart_thread(thread)
                        continue
                    
                    # Check heartbeat
                    last_heartbeat = self.thread_heartbeats.get(thread.name, current_time)
                    if (current_time - last_heartbeat).total_seconds() > 30:  # 30 second timeout
                        self.logger.error(f"Thread {thread.name} heartbeat timeout, restarting")
                        self._restart_thread(thread)
                
                # Reset restart counters every hour
                if (current_time - self.thread_restart_window_start).total_seconds() > 3600:
                    self.thread_restart_counts.clear()
                    self.thread_restart_window_start = current_time
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Watchdog error: {e}")
                time.sleep(5)
    
    def _restart_thread(self, dead_thread: threading.Thread):
        """Restart a dead thread with rate limiting."""
        thread_name = dead_thread.name
        restart_count = self.thread_restart_counts.get(thread_name, 0)
        
        if restart_count >= 10:
            self.logger.error(f"Thread {thread_name} has been restarted {restart_count} times in the last hour, limiting restarts")
            time.sleep(60)  # Wait 1 minute before allowing restart
        
        self.thread_restart_counts[thread_name] = restart_count + 1
        
        # Remove from active threads list
        if dead_thread in self.routing_threads:
            self.routing_threads.remove(dead_thread)
        
        # Create new thread based on the dead one
        if "IncomingToBoth" in thread_name:
            new_thread = threading.Thread(
                target=self._route_data_with_recovery,
                args=(self.incoming_port, self.outgoing_ports, f"{self.incoming_port}->131&141"),
                name="IncomingToBoth"
            )
        elif "Port131ToIncoming" in thread_name:
            new_thread = threading.Thread(
                target=self._route_data_with_recovery,
                args=("COM131", [self.incoming_port], "131->Incoming"),
                name="Port131ToIncoming"
            )
        elif "Port141ToIncoming" in thread_name:
            new_thread = threading.Thread(
                target=self._route_data_with_recovery,
                args=("COM141", [self.incoming_port], "141->Incoming"),
                name="Port141ToIncoming"
            )
        else:
            self.logger.error(f"Unknown thread type: {thread_name}")
            return
        
        new_thread.daemon = True
        new_thread.start()
        self.routing_threads.append(new_thread)
        self.thread_heartbeats[new_thread.name] = datetime.now()
        
        self.logger.info(f"Restarted thread {thread_name}")
    
    def start(self):
        """Start the serial router."""
        if self.running:
            self.logger.warn("Router is already running")
            return
        
        self.logger.info(f"Starting SerialRouter - {self.incoming_port} <-> COM131 & COM141")
        self.logger.info(f"Incoming baud: {self.incoming_baud}, Outgoing baud: {self.outgoing_baud}")
        
        self.running = True
        self.shutdown_requested = False
        self.router_start_time = datetime.now()
        
        # Initialize statistics
        self.bytes_transferred.clear()
        self.error_counts.clear()
        
        # Start routing threads
        if not self._start_routing_threads():
            self.logger.error("SerialRouter failed to start - critical ports unavailable")
            self.running = False
            self.shutdown_requested = True
            return False
        
        # Start watchdog monitor
        self.watchdog_thread = threading.Thread(target=self._watchdog_monitor, name="Watchdog")
        self.watchdog_thread.daemon = True
        self.watchdog_thread.start()
        
        self.logger.info("SerialRouter started successfully")
        return True
    
    def stop(self):
        """Stop the serial router gracefully with proper PortManager cleanup."""
        if not self.running:
            return
        
        self.logger.info("Stopping SerialRouter...")
        self.shutdown_requested = True
        self.running = False
        
        # Wait for threads to finish (with timeout)
        shutdown_start = time.time()
        for thread in self.routing_threads:
            remaining_time = max(0, 5 - (time.time() - shutdown_start))
            thread.join(timeout=remaining_time)
        
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=2)
        
        # Properly release all port ownership through PortManager
        try:
            self.logger.info("Releasing port ownership...")
            port_owners = [
                (self.incoming_port, "IncomingPortOwner"),
                ("COM131", "Port131Owner"),
                ("COM141", "Port141Owner")
            ]
            
            for port_name, owner_name in port_owners:
                if self.port_manager.release_port(port_name, owner_name):
                    self.logger.info(f"Successfully released {port_name} from {owner_name}")
                else:
                    self.logger.warning(f"Failed to release {port_name} from {owner_name}")
                    
        except Exception as e:
            self.logger.error(f"Error during port release: {e}")
            # Emergency cleanup if individual releases fail
            self.logger.info("Performing emergency PortManager cleanup...")
            self.port_manager.cleanup_all_ports()
        
        self.logger.info("SerialRouter stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive router status including advanced monitoring metrics."""
        current_time = datetime.now()
        
        # Get basic router status
        active_threads = len([t for t in self.routing_threads if t.is_alive()])
        
        # Get detailed port status from PortManager
        port_status = self.port_manager.get_port_status()
        
        # Calculate system uptime
        uptime_seconds = 0
        if self.router_start_time:
            uptime_seconds = (current_time - self.router_start_time).total_seconds()
        
        # Calculate total system throughput
        total_current_throughput = 0
        for port_name, port_info in port_status.items():
            if 'throughput' in port_info:
                total_current_throughput += port_info['throughput'].get('bytes_per_second', 0)
        
        # Update peak throughput
        if total_current_throughput > self.peak_throughput:
            self.peak_throughput = total_current_throughput
        
        # Combine PortManager stats with router stats for comprehensive view
        combined_bytes_transferred = self.bytes_transferred.copy()
        
        # Add PortManager port statistics to the status
        for port_name, port_info in port_status.items():
            if 'stats' in port_info and port_info['stats']:
                stats = port_info['stats']
                port_key = f"{port_name}_port_stats"
                combined_bytes_transferred[port_key] = {
                    'bytes_read': stats.get('bytes_read', 0),
                    'bytes_written': stats.get('bytes_written', 0),
                    'errors': stats.get('errors', 0),
                    'reconnects': stats.get('reconnects', 0)
                }
        
        # Calculate critical metrics for dashboard
        connected_ports = sum(1 for port_info in port_status.values() 
                             if port_info.get('connected', False))
        total_ports = len(port_status)
        
        # Get time since last activity across all ports
        most_recent_activity = None
        for port_info in port_status.values():
            last_activity = port_info.get('last_activity')
            if last_activity:
                if most_recent_activity is None or last_activity > most_recent_activity:
                    most_recent_activity = last_activity
        
        seconds_since_last_activity = 0
        if most_recent_activity:
            seconds_since_last_activity = (current_time - most_recent_activity).total_seconds()
        
        # Calculate total error rates
        total_errors_per_hour = 0
        for port_info in port_status.values():
            if 'error_metrics' in port_info:
                total_errors_per_hour += port_info['error_metrics'].get('errors_per_hour', 0)
        
        # Calculate average queue utilization
        total_queue_utilization = 0
        queue_count = 0
        for port_info in port_status.values():
            if 'queue_performance' in port_info:
                util = port_info['queue_performance'].get('queue_utilization_percent', 0)
                if util is not None:
                    total_queue_utilization += util
                    queue_count += 1
        
        avg_queue_utilization = total_queue_utilization / queue_count if queue_count > 0 else 0
        
        return {
            # Core system status
            "running": self.running,
            "incoming_port": self.incoming_port,
            "outgoing_ports": self.outgoing_ports,
            "active_threads": active_threads,
            "bytes_transferred": combined_bytes_transferred,
            "error_counts": self.error_counts.copy(),
            "thread_restart_counts": self.thread_restart_counts.copy(),
            
            # Critical monitoring dashboard metrics
            "critical_metrics": {
                "system_uptime_hours": round(uptime_seconds / 3600, 2),
                "active_connections": f"{connected_ports}/{total_ports}",
                "current_throughput_bps": round(total_current_throughput, 0),
                "data_loss_events_24h": self.data_loss_events,  # TODO: implement 24h window
                "error_rate_per_hour": round(total_errors_per_hour, 2),
                "seconds_since_last_activity": round(seconds_since_last_activity, 1),
                "avg_queue_utilization_percent": round(avg_queue_utilization, 1),
                "peak_throughput_bps": round(self.peak_throughput, 0)
            },
            
            # Enhanced PortManager status information
            "port_manager_status": port_status,
            "port_connections": {
                port_name: {
                    "connected": port_info.get('connected', False),
                    "owner": port_info.get('owner', None),
                    "last_activity": port_info.get('last_activity'),
                    "queue_size": port_info.get('queue_size', 0),
                    "error_count": port_info.get('error_count', 0),
                    "throughput_bps": port_info.get('throughput', {}).get('bytes_per_second', 0),
                    "uptime_percent": port_info.get('connection_reliability', {}).get('uptime_percentage', 0),
                    "mtbf_hours": port_info.get('connection_reliability', {}).get('mtbf_hours'),
                    "queue_latency_ms": port_info.get('queue_performance', {}).get('avg_latency_ms', 0)
                }
                for port_name, port_info in port_status.items()
            },
            
            # System health metrics
            "system_health": {
                "all_ports_connected": all(
                    port_info.get('connected', False) for port_info in port_status.values()
                ),
                "total_port_errors": sum(
                    port_info.get('error_count', 0) for port_info in port_status.values()
                ),
                "total_queue_backlog": sum(
                    port_info.get('queue_size', 0) for port_info in port_status.values()
                ),
                "system_load_percent": min(100, avg_queue_utilization),
                "overall_health_status": self._calculate_health_status(port_status, connected_ports, total_ports)
            }
        }
    
    def _calculate_health_status(self, port_status: Dict, connected_ports: int, total_ports: int) -> str:
        """Calculate overall system health status."""
        if connected_ports < total_ports:
            return "Critical"
        
        # Check error rates
        high_error_rate = any(
            port_info.get('error_metrics', {}).get('errors_per_hour', 0) > 10
            for port_info in port_status.values()
        )
        
        if high_error_rate:
            return "Warning"
        
        # Check queue utilization
        high_queue_usage = any(
            port_info.get('queue_performance', {}).get('queue_utilization_percent', 0) > 80
            for port_info in port_status.values()
        )
        
        if high_queue_usage:
            return "Warning"
        
        # Check recent activity
        any_recent_activity = any(
            port_info.get('connection_reliability', {}).get('seconds_since_last_activity', float('inf')) < 60
            for port_info in port_status.values()
        )
        
        if any_recent_activity:
            return "Good"
        else:
            return "Ok"


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global router
    print("\n\nShutdown signal received...")
    if router:
        router.stop()
    sys.exit(0)


def main():
    """Main entry point."""
    global router
    
    # Setup signal handling
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        print("SerialRouter Production v1.0")
        print("=" * 50)
        
        # Initialize router
        router = SerialRouterCore()
        
        # Start routing
        router.start()
        
        print("Routing active. Press Ctrl+C to stop.")
        print(f"Logging to: serial_router.log")
        print("=" * 50)
        
        # Status reporting loop
        while router.running:
            time.sleep(30)  # Status update every 30 seconds
            status = router.get_status()
            
            if status["bytes_transferred"]:
                total_bytes = sum(status["bytes_transferred"].values())
                print(f"Status: {status['active_threads']}/3 threads active, {total_bytes:,} bytes transferred")
            
            if status["error_counts"]:
                total_errors = sum(status["error_counts"].values())
                if total_errors > 0:
                    print(f"Errors: {total_errors} total")
    
    except Exception as e:
        print(f"Fatal error: {e}")
        if router:
            router.logger.error(f"Fatal error: {e}")
            router.logger.error(f"Traceback: {traceback.format_exc()}")
    
    finally:
        if router:
            router.stop()


if __name__ == "__main__":
    router = None
    main()