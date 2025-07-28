"""
Enhanced Connection Diagram Widget for SerialRouter
Uses QGraphicsView framework for professional visualization with animations and interactive elements.
"""

from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsItem, 
                             QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem,
                             QGraphicsEllipseItem, QGraphicsPathItem)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont, QFontMetrics, QColor, QPainterPath, QLinearGradient


class PortNode(QGraphicsRectItem):
    """Custom graphics item for port nodes with enhanced styling and animations."""
    
    def __init__(self, port_name, node_type="application", parent=None):
        super().__init__(parent)
        self.port_name = port_name
        self.node_type = node_type
        self.is_connected = False
        self.is_hovered = False
        
        # Set node dimensions
        self.node_width = 90
        self.node_height = 32
        self.setRect(0, 0, self.node_width, self.node_height)
        
        # Disable hover and selection
        self.setAcceptHoverEvents(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        
        # Add text label
        self.text_item = QGraphicsTextItem(port_name, self)
        self.text_item.setPos(6, 6)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self.text_item.setFont(font)
        
        # Status indicator (LED-style dot)
        self.status_indicator = QGraphicsEllipseItem(self.node_width - 12, 6, 8, 8, self)
        
        self.update_style()
    
    def set_connected(self, connected):
        """Update connection state with smooth animation."""
        if self.is_connected != connected:
            self.is_connected = connected
            self.update_style()
            self.update()
    
    def update_style(self):
        """Update visual styling based on state."""
        # Get palette from scene view for consistent theming
        from PyQt6.QtWidgets import QApplication
        if self.scene() and self.scene().views():
            palette = self.scene().views()[0].palette()
        else:
            palette = QApplication.instance().palette()
        
        # Use Qt6 Fusion palette colors for consistency
        base_color = palette.color(palette.ColorRole.Base)
        window_color = palette.color(palette.ColorRole.Window)  # Lighter than Base in Fusion
        button_color = palette.color(palette.ColorRole.Button)
        highlight_color = palette.color(palette.ColorRole.Highlight)
        mid_color = palette.color(palette.ColorRole.Mid)
        
        # Keep light background for boxes to stand out in dark mode
        # Use a light grey that works well against dark Fusion theme
        bg_color = QColor(240, 240, 240)  # Light grey background
        
        if self.node_type == "configurable":
            border_color = highlight_color if self.is_connected else mid_color
        elif self.node_type == "router":
            # Router node stays the same regardless of connection state
            border_color = mid_color
        else:  # application
            border_color = highlight_color.darker(120) if self.is_connected else mid_color
        
        # Apply gradient background
        gradient = QLinearGradient(0, 0, 0, self.node_height)
        gradient.setColorAt(0, bg_color.lighter(102))
        gradient.setColorAt(1, bg_color.darker(102))
        self.setBrush(QBrush(gradient))
        
        # Set border
        pen = QPen(border_color, 2 if self.is_connected and self.node_type != "router" else 1)
        self.setPen(pen)
        
        # Update status indicator using palette colors
        status_color = highlight_color if self.is_connected else mid_color
        # Use dark grey text for contrast against light box background
        text_color = QColor(60, 60, 60)  # Dark grey text
            
        self.status_indicator.setBrush(QBrush(status_color))
        self.status_indicator.setPen(QPen(status_color.darker(150), 1))
        self.text_item.setDefaultTextColor(text_color)
    
    def paint(self, painter, option, widget=None):
        """Custom paint with rounded corners and shadow effect."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw shadow using palette colors
        shadow_rect = self.rect().adjusted(2, 2, 2, 2)
        from PyQt6.QtWidgets import QApplication
        if self.scene() and self.scene().views():
            palette = self.scene().views()[0].palette()
        else:
            palette = QApplication.instance().palette()
        
        shadow_color = palette.color(palette.ColorRole.Shadow)
        shadow_color.setAlpha(30)
            
        painter.setBrush(QBrush(shadow_color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(shadow_rect, 4, 4)
        
        # Draw main rectangle with rounded corners
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(self.rect(), 4, 4)
    


class ConnectionLine(QGraphicsPathItem):
    """Custom graphics item for connection lines with flow animation."""
    
    def __init__(self, start_node, end_node, parent=None):
        super().__init__(parent)
        self.start_node = start_node
        self.end_node = end_node
        self.is_active = False
        self.flow_offset = 0
        
        # Timer for simple flow animation
        self.flow_timer = QTimer()
        self.flow_timer.timeout.connect(self.update_flow)
        self.flow_timer.setInterval(50)  # 50ms = 20 FPS
        
        self.update_path()
        self.update_style()
    
    
    def update_flow(self):
        """Update flow animation offset."""
        self.flow_offset = (self.flow_offset + 1) % 20
        self.update()
    
    def set_active(self, active):
        """Set connection active state with animation."""
        if self.is_active != active:
            self.is_active = active
            if active:
                self.flow_timer.start()
            else:
                self.flow_timer.stop()
                self.flow_offset = 0
            self.update_style()
            self.update()  # Force repaint to clear dots immediately
    
    def update_path(self):
        """Update connection path between nodes with 90-degree angles."""
        start_rect = self.start_node.sceneBoundingRect()
        end_rect = self.end_node.sceneBoundingRect()
        
        # Calculate connection points
        start_point = QPointF(start_rect.center().x(), start_rect.bottom())
        end_point = QPointF(end_rect.center().x(), end_rect.top())
        
        # Create angular path with 90-degree turns
        path = QPainterPath(start_point)
        
        # Check if this is a direct vertical connection (like incoming to router)
        if abs(start_point.x() - end_point.x()) < 5:  # Nearly aligned vertically
            # Direct vertical line
            path.lineTo(end_point)
        else:
            # Angular path with 90-degree turns
            # Go down from start point
            mid_y = start_point.y() + (end_point.y() - start_point.y()) * 0.5
            
            # First segment: straight down
            path.lineTo(QPointF(start_point.x(), mid_y))
            
            # Second segment: horizontal to target x
            path.lineTo(QPointF(end_point.x(), mid_y))
            
            # Third segment: straight up to target
            path.lineTo(end_point)
        
        self.setPath(path)
    
    def update_style(self):
        """Update line styling based on active state."""
        # Use Qt6 palette color for consistent styling with Fusion theme
        from PyQt6.QtWidgets import QApplication
        if self.scene() and self.scene().views():
            palette = self.scene().views()[0].palette()
        else:
            palette = QApplication.instance().palette()
        color = palette.color(palette.ColorRole.Highlight)
        width = 3
        
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
    
    def paint(self, painter, option, widget=None):
        """Custom paint with flow animation."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw main path
        painter.setPen(self.pen())
        painter.drawPath(self.path())
        
        # Draw animated flow indicators if active
        if self.is_active and self.flow_timer.isActive():
            self.draw_flow_indicators(painter)
        
        # Draw arrow at end
        self.draw_arrow(painter)
    
    def draw_flow_indicators(self, painter):
        """Draw animated flow indicators along the path."""
        path_length = self.path().length()
        if path_length <= 0:
            return
        
        # Draw multiple flow dots
        dot_spacing = 20
        dot_size = 2  # Reduced from 4 to 2
        
        for i in range(0, int(path_length), dot_spacing):
            percent = (i + self.flow_offset) / path_length
            if percent > 1.0:
                percent -= 1.0
            
            point = self.path().pointAtPercent(percent)
            
            # Draw glowing dot using palette colors
            from PyQt6.QtWidgets import QApplication
            if self.scene() and self.scene().views():
                palette = self.scene().views()[0].palette()
            else:
                palette = QApplication.instance().palette()
            
            dot_color = palette.color(palette.ColorRole.BrightText)
            dot_color.setAlpha(200)
                
            painter.setBrush(QBrush(dot_color))
            painter.setPen(QPen(self.pen().color(), 1))
            painter.drawEllipse(point, dot_size, dot_size)
    
    def draw_arrow(self, painter):
        """Draw directional arrow at the end of the path."""
        path_length = self.path().length()
        if path_length <= 0:
            return
        
        # Get point and angle near the end
        end_point = self.path().pointAtPercent(1.0)
        prev_point = self.path().pointAtPercent(0.95)
        
        # Calculate arrow direction
        dx = end_point.x() - prev_point.x()
        dy = end_point.y() - prev_point.y()
        length = (dx*dx + dy*dy)**0.5
        
        if length > 0:
            # Normalize direction
            dx /= length
            dy /= length
            
            # Arrow size
            arrow_size = 8
            
            # Calculate arrow points
            arrow_tip = end_point
            arrow_left = QPointF(
                end_point.x() - arrow_size * dx + arrow_size * 0.5 * dy,
                end_point.y() - arrow_size * dy - arrow_size * 0.5 * dx
            )
            arrow_right = QPointF(
                end_point.x() - arrow_size * dx - arrow_size * 0.5 * dy,
                end_point.y() - arrow_size * dy + arrow_size * 0.5 * dx
            )
            
            # Draw arrow
            arrow_path = QPainterPath(arrow_tip)
            arrow_path.lineTo(arrow_left)
            arrow_path.lineTo(arrow_right)
            arrow_path.closeSubpath()
            
            painter.setBrush(QBrush(self.pen().color()))
            painter.setPen(QPen(self.pen().color(), 1))
            painter.drawPath(arrow_path)
    
    


class ConnectionDiagramWidget(QGraphicsView):
    """
    Enhanced connection diagram using QGraphicsView for professional visualization.
    Features smooth animations, hover effects, and interactive elements.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create graphics scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Configure view
        self.setMinimumHeight(200)
        self.setMaximumHeight(220)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Port configuration
        self.incoming_port = "COM54"
        self.internal_ports = ["COM131", "COM141"]
        self.external_ports = ["COM132", "COM142"]
        
        # Graphics items
        self.nodes = {}
        self.connections = {}
        
        # Connection state tracking
        self.connection_states = {
            "COM131": False,
            "COM141": False
        }
        
        self.setup_diagram()
    
    def setup_diagram(self):
        """Initialize the graphics scene with nodes and connections."""
        self.scene.clear()
        self.nodes.clear()
        self.connections.clear()
        
        # Scene dimensions
        scene_width = 300
        scene_height = 180
        self.scene.setSceneRect(0, 0, scene_width, scene_height)
        
        # Node positions
        center_x = scene_width // 2
        
        # Incoming port (top)
        incoming_node = PortNode(self.incoming_port, "configurable")
        incoming_node.setPos(center_x - 45, 20)
        self.scene.addItem(incoming_node)
        self.nodes["incoming"] = incoming_node
        
        # Router (middle)
        router_node = PortNode("Router", "router")
        router_node.setPos(center_x - 45, 75)
        self.scene.addItem(router_node)
        self.nodes["router"] = router_node
        
        # Application ports (bottom)
        app1_node = PortNode(self.external_ports[0], "application")
        app1_node.setPos(center_x - 120, 130)
        self.scene.addItem(app1_node)
        self.nodes["app1"] = app1_node
        
        app2_node = PortNode(self.external_ports[1], "application")
        app2_node.setPos(center_x + 30, 130)
        self.scene.addItem(app2_node)
        self.nodes["app2"] = app2_node
        
        # Create connections
        # Incoming to Router
        main_connection = ConnectionLine(incoming_node, router_node)
        self.scene.addItem(main_connection)
        self.connections["main"] = main_connection
        
        # Router to App1
        app1_connection = ConnectionLine(router_node, app1_node)
        self.scene.addItem(app1_connection)
        self.connections["app1"] = app1_connection
        
        # Router to App2
        app2_connection = ConnectionLine(router_node, app2_node)
        self.scene.addItem(app2_connection)
        self.connections["app2"] = app2_connection
        
        # Update initial states
        self.update_connection_states()
    
    def set_connection_states(self, states: dict):
        """Update connection states with smooth animations."""
        self.connection_states.update(states)
        self.update_connection_states()
    
    def update_connection_states(self):
        """Update visual states of all nodes and connections."""
        # Update router state (active if any connection is active)
        any_connected = any(self.connection_states.values())
        if "router" in self.nodes:
            self.nodes["router"].set_connected(any_connected)
        
        # Update main connection (active if any output is active)
        if "main" in self.connections:
            self.connections["main"].set_active(any_connected)
        
        # Update individual connections
        app1_connected = self.connection_states.get("COM131", False)
        if "app1" in self.connections:
            self.connections["app1"].set_active(app1_connected)
        
        app2_connected = self.connection_states.get("COM141", False)
        if "app2" in self.connections:
            self.connections["app2"].set_active(app2_connected)
    
    def set_port_configuration(self, external_ports: list, internal_ports: list, incoming_port: str = None):
        """Update port configuration and rebuild diagram."""
        self.external_ports = external_ports
        self.internal_ports = internal_ports
        if incoming_port:
            self.incoming_port = incoming_port
        self.setup_diagram()
    
    def set_incoming_port(self, port_name: str):
        """Update the incoming port name and refresh display."""
        self.incoming_port = port_name
        if "incoming" in self.nodes:
            self.nodes["incoming"].port_name = port_name
            self.nodes["incoming"].text_item.setPlainText(port_name)
    
    def resizeEvent(self, event):
        """Handle resize events to fit scene to view."""
        super().resizeEvent(event)
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def paintEvent(self, event):
        """Custom paint event for background styling."""
        # Draw custom background
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Use same background as console log (QTextEdit default background)
        # This matches the Fusion theme's QTextEdit background color
        background_color = self.palette().color(self.palette().ColorRole.Base)
        painter.fillRect(self.viewport().rect(), QBrush(background_color))
        
        # Draw border
        border_pen = QPen(self.palette().mid().color(), 1)
        painter.setPen(border_pen)
        painter.drawRect(self.viewport().rect().adjusted(0, 0, -1, -1))
        
        # Call parent paint event to draw the scene
        super().paintEvent(event)