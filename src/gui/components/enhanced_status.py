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
        
        # Windows theme colors
        self.colors = {
            'offline': QColor('#d9d9d9'),      # Gray
            'starting': QColor('#ff8c00'),     # Orange  
            'active': QColor('#107c10'),       # Green
            'stopping': QColor('#ff8c00'),     # Orange
            'error': QColor('#d13438'),        # Red
            'background': QColor('#ffffff'),
            'text': QColor('#333333'),
            'border': QColor('#d9d9d9')
        }
        
        # Font properties will be set dynamically in paint method
        
        # Animation for pulsing states
        self.pulse_animation = QPropertyAnimation(self, b"pulse_opacity")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setLoopCount(-1)  # Infinite loop
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # State text mapping
        self.state_texts = {
            self.STATE_OFFLINE: "Offline",
            self.STATE_STARTING: "Starting Service...",
            self.STATE_ACTIVE: "Routing Active", 
            self.STATE_STOPPING: "Stopping Service...",
            self.STATE_ERROR: "Service Error"
        }
        
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
        
        # Draw background
        painter.fillRect(rect, self.colors['background'])
        
        # Draw border (consistent with GroupBox styling)
        border_pen = QPen(self.colors['border'], 1)
        painter.setPen(border_pen)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        
        # Draw status content
        self.draw_status_indicator(painter, rect)
        
    def draw_status_indicator(self, painter, rect):
        """Draw the main status indicator with clean Windows styling."""
        # Status indicator circle position
        indicator_x = rect.left() + 15
        indicator_y = rect.center().y() - 8
        indicator_size = 16
        
        # Get state color
        state_color = self.get_state_color()
        
        # Draw status circle with subtle gradient
        gradient = QLinearGradient(0, indicator_y, 0, indicator_y + indicator_size)
        gradient.setColorAt(0.0, state_color.lighter(120))
        gradient.setColorAt(1.0, state_color)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(state_color.darker(150), 1))
        painter.drawEllipse(indicator_x, indicator_y, indicator_size, indicator_size)
        
        # Draw status text with theme font
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QPen(self.colors['text']))
        
        text_rect = rect.adjusted(indicator_x + indicator_size + 12, 0, -10, 0)
        status_text = self.state_texts[self._current_state]
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, status_text)
        
        # Add state-specific visual elements
        if self._current_state == self.STATE_ACTIVE:
            self.draw_active_indicator(painter, indicator_x, indicator_y, indicator_size)
        elif self._current_state == self.STATE_ERROR:
            self.draw_error_indicator(painter, indicator_x, indicator_y, indicator_size)
            
    def draw_active_indicator(self, painter, x, y, size):
        """Draw checkmark for active state."""
        painter.setPen(QPen(QColor('#ffffff'), 2))
        
        # Simple checkmark
        check_size = size // 3
        check_x = x + size // 2 - check_size // 2
        check_y = y + size // 2 - check_size // 4
        
        painter.drawLine(check_x, check_y, check_x + check_size//2, check_y + check_size//2)
        painter.drawLine(check_x + check_size//2, check_y + check_size//2, check_x + check_size, check_y - check_size//4)
        
    def draw_error_indicator(self, painter, x, y, size):
        """Draw X for error state."""
        painter.setPen(QPen(QColor('#ffffff'), 2))
        
        # Simple X
        margin = size // 4
        painter.drawLine(x + margin, y + margin, x + size - margin, y + size - margin)
        painter.drawLine(x + size - margin, y + margin, x + margin, y + size - margin)