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
from PyQt6.QtCore import Qt, QRectF, QTimer
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
    Compact design for table row layout with professional VU meter appearance.
    """

    def __init__(self, parent=None, num_segments: int = 20):
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

        # Use brand blue accent color for activity indication
        self._accent_color = QColor("#4f90cd")  # Blue accent - brand color
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

        # Load direction indicator icon (broadcast or response)
        icon = resource_manager.get_stats_icon(direction_icon)
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


class AnimatedHealthIndicator(QWidget):
    """
    Animated colored dot for health status visualization.
    Pulses for warning/critical states, static for normal states.
    Uses simple QTimer + manual painting (proven reliable approach).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Fixed size for the indicator dot
        self.setFixedSize(20, 20)

        # Current state
        self._color = QColor("#6C757D")  # Default grey
        self._opacity = 1.0
        self._opacity_direction = -1  # -1 = fading out, 1 = fading in

        # Animation timer (like ConnectionLine flow animation)
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._update_animation)
        self._animation_timer.setInterval(50)  # 50ms = 20 FPS

    def set_status(self, status: str):
        """Update color and animation based on health status."""
        # Map actual router status values to colors
        color_map = {
            "Good": QColor("#28A745"),       # Green - pulse (active, healthy)
            "Ok": QColor("#28A745"),         # Green - pulse (idle, healthy)
            "Warning": QColor("#FFC107"),    # Yellow - pulse (degraded)
            "Critical": QColor("#DC3545"),   # Red - pulse (critical)
            "OFFLINE": QColor("#6C757D"),    # Gray - static (stopped)
            "UNKNOWN": QColor("#6C757D")     # Gray - static (unknown)
        }

        self._color = color_map.get(status, QColor("#6C757D"))

        # Enable animation for all active states (only OFFLINE/UNKNOWN are static)
        should_animate = status in ["Good", "Ok", "Warning", "Critical"]

        if should_animate:
            # Start pulsing animation
            if not self._animation_timer.isActive():
                self._opacity = 1.0
                self._opacity_direction = -1
                self._animation_timer.start()
        else:
            # Stop animation and reset to full opacity
            if self._animation_timer.isActive():
                self._animation_timer.stop()
            self._opacity = 1.0

        # Force repaint
        self.update()

    def _update_animation(self):
        """Update opacity for pulsing effect (1.0 → 0.4 → 1.0)."""
        self._opacity += self._opacity_direction * 0.02

        # Reverse direction at boundaries
        if self._opacity <= 0.4:
            self._opacity = 0.4
            self._opacity_direction = 1
        elif self._opacity >= 1.0:
            self._opacity = 1.0
            self._opacity_direction = -1

        # Trigger repaint
        self.update()

    def paintEvent(self, event):
        """Draw the colored indicator dot with current opacity."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Apply opacity to color
        color = QColor(self._color)
        color.setAlphaF(self._opacity)

        # Draw filled circle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(120), 1))

        # Center the dot in the widget
        dot_size = 12
        x = (self.width() - dot_size) // 2
        y = (self.height() - dot_size) // 2

        painter.drawEllipse(x, y, dot_size, dot_size)


class HealthTableRow(QWidget):
    """
    Single row in the system health/status table.
    Combines metric label (icon + text), value display, and optional visual indicator.
    Matches the clean design of TransferTableRow.
    """

    @staticmethod
    def format_status(status: str) -> str:
        """
        Format status text for display (proper case instead of all caps).

        Args:
            status: Raw status string (e.g., "HEALTHY", "DEGRADED")

        Returns:
            Formatted status string (e.g., "Healthy", "Degraded")
        """
        if not status:
            return "—"
        return status.capitalize()

    def __init__(self, metric_name: str, metric_icon: str, icon_subfolder: str = "toolbar",
                 show_indicator: bool = False, show_meter: bool = False, parent=None):
        super().__init__(parent)

        # Get monospace font for numeric displays
        self._mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        # Store configuration
        self._metric_icon = metric_icon
        self._icon_subfolder = icon_subfolder
        self._show_indicator = show_indicator
        self._show_meter = show_meter

        # Create widgets
        # Column 1: Metric name (icon + text)
        self.metric_container = QWidget()
        self.metric_layout = QHBoxLayout(self.metric_container)
        self.metric_layout.setContentsMargins(0, 0, 0, 0)
        self.metric_layout.setSpacing(4)

        # Load metric icon
        if icon_subfolder == "stats" or icon_subfolder == "":
            icon = resource_manager.get_stats_icon(metric_icon, icon_subfolder)
        else:
            icon = resource_manager.load_icon(f"{metric_icon}.svg", icon_subfolder)
        if not icon.isNull():
            self.metric_icon_label = QLabel()
            self.metric_icon_label.setPixmap(icon.pixmap(16, 16))
            self.metric_icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            self.metric_layout.addWidget(self.metric_icon_label)

        self.metric_label = QLabel(metric_name)
        self.metric_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.metric_layout.addWidget(self.metric_label)
        self.metric_layout.addStretch()
        self.metric_container.setFixedWidth(150)

        # Column 2: Value display
        self.value_label = QLabel("—")
        self.value_label.setFont(self._mono_font)
        self.value_label.setMinimumWidth(120)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Column 3: Visual indicator (optional)
        self.indicator_container = QWidget()
        indicator_layout = QHBoxLayout(self.indicator_container)
        indicator_layout.setContentsMargins(0, 0, 0, 0)
        indicator_layout.setSpacing(8)

        if show_indicator:
            # Animated color dot indicator for health status
            self.indicator_label = AnimatedHealthIndicator()
            indicator_layout.addWidget(self.indicator_label)

        if show_meter:
            # Horizontal meter for queue utilization
            self.indicator_meter = HorizontalActivityMeter()
            indicator_layout.addWidget(self.indicator_meter)

        indicator_layout.addStretch()
        self.indicator_container.setFixedWidth(140)

        self._init_ui()

    def _init_ui(self):
        """Build row layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)

        layout.addWidget(self.metric_container)
        layout.addWidget(self.value_label)
        layout.addWidget(self.indicator_container)
        layout.addStretch()

    def update_value(self, value: str):
        """Update the value display."""
        self.value_label.setText(value)

    def update_indicator(self, status: str):
        """
        Update the health status indicator color and animation.

        Args:
            status: One of HEALTHY, DEGRADED, CRITICAL, OFFLINE, UNKNOWN
        """
        if not self._show_indicator:
            return

        self.indicator_label.set_status(status)

    def update_meter(self, percentage: int):
        """Update the meter display (for queue utilization)."""
        if self._show_meter:
            self.indicator_meter.setValue(percentage)


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

        # Current port configuration - will be set by main window
        self._current_incoming_port = ""
        self._current_port1 = "COM131"
        self._current_port2 = "COM141"

        # Table row references - Data Transfer
        self.incoming_row = None
        self.port1_row = None
        self.port2_row = None

        # Table row references - System Status
        self.health_row = None
        self.uptime_row = None
        self.connections_row = None
        self.queue_row = None
        self.errors_row = None
        self.error_rate_row = None

        # Error rate tracking
        self._error_history = []  # List of (timestamp, error_count) tuples
        self._last_error_count = 0

        # Dynamic scaling trackers (simplified to 3)
        self.meter_tracker_incoming = MetricMeter()
        self.meter_tracker_port1 = MetricMeter()
        self.meter_tracker_port2 = MetricMeter()
        self.meter_tracker_queue = MetricMeter(min_scale=1, max_scale=100)  # For queue percentage

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
        self.incoming_row = TransferTableRow(self._current_incoming_port, "Broadcast", "broadcast_icon")
        self.port1_row = TransferTableRow(self._current_port1, "Response", "response_icon")
        self.port2_row = TransferTableRow(self._current_port2, "Response", "response_icon")

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

            # Load icon with proper coloring
            if subfolder == "stats" or subfolder == "":
                icon = resource_manager.get_stats_icon(icon_name, subfolder)
            else:
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

        # Direction header (using bidirectional arrow icon)
        direction_header = create_header_with_icon("direction_icon", "Direction", 100, subfolder="stats")
        layout.addWidget(direction_header)

        # Rate header
        rate_header = create_header_with_icon("transfer_rate", "Current Rate", 200, subfolder="stats")
        layout.addWidget(rate_header)

        # Total header
        volume_header = create_header_with_icon("session_total", "Total", 100, subfolder="stats")
        layout.addWidget(volume_header)

        layout.addStretch()

        return header

    def _create_health_header_row(self) -> QWidget:
        """Create table column headers for system status section."""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(5, 0, 5, 5)
        layout.setSpacing(10)

        # Helper function to create icon+text header
        def create_header_with_icon(icon_name: str, text: str, width: int, subfolder: str = "stats"):
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)

            # Load icon with proper coloring
            if subfolder == "stats" or subfolder == "":
                icon = resource_manager.get_stats_icon(icon_name, subfolder)
            else:
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
                container.setMinimumWidth(abs(width))

            return container

        # Metric header
        metric_header = create_header_with_icon("session_stats", "Metric", 150, subfolder="stats")
        layout.addWidget(metric_header)

        # Value header
        value_header = create_header_with_icon("session_total", "Value", 120, subfolder="stats")
        layout.addWidget(value_header)

        # Status/Indicator header
        status_header = create_header_with_icon("transfer_rate", "Status", 140, subfolder="stats")
        layout.addWidget(status_header)

        layout.addStretch()

        return header

    def _create_health_group(self) -> QWidget:
        """Create system status display with clean table layout (no headers, self-evident design)."""
        # Use QWidget with title label (no border)
        group = QWidget()
        outer_layout = QVBoxLayout(group)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(5)

        # Add title label
        title_label = QLabel("System Status")
        title_label.setStyleSheet("font-weight: bold;")
        outer_layout.addWidget(title_label)

        # Create container for table content
        health_content = QWidget()
        health_layout = QVBoxLayout(health_content)
        health_layout.setSpacing(4)
        health_layout.setContentsMargins(0, 0, 0, 0)

        # Data rows (no header - icons and labels are self-evident)
        self.health_row = HealthTableRow("Health", "health_icon", "stats", show_indicator=True)
        self.uptime_row = HealthTableRow("Uptime", "uptime_icon", "stats")
        self.connections_row = HealthTableRow("Connections", "connections_icon", "")
        self.queue_row = HealthTableRow("Queue Util", "queue_icon", "stats", show_meter=True)
        self.errors_row = HealthTableRow("Total Errors", "total_errors_icon", "stats")
        self.error_rate_row = HealthTableRow("Error Rate", "error_rate_icon", "stats")

        health_layout.addWidget(self.health_row)
        health_layout.addWidget(self.uptime_row)
        health_layout.addWidget(self.connections_row)
        health_layout.addWidget(self.queue_row)
        health_layout.addWidget(self.errors_row)
        health_layout.addWidget(self.error_rate_row)

        outer_layout.addWidget(health_content)
        return group

    def update_display(self, status: Dict[str, Any],
                       incoming_port: str,
                       outgoing_port1: str,
                       outgoing_port2: str):
        """
        Update all stats displays with current router status.

        Args:
            status: Router status dictionary from router_core.get_status()
            incoming_port: Currently selected incoming port (e.g., "COM1", "COM3")
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
        """Update system status section with new table row structure."""
        critical_metrics = status.get("critical_metrics", {})
        system_health = status.get("system_health", {})

        # 1. HEALTH STATUS - with color indicator
        health_status = system_health.get("overall_health_status", "UNKNOWN")
        self.health_row.update_value(HealthTableRow.format_status(health_status))
        self.health_row.update_indicator(health_status)

        # 2. UPTIME - formatted time display
        uptime_hours = critical_metrics.get("system_uptime_hours", 0)
        uptime_text = self._format_uptime(uptime_hours)
        self.uptime_row.update_value(uptime_text)

        # 3. ACTIVE CONNECTIONS - combined ports/threads metric
        active_threads = status.get("active_threads", 0)
        port_connections = status.get("port_connections", {})
        connected_ports = 0
        total_ports = 0

        if port_connections:
            connected_ports = sum(1 for p in port_connections.values() if p.get("connected", False))
            total_ports = len(port_connections)

        # Format: "3/3 Active (3 ports)"
        connections_text = f"{active_threads}/3 Active"
        if total_ports > 0:
            connections_text += f" ({connected_ports}/{total_ports} ports)"

        self.connections_row.update_value(connections_text)

        # 4. QUEUE UTILIZATION - percentage with meter
        queue_util = critical_metrics.get("avg_queue_utilization_percent", 0)
        self.queue_row.update_value(f"{queue_util:.1f}%")

        # Calculate meter percentage (0-100 scale)
        queue_percentage = self.meter_tracker_queue.update(queue_util)
        self.queue_row.update_meter(queue_percentage)

        # 5. TOTAL ERRORS - combined error count
        error_data = status.get("error_counts", {})
        router_errors = 0
        for key, value in error_data.items():
            if isinstance(value, int):
                router_errors += value

        port_errors = system_health.get("total_port_errors", 0)
        total_errors = router_errors + port_errors
        self.errors_row.update_value(str(total_errors))

        # 6. ERROR RATE - errors per minute
        error_rate = self._calculate_error_rate(total_errors)
        self.error_rate_row.update_value(f"{error_rate:.1f}/min")

    def _format_uptime(self, uptime_hours: float) -> str:
        """
        Format uptime hours into human-readable string.

        Args:
            uptime_hours: Uptime in hours

        Returns:
            Formatted string (e.g., "34m", "2h 34m", "1.2 days")
        """
        if uptime_hours < 1:
            uptime_minutes = int(uptime_hours * 60)
            return f"{uptime_minutes}m"
        elif uptime_hours < 24:
            hours = int(uptime_hours)
            minutes = int((uptime_hours - hours) * 60)
            return f"{hours}h {minutes}m"
        else:
            uptime_days = uptime_hours / 24
            return f"{uptime_days:.1f} days"

    def _calculate_error_rate(self, current_error_count: int) -> float:
        """
        Calculate error rate (errors per minute) using rolling window.

        Args:
            current_error_count: Current total error count

        Returns:
            Errors per minute (float)
        """
        import time
        current_time = time.time()

        # If error count increased, record the change
        if current_error_count > self._last_error_count:
            errors_added = current_error_count - self._last_error_count
            self._error_history.append((current_time, errors_added))
            self._last_error_count = current_error_count

        # Clean up old entries (keep only last 60 seconds)
        self._error_history = [
            (t, count) for t, count in self._error_history
            if current_time - t <= 60
        ]

        # Calculate errors per minute
        if not self._error_history:
            return 0.0

        total_errors_in_window = sum(count for _, count in self._error_history)
        return total_errors_in_window  # Already per minute since window is 60s

    def reset_display(self):
        """Reset all displays to zero/offline state."""
        # Reset data transfer table rows
        if self.incoming_row:
            self.incoming_row.update_data(0, 0, 0)
        if self.port1_row:
            self.port1_row.update_data(0, 0, 0)
        if self.port2_row:
            self.port2_row.update_data(0, 0, 0)

        # Reset system status table rows
        if self.health_row:
            self.health_row.update_value(HealthTableRow.format_status("OFFLINE"))
            self.health_row.update_indicator("OFFLINE")
        if self.uptime_row:
            self.uptime_row.update_value("0m")
        if self.connections_row:
            self.connections_row.update_value("0/3 Active")
        if self.queue_row:
            self.queue_row.update_value("0.0%")
            self.queue_row.update_meter(0)
        if self.errors_row:
            self.errors_row.update_value("0")
        if self.error_rate_row:
            self.error_rate_row.update_value("0.0/min")

        # Reset metric trackers
        self.meter_tracker_incoming = MetricMeter()
        self.meter_tracker_port1 = MetricMeter()
        self.meter_tracker_port2 = MetricMeter()
        self.meter_tracker_queue = MetricMeter(min_scale=1, max_scale=100)

        # Reset error tracking
        self._error_history = []
        self._last_error_count = 0
