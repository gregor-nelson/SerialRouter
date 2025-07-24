"""About dialog for SerialRouter."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QWidget, QFrame)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QFont, QDesktopServices, QPainter
from PyQt6.QtSvg import QSvgRenderer


class AboutDialog(QDialog):
    """Custom about dialog for SerialRouter with GitHub source link."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About SerialRouter")
        self.setModal(True)
        self.setFixedSize(400, 280)
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        # Apply Windows theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #333333;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Icon and title section
        header_layout = QHBoxLayout()
        
        # App icon from assets
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        # Use SerialRouter app icon (SVG)
        app_icon = self.load_svg_icon("assets/icons/app_icon.svg", 48, 48)
        icon_label.setPixmap(app_icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Title and version
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        
        title_label = QLabel("SerialRouter")
        title_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #0078d4;")
        
        version_label = QLabel("Version 2.0")
        version_font = QFont("Segoe UI", 10)
        version_label.setFont(version_font)
        version_label.setStyleSheet("color: #666666;")
        
        # GitHub link with text and icon
        github_layout = QHBoxLayout()
        github_layout.setContentsMargins(0, 0, 0, 0)
        github_layout.setSpacing(4)
        github_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Source Code label
        source_label = QLabel("Source Code")
        source_label.setFont(version_font)  # Same font as version
        source_label.setStyleSheet("color: #666666;")  # Same color as version
        source_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # GitHub icon button
        self.github_button = QPushButton()
        self.github_button.setFixedSize(12, 12)
        self.github_button.setToolTip("View source code on GitHub")
        
        # Create GitHub SVG icon
        github_svg = '''
        <svg width="12" height="12" viewBox="0 0 24 24" fill="#666666">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.30.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
        </svg>
        '''
        
        # Convert SVG to QIcon
        github_icon = self.create_github_icon(github_svg)
        self.github_button.setIcon(github_icon)
        self.github_button.setIconSize(self.github_button.size())
        
        # Style the button with proper hover effects
        self.github_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e8f4fd;
                border: 1px solid #0078d4;
            }
            QPushButton:pressed {
                background-color: #d1e7f7;
                border: 1px solid #106ebe;
            }
        """)
        
        # Set cursor to pointer on hover
        self.github_button.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Add to horizontal layout with center alignment
        github_layout.addWidget(source_label)
        github_layout.addWidget(self.github_button)
        github_layout.addStretch()
        
        # Create container widget for the github layout
        github_widget = QWidget()
        github_widget.setLayout(github_layout)
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(version_label)
        title_layout.addWidget(github_widget)
        title_layout.addStretch()
        
        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #e1e1e1;")
        layout.addWidget(separator)
        
        # Description text
        description_label = QLabel(
            "Production-hardened serial port routing application for offshore environments.\n\n"
            "Routes data between an incoming port and two fixed outgoing ports (COM131, COM141) "
            "with bidirectional communication and automatic recovery capabilities."
        )
        description_label.setWordWrap(True)
        description_label.setFont(QFont("Segoe UI", 9))
        description_label.setStyleSheet("color: #333333; line-height: 1.4;")
        layout.addWidget(description_label)
        
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.setFixedSize(80, 32)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d9d9d9;
                border-radius: 0px;
                padding: 6px 16px;
                font-size: 11px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #e8f4fd;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #d1e7f7;
                border-color: #106ebe;
            }
        """)
        close_button.clicked.connect(self.close)
        
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
    
    def load_svg_icon(self, svg_path, width, height):
        """Load SVG icon from file path and return as QPixmap."""
        try:
            # Try to use SVG renderer
            renderer = QSvgRenderer()
            renderer.load(svg_path)
            
            pixmap = QPixmap(width, height)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            return pixmap
        except ImportError:
            # Fallback if QtSvg is not available - use system icon
            fallback_icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
            return fallback_icon.pixmap(width, height)

    def create_github_icon(self, svg_content):
        """Create a QIcon from SVG content."""
        try:
            # Try to use SVG renderer
            renderer = QSvgRenderer()
            renderer.load(svg_content.encode('utf-8'))
            
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
        except ImportError:
            # Fallback if QtSvg is not available - use Unicode icon
            return self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView)
    
    def setup_connections(self):
        """Set up signal connections."""
        self.github_button.clicked.connect(self.open_github_repository)
    
    def open_github_repository(self):
        """Open the GitHub repository in the default browser."""
        # SerialRouter GitHub repository URL
        github_url = "https://github.com/gregor-nelson/SerialRouter"
        QDesktopServices.openUrl(QUrl(github_url))
    
    @staticmethod
    def show_about(parent=None):
        """Static method to show the about dialog."""
        dialog = AboutDialog(parent)
        dialog.exec()