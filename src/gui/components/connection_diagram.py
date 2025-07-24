"""
Connection Diagram Widget for SerialRouter
Displays the virtual COM port pairing relationships in a clean Windows-style design.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont, QFontMetrics, QColor


class ConnectionDiagramWidget(QWidget):
    """
    Custom widget that displays serial routing architecture using Top-Down Hub Model.
    Shows the flow from hardware input through router to application connection points.
    Designed for marine surveyors - clear technical visualization without oversimplification.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setMaximumHeight(220)
        
        # Port configuration for Top-Down Hub Model
        self.incoming_port = "COM54"  # Hardware input (configurable)
        self.internal_ports = ["COM131", "COM141"]  # Router uses these (fixed)
        self.external_ports = ["COM132", "COM142"]  # Applications connect here
        
        # Connection state tracking
        self.connection_states = {
            "COM131": False,  # Connected/Active state
            "COM141": False
        }
        
        # Colors from theme - no dictionary needed
        
        # Font properties will be set dynamically in paint methods
        
    def set_connection_states(self, states: dict):
        """Update connection states and trigger repaint."""
        self.connection_states.update(states)
        self.update()
        
    def set_port_configuration(self, external_ports: list, internal_ports: list, incoming_port: str = None):
        """Update port configuration for dynamic setups."""
        self.external_ports = external_ports
        self.internal_ports = internal_ports
        if incoming_port:
            self.incoming_port = incoming_port
        self.update()
        
    def set_incoming_port(self, port_name: str):
        """Update the incoming port name and refresh display."""
        self.incoming_port = port_name
        self.update()
        
    def paintEvent(self, event):
        """Main paint method following Windows design principles."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Get widget dimensions
        rect = self.rect()
        
        # Draw background
        painter.fillRect(rect, QColor('#ffffff'))
        
        # Draw border (consistent with GroupBox styling)
        border_pen = QPen(QColor('#d9d9d9'), 1)
        painter.setPen(border_pen)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        
        # Draw content (title removed - GroupBox already has title)
        self.draw_connection_diagram(painter, rect)
        self.draw_labels(painter, rect)
        
    def draw_connection_diagram(self, painter, rect):
        """Draw simplified vertical connection diagram for narrow panel."""
        # Use theme-consistent margins (12px like form controls)
        center_x = rect.center().x()
        margin = 12  # Match QLineEdit/button padding
        
        # Optimized vertical layout using theme spacing
        # Configurable Port (Top)
        config_y = rect.top() + 12  # 12px like QGroupBox margin-top
        
        # Router Section (Middle) - increased gap for longer arrow
        router_y = config_y + 55  # Increased from 42 to 55 for longer vertical arrow
        
        # Application Ports (Bottom, side by side)
        app_y = router_y + 55  # Match incoming-to-router gap for consistent arrow lengths
        
        # Node width using theme button sizing (min-width: 70px, padding: 6px 12px)
        min_node_width = 70  # Match ribbon-button min-width
        max_node_width = 90  # Match ribbon-button max-width  
        available_width = rect.width() - 24  # Account for 12px margins both sides
        calculated_width = available_width // 2  # Space for 2 nodes side by side
        node_width = max(min_node_width, min(max_node_width, calculated_width))
        
        # Draw components - simplified 3-tier layout
        # Configurable incoming port (top tier)
        self.draw_simple_node(painter, center_x - node_width//2, config_y,
                             self.incoming_port, node_width, 24, "configurable")  # 24px like TreeWidget item height
        
        # Router (centered, using button sizing)
        router_width = min(90, rect.width() - 24)  # Max button width, theme margins
        any_connected = any(self.connection_states.get(port, False) for port in self.internal_ports)
        self.draw_simple_node(painter, center_x - router_width//2, router_y,
                             "Router", router_width, 28, "router", any_connected)  # Slightly larger for central component
        
        # Application ports (side by side) - Theme spacing
        gap = 16  # Match typical widget spacing in theme
        left_x = center_x - node_width - gap//2
        right_x = center_x + gap//2
        
        self.draw_simple_node(painter, left_x, app_y,
                             self.external_ports[0], node_width, 24, "application")  # Match TreeWidget height
        self.draw_simple_node(painter, right_x, app_y,
                             self.external_ports[1], node_width, 24, "application")  # Match TreeWidget height
        
        # Draw simple connections for 3-tier layout
        self.draw_simple_connections(painter, center_x, config_y, router_y, app_y,
                                   left_x + node_width//2, right_x + node_width//2, node_width)
    
    def draw_simple_node(self, painter, x, y, text, width, height, node_type="application", is_connected=False):
        """Draw nodes matching exact toolbar button styling."""
        node_rect = QRect(x, y, width, height)
        
        # Standard app colors - clean and consistent
        if node_type == "configurable":
            # Blue background for the configurable port with QGroupBox border
            bg_color = QColor('#e5f3ff')
            border_color = QColor('#d9d9d9')  # QGroupBox border color
        elif node_type == "router":
            # Router uses white background with QGroupBox border
            bg_color = QColor('#ffffff')
            border_color = QColor('#d9d9d9')  # QGroupBox border color
        else:  # application
            # Application ports use white background with QGroupBox border
            bg_color = QColor('#ffffff')
            border_color = QColor('#d9d9d9')  # QGroupBox border color 

        # Draw rectangle matching QGroupBox theme (2px border like sections)
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 2))  # 2px like QGroupBox border
        painter.drawRoundedRect(node_rect, 0, 0)  # 0px radius like theme
        
        # Draw text with theme font styling
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QPen(QColor('#333333')))
        painter.drawText(node_rect, Qt.AlignmentFlag.AlignCenter, text)
        
    def draw_connection_line(self, painter, start_point, end_point, is_connected=False):
        """Draw connection line with directional indicators."""
        # Line color with blue accent when inactive, green when active
        if is_connected:
            line_color = QColor('#107c10')  # Success green when active
            line_width = 2
        else:
            line_color = QColor('#0078d4')  # Blue accent when inactive
            line_width = 1
            
        painter.setPen(QPen(line_color, line_width))
        
        # Draw main connection line
        painter.drawLine(start_point, end_point)
        
        # Draw directional arrow in center
        mid_point = QPoint(
            (start_point.x() + end_point.x()) // 2,
            (start_point.y() + end_point.y()) // 2
        )
        
        # Simple arrow pointing right
        arrow_size = 4
        arrow_points = [
            QPoint(mid_point.x() - arrow_size, mid_point.y() - arrow_size//2),
            QPoint(mid_point.x() + arrow_size, mid_point.y()),
            QPoint(mid_point.x() - arrow_size, mid_point.y() + arrow_size//2)
        ]
        
        painter.setBrush(QBrush(line_color))
        painter.drawPolygon(arrow_points)
    
    def draw_simple_connections(self, painter, center_x, config_y, router_y, app_y,
                              left_app_x, right_app_x, node_width):
        """Draw clean vertical connections for narrow panel."""
        
        any_connected = any(self.connection_states.get(port, False) for port in self.internal_ports)
        
        # Vertical flow lines for 3-tier layout
        # Config to Router (main connection always shows incoming data flow)
        start = QPoint(center_x, config_y + 25)
        end = QPoint(center_x, router_y)
        self.draw_simple_arrow(painter, start, end, any_connected)
        
        # Router to Apps (split) - using 90-degree L-shaped connections
        router_center = QPoint(center_x, router_y + 30)
        
        # Left app connection
        app1_connected = self.connection_states.get(self.internal_ports[0], False)
        left_end = QPoint(left_app_x, app_y)
        self.draw_l_shaped_connection(painter, router_center, left_end, app1_connected)
        
        # Right app connection  
        app2_connected = self.connection_states.get(self.internal_ports[1], False)
        right_end = QPoint(right_app_x, app_y)
        self.draw_l_shaped_connection(painter, router_center, right_end, app2_connected)
    
    def draw_vertical_line(self, painter, start_point, end_point, is_active=False, is_bidirectional=False):
        """Draw vertical connection line with appropriate styling."""
        if is_active:
            line_color = QColor('#107c10')  # Success green when active
            line_width = 2
        else:
            line_color = QColor('#0078d4')  # Blue accent when inactive
            line_width = 1
            
        painter.setPen(QPen(line_color, line_width))
        painter.drawLine(start_point, end_point)
        
        # Add bidirectional arrows if specified
        if is_bidirectional:
            self.draw_bidirectional_arrows(painter, start_point, end_point, line_color)
        else:
            # Single arrow pointing down
            self.draw_single_arrow(painter, start_point, end_point, line_color)
    
    def draw_angled_line(self, painter, start_point, end_point, is_active=False):
        """Draw angled connection line from hub to internal ports."""
        if is_active:
            line_color = QColor('#107c10')  # Success green when active
            line_width = 2
        else:
            line_color = QColor('#0078d4')  # Blue accent when inactive
            line_width = 1
            
        painter.setPen(QPen(line_color, line_width))
        painter.drawLine(start_point, end_point)
        
        # Add arrow at end point
        self.draw_single_arrow(painter, start_point, end_point, line_color)
    
    def draw_single_arrow(self, painter, start_point, end_point, color):
        """Draw single directional arrow."""
        # Calculate arrow position (75% along the line)
        arrow_x = start_point.x() + int(0.75 * (end_point.x() - start_point.x()))
        arrow_y = start_point.y() + int(0.75 * (end_point.y() - start_point.y()))
        arrow_point = QPoint(arrow_x, arrow_y)
        
        # Arrow pointing towards end_point
        if end_point.y() > start_point.y():  # Pointing down
            arrow_points = [
                QPoint(arrow_point.x() - 3, arrow_point.y() - 3),
                QPoint(arrow_point.x() + 3, arrow_point.y() - 3),
                QPoint(arrow_point.x(), arrow_point.y() + 3)
            ]
        else:  # Pointing up
            arrow_points = [
                QPoint(arrow_point.x() - 3, arrow_point.y() + 3),
                QPoint(arrow_point.x() + 3, arrow_point.y() + 3),
                QPoint(arrow_point.x(), arrow_point.y() - 3)
            ]
        
        painter.setBrush(QBrush(color))
        painter.drawPolygon(arrow_points)
    
    def draw_bidirectional_arrows(self, painter, start_point, end_point, color):
        """Draw bidirectional arrows for virtual pairing connections."""
        # Up arrow (25% along line)
        up_arrow_y = start_point.y() + int(0.25 * (end_point.y() - start_point.y()))
        up_arrow_point = QPoint(start_point.x(), up_arrow_y)
        up_arrow_points = [
            QPoint(up_arrow_point.x() - 3, up_arrow_point.y() + 3),
            QPoint(up_arrow_point.x() + 3, up_arrow_point.y() + 3),
            QPoint(up_arrow_point.x(), up_arrow_point.y() - 3)
        ]
        
        # Down arrow (75% along line)
        down_arrow_y = start_point.y() + int(0.75 * (end_point.y() - start_point.y()))
        down_arrow_point = QPoint(start_point.x(), down_arrow_y)
        down_arrow_points = [
            QPoint(down_arrow_point.x() - 3, down_arrow_point.y() - 3),
            QPoint(down_arrow_point.x() + 3, down_arrow_point.y() - 3),
            QPoint(down_arrow_point.x(), down_arrow_point.y() + 3)
        ]
        
        painter.setBrush(QBrush(color))
        painter.drawPolygon(up_arrow_points)
        painter.drawPolygon(down_arrow_points)
    
    def draw_flow_arrow(self, painter, start_point, end_point, is_active=False):
        """Draw clean horizontal flow arrows for linear diagram."""
        # Line styling based on active state
        if is_active:
            line_color = QColor('#107c10')  # Success green when active
            line_width = 3
        else:
            line_color = QColor('#0078d4')  # Blue accent when inactive
            line_width = 2
            
        painter.setPen(QPen(line_color, line_width))
        painter.drawLine(start_point, end_point)
        
        # Draw arrow head at end point
        arrow_size = 6
        arrow_tip = end_point
        arrow_base_x = arrow_tip.x() - arrow_size
        
        arrow_points = [
            QPoint(arrow_base_x, arrow_tip.y() - arrow_size//2),
            QPoint(arrow_base_x, arrow_tip.y() + arrow_size//2),
            QPoint(arrow_tip.x(), arrow_tip.y())
        ]
        
        painter.setBrush(QBrush(line_color))
        painter.setPen(QPen(line_color, 1))
        painter.drawPolygon(arrow_points)
    
    def draw_bidirectional_indicator(self, painter, position):
        """Draw small bidirectional indicator for virtual pairing."""
        indicator_color = QColor('#107c10')
        painter.setPen(QPen(indicator_color, 1))
        painter.setBrush(QBrush(indicator_color))
        
        # Small double arrow symbol
        size = 3
        # Left arrow
        left_points = [
            QPoint(position.x() - size, position.y()),
            QPoint(position.x(), position.y() - size//2),
            QPoint(position.x(), position.y() + size//2)
        ]
        # Right arrow  
        right_points = [
            QPoint(position.x() + size, position.y()),
            QPoint(position.x(), position.y() - size//2),
            QPoint(position.x(), position.y() + size//2)
        ]
        
        painter.drawPolygon(left_points)
        painter.drawPolygon(right_points)
    
    def draw_simple_arrow(self, painter, start_point, end_point, is_active):
        """Draw bidirectional arrows to show two-way data flow."""
        if is_active:
            color = QColor('#107c10')  # Success green when active
            width = 2
        else:
            color = QColor('#0078d4')  # Blue accent when inactive
            width = 1
            
        painter.setPen(QPen(color, width))
        painter.drawLine(start_point, end_point)
        
        # Bidirectional arrows - one pointing up, one pointing down
        painter.setBrush(QBrush(color))
        
        # Upper arrow (pointing up toward start_point)
        upper_arrow_y = start_point.y() + 8
        upper_arrow_points = [
            QPoint(start_point.x() - 3, upper_arrow_y),
            QPoint(start_point.x() + 3, upper_arrow_y),
            QPoint(start_point.x(), start_point.y() + 4)
        ]
        painter.drawPolygon(upper_arrow_points)
        
        # Lower arrow (pointing down toward end_point)
        lower_arrow_y = end_point.y() - 4
        lower_arrow_points = [
            QPoint(end_point.x() - 3, lower_arrow_y),
            QPoint(end_point.x() + 3, lower_arrow_y),
            QPoint(end_point.x(), end_point.y())
        ]
        painter.drawPolygon(lower_arrow_points)
    
    def draw_angled_simple_line(self, painter, start_point, end_point, is_active):
        """Draw bidirectional angled line for router splits."""
        if is_active:
            color = QColor('#107c10')  # Success green when active
            width = 2
        else:
            color = QColor('#0078d4')  # Blue accent when inactive
            width = 1
            
        painter.setPen(QPen(color, width))
        painter.drawLine(start_point, end_point)
        
        # Add bidirectional arrows on angled lines
        painter.setBrush(QBrush(color))
        
        # Calculate direction vector
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = (dx**2 + dy**2)**0.5
        
        if length > 0:
            # Normalize direction
            unit_x = dx / length
            unit_y = dy / length
            
            # Arrow pointing toward end_point (25% along line)
            arrow1_pos = QPoint(
                int(start_point.x() + 0.25 * dx),
                int(start_point.y() + 0.25 * dy)
            )
            
            # Arrow pointing toward start_point (75% along line)  
            arrow2_pos = QPoint(
                int(start_point.x() + 0.75 * dx),
                int(start_point.y() + 0.75 * dy)
            )
            
            # Draw arrow pointing toward end (forward direction)
            self.draw_directional_arrow(painter, arrow1_pos, unit_x, unit_y, color)
            
            # Draw arrow pointing toward start (reverse direction)
            self.draw_directional_arrow(painter, arrow2_pos, -unit_x, -unit_y, color)
    
    def draw_directional_arrow(self, painter, position, unit_x, unit_y, color):
        """Draw a small directional arrow at given position."""
        arrow_size = 3
        
        # Calculate arrow points based on direction
        tip_x = position.x() + int(arrow_size * unit_x)
        tip_y = position.y() + int(arrow_size * unit_y)
        
        # Perpendicular vector for arrow wings
        perp_x = -unit_y
        perp_y = unit_x
        
        arrow_points = [
            QPoint(tip_x, tip_y),  # Arrow tip
            QPoint(
                int(position.x() - arrow_size * unit_x + arrow_size * 0.6 * perp_x),
                int(position.y() - arrow_size * unit_y + arrow_size * 0.6 * perp_y)
            ),
            QPoint(
                int(position.x() - arrow_size * unit_x - arrow_size * 0.6 * perp_x),
                int(position.y() - arrow_size * unit_y - arrow_size * 0.6 * perp_y)
            )
        ]
        
        painter.setBrush(QBrush(color))
        painter.drawPolygon(arrow_points)
    
    def draw_l_shaped_connection(self, painter, start_point, end_point, is_active):
        """Draw 90-degree L-shaped connection from router to outgoing ports."""
        if is_active:
            color = QColor('#107c10')  # Success green when active
            width = 2
        else:
            color = QColor('#0078d4')  # Blue accent when inactive
            width = 1
            
        painter.setPen(QPen(color, width))
        
        # Calculate corner point for L-shape
        # Vertical line from router center down, then horizontal line to port
        corner_point = QPoint(start_point.x(), end_point.y())
        
        # Draw vertical line (router to corner)
        painter.drawLine(start_point, corner_point)
        
        # Draw horizontal line (corner to port)
        painter.drawLine(corner_point, end_point)
        
        # Add bidirectional arrows
        painter.setBrush(QBrush(color))
        
        # Arrow on vertical segment (pointing down)
        vertical_mid = QPoint(start_point.x(), start_point.y() + (corner_point.y() - start_point.y()) // 2)
        down_arrow_points = [
            QPoint(vertical_mid.x() - 3, vertical_mid.y() - 3),
            QPoint(vertical_mid.x() + 3, vertical_mid.y() - 3),
            QPoint(vertical_mid.x(), vertical_mid.y() + 3)
        ]
        painter.drawPolygon(down_arrow_points)
        
        # Arrow on horizontal segment (pointing toward port)
        horizontal_mid = QPoint(corner_point.x() + (end_point.x() - corner_point.x()) // 2, end_point.y())
        if end_point.x() > corner_point.x():  # Pointing right
            right_arrow_points = [
                QPoint(horizontal_mid.x() - 3, horizontal_mid.y() - 3),
                QPoint(horizontal_mid.x() - 3, horizontal_mid.y() + 3),
                QPoint(horizontal_mid.x() + 3, horizontal_mid.y())
            ]
            painter.drawPolygon(right_arrow_points)
        else:  # Pointing left
            left_arrow_points = [
                QPoint(horizontal_mid.x() + 3, horizontal_mid.y() - 3),
                QPoint(horizontal_mid.x() + 3, horizontal_mid.y() + 3),
                QPoint(horizontal_mid.x() - 3, horizontal_mid.y())
            ]
            painter.drawPolygon(left_arrow_points)
        
    def draw_labels(self, painter, rect):
        """Draw minimal labels that don't overlap."""
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QPen(QColor('#0078d4')))  # Blue accent like QGroupBox::title
        
        # Single bottom label with minimal padding to prevent text overflow
        label_rect = QRect(rect.left() + 12, rect.bottom() - 18, rect.width() - 24, 14)  # Increased text area to prevent overflow
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "Connect -> COM 132 & 142")