"""About dialog for Serial Splitter."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QWidget, QFrame, QGroupBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QFont, QDesktopServices, QPainter, QKeySequence, QShortcut
from PyQt6.QtSvg import QSvgRenderer
from src.gui.resources import resource_manager


class AboutDialog(QDialog):
    """Custom about dialog for Serial Splitter with GitHub source link."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Serial Splitter")
        self.setModal(True)
        self.setFixedSize(420, 300)
        
        # Center on parent window
        if parent:
            parent_geometry = parent.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            self.move(x, y)
        
        # Apply the same theme as main window
        self.apply_theme()
        
        self.setup_ui()
        self.setup_connections()
        self.setup_keyboard_shortcuts()
    
    def apply_theme(self):
        """Apply the same theme as the main window."""
        theme_css = resource_manager.load_theme()
        if theme_css:
            self.setStyleSheet(theme_css)
    
    def setup_ui(self):
        """Set up the dialog UI to match main window structure."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Match main window spacing
        layout.setContentsMargins(10, 10, 10, 10)  # Match main window margins
        
        # Single About Group (matches main window QGroupBox style)
        about_group = QGroupBox("About Serial Splitter")
        about_layout = QVBoxLayout(about_group)
        about_layout.setSpacing(12)
        
        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # App icon - use MessageBoxInformation for better context
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        info_icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxInformation)
        icon_label.setPixmap(info_icon.pixmap(48, 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Title and version info
        title_info_layout = QVBoxLayout()
        title_info_layout.setSpacing(2)
        
        title_label = QLabel("Serial Splitter")
        title_label.setProperty("class", "title")  # Use theme's title class
        
        version_label = QLabel("Version 2.0")
        version_label.setProperty("class", "description")  # Use theme's description class
        
        title_info_layout.addWidget(title_label)
        title_info_layout.addWidget(version_label)
        title_info_layout.addStretch()
        
        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_info_layout)
        header_layout.addStretch()
        
        about_layout.addLayout(header_layout)
        
        # Description text
        description_label = QLabel(
            "A robust serial port routing application for continuous operation environments.\n\n"
            "Routes data between a configurable incoming port and two fixed outgoing ports "
            "(COM131, COM141) with bidirectional communication and automatic fault recovery."
        )
        description_label.setWordWrap(True)
        # Let the theme handle the font styling
        about_layout.addWidget(description_label)
        
        # GitHub icon only (bottom right)
        github_layout = QHBoxLayout()
        github_layout.addStretch()
        
        self.github_button = QPushButton()
        self.github_button.setFixedSize(24, 24)
        self.github_button.setToolTip("View source code on GitHub")
        
        # Remove border and background, add hover effect
        palette = self.palette()
        self.github_button.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: transparent;
            }}
        """)
        
        # Create GitHub SVG icon using QPalette colors
        palette = self.palette()
        disabled_color = palette.color(palette.ColorGroup.Disabled, palette.ColorRole.WindowText)
        
        github_svg = f'''
        <svg width="20" height="20" viewBox="0 0 24 24" fill="{disabled_color.name()}">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
        </svg>
        '''
        
        # Convert SVG to QIcon
        github_icon = self.create_github_icon(github_svg)
        self.github_button.setIcon(github_icon)
        self.github_button.setIconSize(self.github_button.size())
        
        # Set cursor to pointer on hover
        self.github_button.setCursor(Qt.CursorShape.PointingHandCursor)
        
        github_layout.addWidget(self.github_button)
        
        about_layout.addLayout(github_layout)
        
        layout.addWidget(about_group)
        
        # Button area (matches main window button placement)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.setDefault(True)  # Make it the default button for Enter key
        # Let the theme handle button styling - no custom stylesheet needed
        self.close_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
    
    def setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts for professional behavior."""
        # Escape key to close dialog
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self.close)
        
        # Enter key to activate Close button (handled by setDefault(True) above)
        # Return key as well
        return_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        return_shortcut.activated.connect(self.close_button.click)
    
    def create_github_icon(self, svg_content):
        """Create a QIcon from SVG content with hover states."""
        try:
            # Try to use SVG renderer
            renderer = QSvgRenderer()
            renderer.load(svg_content.encode('utf-8'))
            
            # Create normal state icon
            normal_pixmap = QPixmap(20, 20)
            normal_pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(normal_pixmap)
            renderer.render(painter)
            painter.end()
            
            # Create hover state icon (darker)
            palette = self.palette()
            text_color = palette.color(palette.ColorGroup.Normal, palette.ColorRole.WindowText)
            # Replace the disabled color with normal text color for hover
            disabled_color = palette.color(palette.ColorGroup.Disabled, palette.ColorRole.WindowText)
            hover_svg = svg_content.replace(f'fill="{disabled_color.name()}"', f'fill="{text_color.name()}"')
            
            hover_renderer = QSvgRenderer()
            hover_renderer.load(hover_svg.encode('utf-8'))
            
            hover_pixmap = QPixmap(20, 20)
            hover_pixmap.fill(Qt.GlobalColor.transparent)
            
            hover_painter = QPainter(hover_pixmap)
            hover_renderer.render(hover_painter)
            hover_painter.end()
            
            # Create icon with multiple states
            icon = QIcon()
            icon.addPixmap(normal_pixmap, QIcon.Mode.Normal)
            icon.addPixmap(hover_pixmap, QIcon.Mode.Active)
            
            return icon
        except ImportError:
            # Fallback if QtSvg is not available - use Unicode icon
            return self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView)
    
    def setup_connections(self):
        """Set up signal connections."""
        self.github_button.clicked.connect(self.open_github_repository)
    
    def open_github_repository(self):
        """Open the GitHub repository in the default browser."""
        # Serial Splitter GitHub repository URL
        github_url = "https://github.com/gregor-nelson/SerialSplitter"
        QDesktopServices.openUrl(QUrl(github_url))
    
    @staticmethod
    def show_about(parent=None):
        """Static method to show the about dialog."""
        dialog = AboutDialog(parent)
        dialog.exec()