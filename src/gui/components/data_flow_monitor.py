"""
Data Flow Monitor Widget for SerialRouter
Displays real-time statistics, health metrics, and data flow monitoring.
"""

from datetime import datetime
from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QLabel, QGroupBox, QGridLayout, QVBoxLayout,
    QHBoxLayout, QFormLayout, QProgressBar, QApplication, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtProperty, QRectF, QTimer, QEvent
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush, QFontDatabase
from src.gui.resources import resource_manager


class MetricMeter:
    """
    Dynamic scaling calculator for activity meters.
    Uses rolling window maximum with decay to adapt to traffic patterns.
    """

    def __init__(self, min_scale=100, max_scale=50000, decay=0.98):
        """
        Args:
            min_scale: Minimum scale value (B/s) - prevents noise at low rates
            max_scale: Maximum scale value (B/s) - caps at practical serial limits
            decay: Decay factor per update (0.98 = 2% decay)
        """
        self.min_scale = min_scale      # 100 B/s minimum
        self.max_scale = max_scale      # 50 KB/s max (high-speed serial)
        self.decay = decay              # 2% decay per update
        self.current_max = min_scale

    def update(self, current_rate: float) -> int:
        """
        Calculate percentage for meter display based on current rate.

        Args:
            current_rate: Current transfer rate in B/s

        Returns:
            Percentage 0-100 for meter display
        """
        # Update rolling max with decay
        self.current_max = max(
            self.min_scale,
            min(self.max_scale, max(current_rate, self.current_max * self.decay))
        )

        # Calculate percentage
        return int(min(100, (current_rate / self.current_max) * 100))


class HorizontalActivityMeter(QWidget):
    """
    Horizontal segmented bar for real-time rate visualization.
    Displays current transfer rate as a left-to-right filling meter.
    Compact design for table row layout.
    """

    def __init__(self, parent=None, num_segments: int = 10):
        super().__init__(parent)

        # Configuration
        self._num_segments = num_segments
        self._current_value = 0.0  # 0-100 percentage
        self._target_value = 0.0   # For smooth animation

        # Set fixed compact dimensions
        self.setFixedWidth(120)
        self.setFixedHeight(18)

        # Animation timer for smooth transitions
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_value)
        self._animation_timer.setInterval(50)  # 20 FPS

        # Cache colors from palette
        self._update_colors()

        # Connect to application palette changes
        QApplication.instance().paletteChanged.connect(self._on_palette_changed)

    def _on_palette_changed(self, palette):
        """Handle application palette changes to maintain theme consistency."""
        self._update_colors()
        self.update()  # Trigger repaint with new colors

    def _update_colors(self):
        """Update cached colors from application palette."""
        palette = QApplication.palette()

        # Use green accent color for activity indication
        self._accent_color = QColor("#28A745")  # Green from enable.svg
        self._border_color = palette.color(QPalette.ColorRole.Mid)

    def setValue(self, value: int):
        """
        Set the meter value (0-100) with smooth animation.

        Args:
            value: Percentage 0-100 for meter display
        """
        self._target_value = max(0, min(100, value))

        # Start animation if not already running
        if not self._animation_timer.isActive():
            self._animation_timer.start()

    def _animate_value(self):
        """Smoothly animate current value towards target."""
        diff = self._target_value - self._current_value

        # Ease towards target
        if abs(diff) < 0.5:
            self._current_value = self._target_value
            self._animation_timer.stop()
        else:
            self._current_value += diff * 0.3  # Smooth easing

        self.update()  # Trigger repaint

    def paintEvent(self, event):
        """Paint horizontal segments from left to right."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Calculate segment dimensions
        segment_gap = 2
        segment_width = (width - (self._num_segments + 1) * segment_gap) / self._num_segments
        segment_height = height - 4  # Leave 2px margin top/bottom

        # Calculate how many segments to fill
        filled_segments = int((self._current_value / 100) * self._num_segments)
        partial_fill = ((self._current_value / 100) * self._num_segments) - filled_segments

        # Draw segments from left to right
        for i in range(self._num_segments):
            # Calculate X position (left to right)
            x = i * (segment_width + segment_gap) + segment_gap
            y = 2

            # Progressive opacity (segments towards right = more opaque)
            base_intensity = (i + 1) / self._num_segments
            segment_opacity = 0.70 + (base_intensity * 0.30)

            # Determine fill state
            if i < filled_segments:
                # Fully filled segment
                color = QColor(self._accent_color)
                alpha = int(segment_opacity * 255)
            elif i == filled_segments and partial_fill > 0:
                # Partially filled segment
                color = QColor(self._accent_color)
                alpha = int(partial_fill * segment_opacity * 255)
            else:
                # Empty segment
                color = QColor(self._border_color)
                alpha = 0

            # Draw segment
            color.setAlpha(alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(self._border_color, 0.5))
            painter.drawRoundedRect(QRectF(x, y, segment_width, segment_height), 1, 1)


class TransferTableRow(QWidget):
    """
    Single row in the transfer activity table.
    Combines port label, direction, rate meter+label, and total bytes.
    Compact horizontal layout for space efficiency.
    """

    def __init__(self, port_name: str, direction: str, direction_icon: str, parent=None):
        super().__init__(parent)

        # Get monospace font for numeric displays
        self._mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        # Store direction icon name
        self._direction_icon = direction_icon

        # Create widgets
        self.port_label = QLabel(port_name)
        self.port_label.setFixedWidth(80)
        self.port_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Direction column (icon + text)
        self.direction_container = QWidget()
        self.direction_layout = QHBoxLayout(self.direction_container)
        self.direction_layout.setContentsMargins(0, 0, 0, 0)
        self.direction_layout.setSpacing(4)  # Match toolbar spacing

        # Load direction icon (preserve original colors)
        icon = resource_manager.load_icon(f"{direction_icon}.svg", "stats")
        if not icon.isNull():
            self.direction_icon_label = QLabel()
            self.direction_icon_label.setPixmap(icon.pixmap(16, 16))
            self.direction_icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            self.direction_layout.addWidget(self.direction_icon_label)

        self.direction_label = QLabel(direction)
        self.direction_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.direction_layout.addWidget(self.direction_label)
        self.direction_layout.addStretch()

        self.direction_container.setFixedWidth(100)

        # Current Rate column (horizontal meter + label)
        self.rate_meter = HorizontalActivityMeter()
        self.rate_label = QLabel("0 B/s")
        self.rate_label.setFont(self._mono_font)
        self.rate_label.setMinimumWidth(70)
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Total Volume column (numeric value only)
        self.volume_label = QLabel("0 bytes")
        self.volume_label.setFont(self._mono_font)
        self.volume_label.setMinimumWidth(80)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._init_ui()

    def _init_ui(self):
        """Build row layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)  # Reduced vertical padding
        layout.setSpacing(10)

        # Column 1: Port
        layout.addWidget(self.port_label)

        # Column 2: Direction (icon + text container)
        layout.addWidget(self.direction_container)

        # Column 3: Current Rate (meter + label inline)
        rate_container = QWidget()
        rate_layout = QHBoxLayout(rate_container)
        rate_layout.setContentsMargins(0, 0, 0, 0)
        rate_layout.setSpacing(8)
        rate_layout.addWidget(self.rate_meter)
        rate_layout.addWidget(self.rate_label)
        rate_layout.addStretch()
        layout.addWidget(rate_container)

        # Column 4: Total Volume (numeric value only)
        layout.addWidget(self.volume_label)
        layout.addStretch()

    def update_data(self, rate: float, total_bytes: int, rate_percentage: int):
        """
        Update all displays for this row.

        Args:
            rate: Current transfer rate in B/s
            total_bytes: Cumulative bytes transferred
            rate_percentage: Percentage 0-100 for rate meter
        """
        self.rate_label.setText(self._format_rate(rate))
        self.volume_label.setText(self._format_bytes(total_bytes))
        self.rate_meter.setValue(rate_percentage)

    def _format_rate(self, rate: float) -> str:
        """Format transfer rate."""
        if rate > 1024:
            return f"{rate/1024:.1f} KB/s"
        else:
            return f"{rate:.0f} B/s"

    def _format_bytes(self, count: int) -> str:
        """Format byte count."""
        if count > 1_000_000:
            return f"{count/1_000_000:.1f} MB"
        elif count > 1024:
            return f"{count/1024:.1f} KB"
        else:
            return f"{count} bytes"

    def set_port_name(self, port_name: str):
        """Update port label dynamically."""
        self.port_label.setText(port_name)


class DataFlowMonitorWidget(QWidget):
    """
    Self-contained data flow monitoring widget.
    Handles all stats display, formatting, and state tracking.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Internal state tracking
        self.last_bytes_transferred = {}
        self.last_update_time = datetime.now()
        self._last_status_error = None
        self._last_status_error_time = None

        # Current port configuration
        self._current_incoming_port = "COM54"
        self._current_port1 = "COM131"
        self._current_port2 = "COM141"

        # Table row references
        self.incoming_row = None
        self.port1_row = None
        self.port2_row = None

        # System status references
        self.connections_label = None
        self.thread_status_label = None
        self.error_count_label = None
        self.health_status_label = None
        self.queue_util_label = None
        self.uptime_label = None
        self.session_duration_label = None
        self.last_reset_label = None

        # Dynamic scaling trackers (simplified to 3)
        self.meter_tracker_incoming = MetricMeter()
        self.meter_tracker_port1 = MetricMeter()
        self.meter_tracker_port2 = MetricMeter()

        # Build UI
        self._init_ui()


    def _get_monospace_font(self) -> QFont:
        """Get the system's fixed-width font for numeric displays."""
        return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

    def _init_ui(self):
        """Initialize the monitoring UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Data Transfer Table Section (borderless)
        transfer_group = QWidget()
        transfer_outer_layout = QVBoxLayout(transfer_group)
        transfer_outer_layout.setContentsMargins(0, 0, 0, 0)
        transfer_outer_layout.setSpacing(5)

        # Add title label
        title_label = QLabel("Data Transfer")
        title_label.setStyleSheet("font-weight: bold;")
        transfer_outer_layout.addWidget(title_label)

        # Create container for table content
        transfer_content = QWidget()
        transfer_layout = QVBoxLayout(transfer_content)
        transfer_layout.setSpacing(4)
        transfer_layout.setContentsMargins(0, 0, 0, 0)

        # Header row
        header_row = self._create_header_row()
        transfer_layout.addWidget(header_row)

        # Data rows
        self.incoming_row = TransferTableRow(self._current_incoming_port, "Broadcast", "to_client")
        self.port1_row = TransferTableRow(self._current_port1, "Response", "from_client")
        self.port2_row = TransferTableRow(self._current_port2, "Response", "from_client")

        transfer_layout.addWidget(self.incoming_row)
        transfer_layout.addWidget(self.port1_row)
        transfer_layout.addWidget(self.port2_row)

        transfer_outer_layout.addWidget(transfer_content)
        layout.addWidget(transfer_group)

        # System Status (keep existing _create_health_group)
        health_group = self._create_health_group()
        layout.addWidget(health_group)

        layout.addStretch()

    def _create_header_row(self) -> QWidget:
        """Create table column headers with icons."""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(5, 0, 5, 5)
        layout.setSpacing(10)

        # Helper function to create icon+text header
        def create_header_with_icon(icon_name: str, text: str, width: int, subfolder: str = "stats"):
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)  # Match toolbar spacing

            # Load icon preserving original colors
            icon = resource_manager.load_icon(f"{icon_name}.svg", subfolder)

            if not icon.isNull():
                icon_label = QLabel()
                icon_label.setPixmap(icon.pixmap(16, 16))
                icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                container_layout.addWidget(icon_label)

            # Add text label
            text_label = QLabel(text)
            text_label.setStyleSheet("font-weight: bold;")
            container_layout.addWidget(text_label)
            container_layout.addStretch()

            if width > 0:
                container.setFixedWidth(width)
            else:
                container.setMinimumWidth(width)

            return container

        # Port header (using port_icon from root icons folder)
        port_header = create_header_with_icon("port_icon", "Port", 80, subfolder="")
        layout.addWidget(port_header)

        # Direction header (using data_outbound as generic direction indicator)
        direction_header = create_header_with_icon("data_outbound", "Direction", 100, subfolder="stats")
        layout.addWidget(direction_header)

        # Rate header
        rate_header = create_header_with_icon("transfer_rate", "Current Rate", 200, subfolder="stats")
        layout.addWidget(rate_header)

        # Total header
        volume_header = create_header_with_icon("session_stats", "Total", 100, subfolder="stats")
        layout.addWidget(volume_header)

        layout.addStretch()

        return header

    def _create_health_group(self) -> QWidget:
        """Create system health display with compact multi-column grid layout."""
        # Use QWidget with title label (no border)
        group = QWidget()
        outer_layout = QVBoxLayout(group)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(5)

        # Add title label
        title_label = QLabel("System Status")
        title_label.setStyleSheet("font-weight: bold;")
        outer_layout.addWidget(title_label)

        # Create grid for metrics
        metrics_widget = QWidget()
        main_layout = QGridLayout(metrics_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Get system monospace font for numeric values
        mono_font = self._get_monospace_font()

        # Helper function to create metric row
        def create_metric(label_text: str, value_text: str):
            label = QLabel(label_text)
            label.setMinimumWidth(80)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            value = QLabel(value_text)
            value.setFont(mono_font)
            value.setMinimumWidth(120)
            value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            return label, value

        # Column 1: Connection metrics
        conn_label, self.connections_label = create_metric("Connections:", "0/3")
        main_layout.addWidget(conn_label, 0, 0)
        main_layout.addWidget(self.connections_label, 0, 1)

        thread_label, self.thread_status_label = create_metric("Threads:", "0/3 Active")
        main_layout.addWidget(thread_label, 1, 0)
        main_layout.addWidget(self.thread_status_label, 1, 1)

        error_label, self.error_count_label = create_metric("Errors:", "0")
        main_layout.addWidget(error_label, 2, 0)
        main_layout.addWidget(self.error_count_label, 2, 1)

        # Column 2: Health metrics
        health_label, self.health_status_label = create_metric("Health:", "Offline")
        main_layout.addWidget(health_label, 0, 2)
        main_layout.addWidget(self.health_status_label, 0, 3)

        queue_label, self.queue_util_label = create_metric("Queue:", "0%")
        main_layout.addWidget(queue_label, 1, 2)
        main_layout.addWidget(self.queue_util_label, 1, 3)

        uptime_label, self.uptime_label = create_metric("Uptime:", "0 hours")
        main_layout.addWidget(uptime_label, 2, 2)
        main_layout.addWidget(self.uptime_label, 2, 3)

        # Column 3: Session metrics
        session_label, self.session_duration_label = create_metric("Session:", "0h 0m")
        main_layout.addWidget(session_label, 0, 4)
        main_layout.addWidget(self.session_duration_label, 0, 5)

        reset_label, self.last_reset_label = create_metric("Last Reset:", "Never")
        main_layout.addWidget(reset_label, 1, 4)
        main_layout.addWidget(self.last_reset_label, 1, 5)

        outer_layout.addWidget(metrics_widget)
        return group

    def update_display(self, status: Dict[str, Any],
                       incoming_port: str,
                       outgoing_port1: str,
                       outgoing_port2: str):
        """
        Update all stats displays with current router status.

        Args:
            status: Router status dictionary from router_core.get_status()
            incoming_port: Currently selected incoming port (e.g., "COM54")
            outgoing_port1: First outgoing port (e.g., "COM131")
            outgoing_port2: Second outgoing port (e.g., "COM141")
        """
        # Store current port configuration
        self._current_incoming_port = incoming_port
        self._current_port1 = outgoing_port1
        self._current_port2 = outgoing_port2

        # Update port labels dynamically
        self.incoming_row.set_port_name(incoming_port)
        self.port1_row.set_port_name(outgoing_port1)
        self.port2_row.set_port_name(outgoing_port2)

        try:
            bytes_data = status.get("bytes_transferred", {})
            session_totals = status.get("session_totals", {})
            transfer_rates = status.get("transfer_rates", {})

            # INCOMING BROADCAST DATA
            # This is the data going from incoming port to both outgoing clients
            out_direction = f"{incoming_port}->{outgoing_port1.replace('COM', '')}&{outgoing_port2.replace('COM', '')}"
            out_rate = transfer_rates.get(out_direction, 0)
            out_bytes = bytes_data.get(out_direction, 0)

            # Calculate dynamic meter percentage
            rate_percentage = self.meter_tracker_incoming.update(out_rate)

            # Update incoming row
            self.incoming_row.update_data(
                rate=out_rate,
                total_bytes=out_bytes,
                rate_percentage=rate_percentage
            )

            # PORT 1 RESPONSE DATA
            # Data coming back from outgoing_port1 to incoming
            in1_direction = f"{outgoing_port1}->Incoming"
            in1_rate = transfer_rates.get(in1_direction, 0)
            in1_bytes = bytes_data.get(in1_direction, 0)
            rate_percentage1 = self.meter_tracker_port1.update(in1_rate)

            self.port1_row.update_data(
                rate=in1_rate,
                total_bytes=in1_bytes,
                rate_percentage=rate_percentage1
            )

            # PORT 2 RESPONSE DATA
            # Data coming back from outgoing_port2 to incoming
            in2_direction = f"{outgoing_port2}->Incoming"
            in2_rate = transfer_rates.get(in2_direction, 0)
            in2_bytes = bytes_data.get(in2_direction, 0)
            rate_percentage2 = self.meter_tracker_port2.update(in2_rate)

            self.port2_row.update_data(
                rate=in2_rate,
                total_bytes=in2_bytes,
                rate_percentage=rate_percentage2
            )

            # UPDATE SYSTEM STATUS
            self._update_system_status(status)

        except Exception as e:
            # Error tracking
            import time
            error_type = type(e).__name__
            if not self._last_status_error or self._last_status_error != error_type:
                self._last_status_error = error_type
                self._last_status_error_time = time.time()

    def _update_system_status(self, status: Dict[str, Any]):
        """Update system status section (extracted from update_display)."""
        critical_metrics = status.get("critical_metrics", {})

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

        # Queue utilization
        queue_util = critical_metrics.get("avg_queue_utilization_percent", 0)
        self.queue_util_label.setText(f"{queue_util:.1f}%")

        # Health status
        system_health = status.get("system_health", {})
        health_status = system_health.get("overall_health_status", "UNKNOWN")
        self.health_status_label.setText(health_status)

        # Thread health display
        active_threads = status.get("active_threads", 0)
        self.thread_status_label.setText(f"{active_threads}/3 Active")

        # Update session duration
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

        # Error counts
        error_data = status.get("error_counts", {})
        router_errors = 0
        for key, value in error_data.items():
            if isinstance(value, int):
                router_errors += value

        port_errors = system_health.get("total_port_errors", 0)
        total_errors = router_errors + port_errors
        self.error_count_label.setText(str(total_errors))

        # Port connection status
        port_connections = status.get("port_connections", {})
        if port_connections:
            connected_ports = sum(1 for p in port_connections.values() if p.get("connected", False))
            total_ports = len(port_connections)

            if total_ports > 0:
                connection_status = f" ({connected_ports}/{total_ports} ports)"
                current_text = self.thread_status_label.text()
                if "ports)" not in current_text:
                    self.thread_status_label.setText(current_text + connection_status)

    def reset_display(self):
        """Reset all displays to zero/offline state."""
        # Reset table rows
        if self.incoming_row:
            self.incoming_row.update_data(0, 0, 0)
        if self.port1_row:
            self.port1_row.update_data(0, 0, 0)
        if self.port2_row:
            self.port2_row.update_data(0, 0, 0)

        # Reset system status
        self.uptime_label.setText("0 hours")
        self.connections_label.setText("0/3")
        self.health_status_label.setText("Offline")
        self.thread_status_label.setText("0/3 Active")
        self.error_count_label.setText("0")
        self.queue_util_label.setText("0%")
        self.session_duration_label.setText("0h 0m")
        self.last_reset_label.setText("Never")

        # Reset metric trackers
        self.meter_tracker_incoming = MetricMeter()
        self.meter_tracker_port1 = MetricMeter()
        self.meter_tracker_port2 = MetricMeter()
