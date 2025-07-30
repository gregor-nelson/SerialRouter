"""
Enhanced Status Widget for SerialRouter
Provides a clean, visual status indicator following Windows design principles.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QEvent
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont, QColor, QPalette


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
        
        # Initialize colors using Qt palette roles
        self._init_colors()
        
        # Font properties will be set dynamically in paint method
        
    def _init_colors(self):
        """Initialize colors using proper Qt palette roles for theme compatibility."""
        palette = self.palette()
        
        # Use semantic color roles that adapt to light/dark themes
        self.colors = {
            'offline': palette.color(QPalette.ColorRole.PlaceholderText),
            'starting': palette.color(QPalette.ColorRole.Link),
            'active': self._get_success_color(palette),
            'stopping': palette.color(QPalette.ColorRole.Link),
            'error': self._get_error_color(palette),
            'background': palette.color(QPalette.ColorRole.Window),
            'text': palette.color(QPalette.ColorRole.WindowText),
            'border': palette.color(QPalette.ColorRole.Mid)
        }
        
    def _get_success_color(self, palette):
        """Get success color that works in both light and dark themes."""
        # Use Link color as base and adjust for success (green tone)
        link_color = palette.color(QPalette.ColorRole.Link)
        # Create a green-tinted version while maintaining theme compatibility
        success_color = QColor(link_color)
        # Adjust hue towards green while keeping saturation and lightness theme-appropriate
        h, s, l, a = success_color.getHsl()
        success_color.setHsl(120, max(s, 100), l, a)  # Green hue with theme-appropriate saturation/lightness
        return success_color
        
    def _get_error_color(self, palette):
        """Get error color that works in both light and dark themes."""
        # Use system's text color and tint towards red while maintaining readability
        text_color = palette.color(QPalette.ColorRole.WindowText)
        error_color = QColor(text_color)
        # Create red-tinted version
        h, s, l, a = error_color.getHsl()
        # Use red hue but keep theme-appropriate lightness
        error_color.setHsl(0, min(s + 50, 255), l, a)
        return error_color
        
    def changeEvent(self, event):
        """Handle palette changes to update colors when theme changes."""
        if event.type() == QEvent.Type.PaletteChange:
            self._init_colors()
            self.update()
        super().changeEvent(event)
        
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
        """Get color for current state with pulse effect using Qt color manipulation."""
        base_color = self.colors[self._current_state]
        
        # Apply pulse effect for transitional states using Qt's color methods
        if self._current_state in [self.STATE_STARTING, self.STATE_STOPPING]:
            # Use Qt's lighter/darker methods instead of alpha for better theme compatibility
            pulse_factor = int(100 + (self._pulse_opacity * 100))  # 100-200 range
            return base_color.lighter(pulse_factor)
        
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
        
        # Draw simple LED-style indicator using theme-aware colors
        painter.setBrush(QBrush(state_color))
        # Use Qt's darker() method for theme-compatible borders
        border_color = state_color.darker(150) if state_color.lightness() > 128 else state_color.lighter(150)
        painter.setPen(QPen(border_color, 2))
        painter.drawEllipse(indicator_x, indicator_y, indicator_size, indicator_size)
        
        # Primary status text - clean, minimal styling to match app design
        painter.setPen(QPen(self.colors['text']))
        # Use standard app font without bold or size increase for clean look
        primary_font = self.font()
        # Optional: slight size adjustment for better readability while maintaining clean look
        if self._current_state in [self.STATE_ERROR, self.STATE_ACTIVE]:
            # Subtle emphasis for important states without being heavy
            primary_font.setWeight(QFont.Weight.Medium)
        painter.setFont(primary_font)
        
        text_x = indicator_x + indicator_size + 8
        # Align text with indicator center
        text_y = indicator_y + (indicator_size // 2)
        primary_text_rect = rect.adjusted(text_x, text_y - rect.center().y(), -10, 0)
        status_text = self.state_texts[self._current_state]
        painter.drawText(primary_text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, status_text)
        
        
        # Add state-specific visual elements
        if self._current_state == self.STATE_ACTIVE:
            self.draw_active_indicator(painter, indicator_x, indicator_y, indicator_size)
        elif self._current_state == self.STATE_ERROR:
            self.draw_error_indicator(painter, indicator_x, indicator_y, indicator_size)
            
    def draw_active_indicator(self, painter, x, y, size):
        """Draw subtle checkmark for active state using theme colors."""
        # Use contrasting color that works in both light and dark themes
        palette = self.palette()
        contrast_color = palette.color(QPalette.ColorRole.Window)
        painter.setPen(QPen(contrast_color, 2))
        
        # Smaller, cleaner checkmark
        check_size = size // 4
        check_x = x + size // 2 - check_size // 2
        check_y = y + size // 2 - check_size // 4
        
        painter.drawLine(check_x, check_y + 1, check_x + check_size//2, check_y + check_size//2 + 1)
        painter.drawLine(check_x + check_size//2, check_y + check_size//2 + 1, check_x + check_size, check_y - check_size//4 + 1)
        
    def draw_error_indicator(self, painter, x, y, size):
        """Draw subtle X for error state using theme colors."""
        # Use contrasting color that works in both light and dark themes
        palette = self.palette()
        contrast_color = palette.color(QPalette.ColorRole.Window)
        painter.setPen(QPen(contrast_color, 2))
        
        # Smaller, cleaner X
        margin = size // 3
        painter.drawLine(x + margin, y + margin, x + size - margin, y + size - margin)
        painter.drawLine(x + size - margin, y + margin, x + margin, y + size - margin)