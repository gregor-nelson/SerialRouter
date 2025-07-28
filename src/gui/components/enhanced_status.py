"""
Enhanced Status Widget for SerialRouter
Provides a clean, visual status indicator following Windows design principles.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont, QColor, QLinearGradient


class EnhancedStatusWidget(QWidget):
    """
    Enhanced status display widget with visual state indicators.
    Follows Windows design principles with clean typography and subtle animations.
    """
    
    # Application states
    STATE_OFFLINE = "offline"
    STATE_STARTING = "starting" 
    STATE_ACTIVE = "active"
    STATE_STOPPING = "stopping"
    STATE_ERROR = "error"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        
        # Current state
        self._current_state = self.STATE_OFFLINE
        self._pulse_opacity = 1.0
        
        # Use default palette colors
        palette = self.palette()
        self.colors = {
            'offline': palette.mid().color(),
            'starting': palette.highlight().color(),
            'active': palette.highlight().color(),
            'stopping': palette.highlight().color(),
            'error': palette.highlight().color(),
            'background': palette.base().color(),
            'text': palette.text().color(),
            'border': palette.mid().color()
        }
        
        # Font properties will be set dynamically in paint method
        
        # Animation for pulsing states
        self.pulse_animation = QPropertyAnimation(self, b"pulse_opacity")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setLoopCount(-1)  # Infinite loop
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # State text mapping with connection info
        self.state_texts = {
            self.STATE_OFFLINE: "Offline",
            self.STATE_STARTING: "Starting Service...",
            self.STATE_ACTIVE: "Routing Active", 
            self.STATE_STOPPING: "Stopping Service...",
            self.STATE_ERROR: "Service Error"
        }
        
        # Connection status
        self.connection_status = "0/2 ports connected"
        
    @pyqtProperty(float)
    def pulse_opacity(self):
        return self._pulse_opacity
        
    @pulse_opacity.setter  
    def pulse_opacity(self, value):
        self._pulse_opacity = value
        self.update()
        
    def set_state(self, state: str):
        """Set the current application state and update visuals."""
        if state not in self.state_texts:
            return
            
        self._current_state = state
        
        # Handle animations based on state
        if state in [self.STATE_STARTING, self.STATE_STOPPING]:
            self.start_pulse_animation()
        else:
            self.stop_pulse_animation()
            
        self.update()
        
    def set_connection_status(self, connected_ports: int, total_ports: int = 2):
        """Update the connection status display."""
        self.connection_status = f"{connected_ports}/{total_ports} ports connected"
        self.update()
        
    def start_pulse_animation(self):
        """Start pulsing animation for transitional states."""
        self.pulse_animation.setStartValue(0.3)
        self.pulse_animation.setEndValue(1.0)
        self.pulse_animation.start()
        
    def stop_pulse_animation(self):
        """Stop pulsing animation."""
        self.pulse_animation.stop()
        self._pulse_opacity = 1.0
        
    def get_state_color(self):
        """Get color for current state with pulse effect."""
        base_color = self.colors[self._current_state]
        
        # Apply pulse opacity for transitional states
        if self._current_state in [self.STATE_STARTING, self.STATE_STOPPING]:
            color = QColor(base_color)
            color.setAlphaF(self._pulse_opacity)
            return color
        
        return base_color
        
    def paintEvent(self, event):
        """Custom paint method with Windows styling."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        rect = self.rect()
        
        # Draw status content
        self.draw_status_indicator(painter, rect)
        
    def draw_status_indicator(self, painter, rect):
        """Draw the main status indicator with clean Windows styling."""
        # Status indicator circle position (LED-style) - moved higher
        indicator_x = rect.left() + 8
        indicator_y = rect.top() + 8
        indicator_size = 20
        
        # Get state color
        state_color = self.get_state_color()
        
        # Draw simple LED-style indicator (solid circle with border)
        painter.setBrush(QBrush(state_color))
        painter.setPen(QPen(state_color.darker(160), 2))
        painter.drawEllipse(indicator_x, indicator_y, indicator_size, indicator_size)
        
        # Primary status text - aligned with indicator (moved higher)
        painter.setPen(QPen(self.colors['text']))
        primary_font = self.font()
        primary_font.setPointSize(primary_font.pointSize() + 1)
        primary_font.setBold(True)
        painter.setFont(primary_font)
        
        text_x = indicator_x + indicator_size + 8
        # Align text with indicator center
        text_y = indicator_y + (indicator_size // 2)
        primary_text_rect = rect.adjusted(text_x, text_y - rect.center().y(), -10, 0)
        status_text = self.state_texts[self._current_state]
        painter.drawText(primary_text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, status_text)
        
        # Secondary connection info - positioned below with more space
        if self._current_state == self.STATE_ACTIVE:
            secondary_font = self.font()
            secondary_font.setPointSize(secondary_font.pointSize() - 1)
            painter.setFont(secondary_font)
            painter.setPen(QPen(self.colors['text'].darker(150)))
            
            # Position secondary text below primary text with more space
            secondary_y = text_y + 14
            secondary_rect = rect.adjusted(text_x, secondary_y - rect.center().y(), -10, 0)
            painter.drawText(secondary_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self.connection_status)
        
        # Add state-specific visual elements
        if self._current_state == self.STATE_ACTIVE:
            self.draw_active_indicator(painter, indicator_x, indicator_y, indicator_size)
        elif self._current_state == self.STATE_ERROR:
            self.draw_error_indicator(painter, indicator_x, indicator_y, indicator_size)
            
    def draw_active_indicator(self, painter, x, y, size):
        """Draw subtle checkmark for active state."""
        painter.setPen(QPen(self.palette().base().color(), 2))
        
        # Smaller, cleaner checkmark
        check_size = size // 4
        check_x = x + size // 2 - check_size // 2
        check_y = y + size // 2 - check_size // 4
        
        painter.drawLine(check_x, check_y + 1, check_x + check_size//2, check_y + check_size//2 + 1)
        painter.drawLine(check_x + check_size//2, check_y + check_size//2 + 1, check_x + check_size, check_y - check_size//4 + 1)
        
    def draw_error_indicator(self, painter, x, y, size):
        """Draw subtle X for error state."""
        painter.setPen(QPen(self.palette().base().color(), 2))
        
        # Smaller, cleaner X
        margin = size // 3
        painter.drawLine(x + margin, y + margin, x + size - margin, y + size - margin)
        painter.drawLine(x + size - margin, y + margin, x + margin, y + size - margin)