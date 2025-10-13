"""
Enhanced Status Widget for SerialRouter
Provides a clean, visual status indicator following Windows design principles.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QEvent
from PyQt6.QtGui import QColor, QPalette
from src.gui.resources import resource_manager


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

        # Create UI layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(8)

        # Status icon label
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        layout.addWidget(self.icon_label)

        # Status text label
        self.text_label = QLabel()
        layout.addWidget(self.text_label)
        layout.addStretch()

        # Initialize colors using Qt palette roles
        self._init_colors()

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

        # Update initial display
        self.update_display()
        
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
            self.update_display()
        super().changeEvent(event)
        
        
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

        # Update display with new state
        self.update_display()
        
        
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
        
    def update_display(self):
        """Update the icon and text display based on current state."""
        # Map states to icon filenames
        icon_map = {
            self.STATE_OFFLINE: "status_offline.svg",
            self.STATE_STARTING: "status_starting.svg",
            self.STATE_ACTIVE: "status_active.svg",
            self.STATE_STOPPING: "status_stopping.svg",
            self.STATE_ERROR: "status_error.svg"
        }

        # Load and display the SVG icon
        icon_filename = icon_map.get(self._current_state, "status_offline.svg")
        icon = resource_manager.load_icon(icon_filename, "toolbar")

        if not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(20, 20))

        # Update text with optional emphasis for important states
        status_text = self.state_texts[self._current_state]
        if self._current_state in [self.STATE_ERROR, self.STATE_ACTIVE]:
            # Subtle emphasis for important states
            self.text_label.setText(f"<span style='font-weight: 500;'>{status_text}</span>")
        else:
            self.text_label.setText(status_text)