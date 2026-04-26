"""Settings dock widget for CDSE Plugin."""

import os
from typing import TYPE_CHECKING

try:
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtWidgets import (
        QColorDialog,
        QDockWidget,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSlider,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
    from qgis.core import QgsSettings
except ImportError:
    pass

if TYPE_CHECKING:
    from ..api.auth import AuthManager

from ..utils.config import (
    DEFAULT_CLOUD_COVER,
    DEFAULT_DATE_RANGE_DAYS,
    DEFAULT_MAX_RESULTS,
    FOOTPRINT_COLOR,
    FOOTPRINT_OPACITY,
    MAX_CONCURRENT_DOWNLOADS,
    THUMBNAIL_SIZE,
)


class SettingsDock(QDockWidget):
    """Dock widget for plugin settings.

    This dock provides UI for configuring plugin settings including
    credentials, search defaults, download options, and display settings.

    Signals:
        settings_changed: Emitted when settings are changed.
    """

    settings_changed = pyqtSignal()

    SETTINGS_PREFIX = "cdse_plugin"

    def __init__(self, auth_manager: "AuthManager", parent=None):
        """Initialize the settings dock.

        Args:
            auth_manager: Authentication manager instance.
            parent: Parent widget.
        """
        super().__init__("CDSE Settings", parent)
        self.auth_manager = auth_manager
        self._setup_ui()
        self._load_settings()
        self._update_auth_status()

    def _setup_ui(self) -> None:
        """Set up the dock UI."""
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Tab widget
        tabs = QTabWidget()

        # Credentials tab
        credentials_tab = QWidget()
        credentials_layout = QVBoxLayout(credentials_tab)

        # OAuth credentials group
        oauth_group = QGroupBox("OAuth2 Credentials (for API access)")
        oauth_layout = QFormLayout(oauth_group)

        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText("Enter Client ID")
        oauth_layout.addRow("Client ID:", self.client_id_edit)

        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setPlaceholderText("Enter Client Secret")
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        oauth_layout.addRow("Client Secret:", self.client_secret_edit)

        oauth_btn_layout = QHBoxLayout()
        self.save_oauth_btn = QPushButton("Save && Test OAuth")
        self.save_oauth_btn.clicked.connect(self._save_oauth_credentials)
        oauth_btn_layout.addWidget(self.save_oauth_btn)

        self.oauth_status_label = QLabel()
        oauth_btn_layout.addWidget(self.oauth_status_label)
        oauth_btn_layout.addStretch()

        oauth_layout.addRow("", oauth_btn_layout)

        credentials_layout.addWidget(oauth_group)

        # S3 credentials group
        s3_group = QGroupBox("S3 Credentials (for DEM/COG access)")
        s3_layout = QFormLayout(s3_group)

        self.aws_key_edit = QLineEdit()
        self.aws_key_edit.setPlaceholderText("Enter Access Key ID")
        s3_layout.addRow("Access Key ID:", self.aws_key_edit)

        self.aws_secret_edit = QLineEdit()
        self.aws_secret_edit.setPlaceholderText("Enter Secret Access Key")
        self.aws_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        s3_layout.addRow("Secret Access Key:", self.aws_secret_edit)

        s3_btn_layout = QHBoxLayout()
        self.save_s3_btn = QPushButton("Save S3 Credentials")
        self.save_s3_btn.clicked.connect(self._save_s3_credentials)
        s3_btn_layout.addWidget(self.save_s3_btn)

        self.s3_status_label = QLabel()
        s3_btn_layout.addWidget(self.s3_status_label)
        s3_btn_layout.addStretch()

        s3_layout.addRow("", s3_btn_layout)

        credentials_layout.addWidget(s3_group)

        # Help text
        help_label = QLabel(
            "<b>How to get credentials:</b><br>"
            "1. Go to <a href='https://dataspace.copernicus.eu/'>dataspace.copernicus.eu</a><br>"
            "2. Log in and go to User Settings<br>"
            "3. Generate OAuth2 credentials (Client ID + Secret)<br>"
            "4. Generate S3 credentials for DEM/COG access"
        )
        help_label.setWordWrap(True)
        help_label.setOpenExternalLinks(True)
        help_label.setStyleSheet("color: #666; padding: 10px;")
        credentials_layout.addWidget(help_label)

        # Clear credentials button
        clear_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear All Credentials")
        self.clear_btn.clicked.connect(self._clear_credentials)
        clear_layout.addWidget(self.clear_btn)
        clear_layout.addStretch()
        credentials_layout.addLayout(clear_layout)

        credentials_layout.addStretch()

        tabs.addTab(credentials_tab, "Credentials")

        # Search defaults tab
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)

        defaults_group = QGroupBox("Default Values")
        defaults_layout = QFormLayout(defaults_group)

        self.default_cloud_spin = QSpinBox()
        self.default_cloud_spin.setMinimum(0)
        self.default_cloud_spin.setMaximum(100)
        self.default_cloud_spin.setValue(DEFAULT_CLOUD_COVER)
        defaults_layout.addRow("Cloud Cover (%):", self.default_cloud_spin)

        self.default_days_spin = QSpinBox()
        self.default_days_spin.setMinimum(1)
        self.default_days_spin.setMaximum(365)
        self.default_days_spin.setValue(DEFAULT_DATE_RANGE_DAYS)
        defaults_layout.addRow("Date Range (days):", self.default_days_spin)

        self.default_results_spin = QSpinBox()
        self.default_results_spin.setMinimum(1)
        self.default_results_spin.setMaximum(1000)
        self.default_results_spin.setValue(DEFAULT_MAX_RESULTS)
        defaults_layout.addRow("Max Results:", self.default_results_spin)

        search_layout.addWidget(defaults_group)
        search_layout.addStretch()

        tabs.addTab(search_tab, "Search")

        # Download tab
        download_tab = QWidget()
        download_layout = QVBoxLayout(download_tab)

        download_group = QGroupBox("Download Settings")
        download_form = QFormLayout(download_group)

        dir_layout = QHBoxLayout()
        self.download_dir_edit = QLineEdit()
        self.download_dir_edit.setReadOnly(True)
        dir_layout.addWidget(self.download_dir_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_download_dir)
        dir_layout.addWidget(browse_btn)

        download_form.addRow("Default Directory:", dir_layout)

        self.concurrent_downloads_spin = QSpinBox()
        self.concurrent_downloads_spin.setMinimum(1)
        self.concurrent_downloads_spin.setMaximum(10)
        self.concurrent_downloads_spin.setValue(MAX_CONCURRENT_DOWNLOADS)
        download_form.addRow("Concurrent Downloads:", self.concurrent_downloads_spin)

        download_layout.addWidget(download_group)
        download_layout.addStretch()

        tabs.addTab(download_tab, "Download")

        # Display tab
        display_tab = QWidget()
        display_layout = QVBoxLayout(display_tab)

        footprint_group = QGroupBox("Footprint Styling")
        footprint_layout = QFormLayout(footprint_group)

        color_layout = QHBoxLayout()
        self.footprint_color_btn = QPushButton()
        self.footprint_color_btn.setFixedSize(60, 25)
        self._footprint_color = FOOTPRINT_COLOR
        self._update_color_button()
        self.footprint_color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.footprint_color_btn)
        color_layout.addStretch()
        footprint_layout.addRow("Color:", color_layout)

        opacity_layout = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(int(FOOTPRINT_OPACITY * 100))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)

        self.opacity_label = QLabel(f"{int(FOOTPRINT_OPACITY * 100)}%")
        self.opacity_label.setMinimumWidth(40)
        opacity_layout.addWidget(self.opacity_label)

        footprint_layout.addRow("Opacity:", opacity_layout)

        display_layout.addWidget(footprint_group)

        thumbnail_group = QGroupBox("Thumbnails")
        thumbnail_layout = QFormLayout(thumbnail_group)

        self.thumbnail_size_spin = QSpinBox()
        self.thumbnail_size_spin.setMinimum(32)
        self.thumbnail_size_spin.setMaximum(256)
        self.thumbnail_size_spin.setValue(THUMBNAIL_SIZE)
        thumbnail_layout.addRow("Size (px):", self.thumbnail_size_spin)

        display_layout.addWidget(thumbnail_group)
        display_layout.addStretch()

        tabs.addTab(display_tab, "Display")

        layout.addWidget(tabs)

        # Save/Reset buttons
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_settings)
        button_layout.addWidget(self.reset_btn)

        layout.addLayout(button_layout)

        self.setWidget(main_widget)

    def _load_settings(self) -> None:
        """Load settings from QgsSettings."""
        settings = QgsSettings()

        # Load OAuth credentials (masked)
        if self.auth_manager.client_id:
            self.client_id_edit.setText(self.auth_manager.client_id)
        # Don't load secret into edit field for security, but show placeholder
        if self.auth_manager._client_secret:
            self.client_secret_edit.setPlaceholderText("••••••••")

        # Load AWS credentials (masked)
        if self.auth_manager.aws_access_key_id:
            self.aws_key_edit.setText(self.auth_manager.aws_access_key_id)
        if self.auth_manager._aws_secret_access_key:
            self.aws_secret_edit.setPlaceholderText("••••••••")

        # Search defaults
        self.default_cloud_spin.setValue(
            settings.value(
                f"{self.SETTINGS_PREFIX}/default_cloud_cover",
                DEFAULT_CLOUD_COVER,
                type=int,
            )
        )
        self.default_days_spin.setValue(
            settings.value(
                f"{self.SETTINGS_PREFIX}/default_date_range",
                DEFAULT_DATE_RANGE_DAYS,
                type=int,
            )
        )
        self.default_results_spin.setValue(
            settings.value(
                f"{self.SETTINGS_PREFIX}/default_max_results",
                DEFAULT_MAX_RESULTS,
                type=int,
            )
        )

        # Download settings
        download_dir = settings.value(
            f"{self.SETTINGS_PREFIX}/download_dir", "", type=str
        )
        self.download_dir_edit.setText(download_dir)
        self.concurrent_downloads_spin.setValue(
            settings.value(
                f"{self.SETTINGS_PREFIX}/concurrent_downloads",
                MAX_CONCURRENT_DOWNLOADS,
                type=int,
            )
        )

        # Display settings
        self._footprint_color = settings.value(
            f"{self.SETTINGS_PREFIX}/footprint_color", FOOTPRINT_COLOR, type=str
        )
        self._update_color_button()

        opacity = settings.value(
            f"{self.SETTINGS_PREFIX}/footprint_opacity",
            int(FOOTPRINT_OPACITY * 100),
            type=int,
        )
        self.opacity_slider.setValue(opacity)

        self.thumbnail_size_spin.setValue(
            settings.value(
                f"{self.SETTINGS_PREFIX}/thumbnail_size", THUMBNAIL_SIZE, type=int
            )
        )

    def _save_settings(self) -> None:
        """Save settings to QgsSettings."""
        settings = QgsSettings()

        # Search defaults
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/default_cloud_cover",
            self.default_cloud_spin.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/default_date_range", self.default_days_spin.value()
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/default_max_results",
            self.default_results_spin.value(),
        )

        # Download settings
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/download_dir", self.download_dir_edit.text()
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/concurrent_downloads",
            self.concurrent_downloads_spin.value(),
        )

        # Display settings
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/footprint_color", self._footprint_color
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/footprint_opacity", self.opacity_slider.value()
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/thumbnail_size", self.thumbnail_size_spin.value()
        )

        self.settings_changed.emit()

    def _save_oauth_credentials(self) -> None:
        """Save and test OAuth credentials."""
        client_id = self.client_id_edit.text().strip()
        client_secret = self.client_secret_edit.text().strip()

        if not client_id:
            self.oauth_status_label.setText("Client ID required")
            self.oauth_status_label.setStyleSheet("color: red")
            return

        # If secret is empty but we have a stored one, use stored
        if not client_secret and self.auth_manager._client_secret:
            client_secret = self.auth_manager._client_secret

        if not client_secret:
            self.oauth_status_label.setText("Client Secret required")
            self.oauth_status_label.setStyleSheet("color: red")
            return

        self.oauth_status_label.setText("Testing...")
        self.oauth_status_label.setStyleSheet("")
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()

        success, message = self.auth_manager.set_oauth_credentials(
            client_id, client_secret
        )

        if success:
            self.oauth_status_label.setText("✓ Connected")
            self.oauth_status_label.setStyleSheet("color: green")
            self.client_secret_edit.clear()
            self.client_secret_edit.setPlaceholderText("••••••••")
        else:
            self.oauth_status_label.setText(f"✗ {message}")
            self.oauth_status_label.setStyleSheet("color: red")

        self._update_auth_status()

    def _save_s3_credentials(self) -> None:
        """Save S3 credentials."""
        access_key = self.aws_key_edit.text().strip()
        secret_key = self.aws_secret_edit.text().strip()

        if not access_key:
            self.s3_status_label.setText("Access Key ID required")
            self.s3_status_label.setStyleSheet("color: red")
            return

        # If secret is empty but we have a stored one, use stored
        if not secret_key and self.auth_manager._aws_secret_access_key:
            secret_key = self.auth_manager._aws_secret_access_key

        if not secret_key:
            self.s3_status_label.setText("Secret Access Key required")
            self.s3_status_label.setStyleSheet("color: red")
            return

        success, message = self.auth_manager.set_aws_credentials(access_key, secret_key)

        if success:
            self.s3_status_label.setText("✓ Saved")
            self.s3_status_label.setStyleSheet("color: green")
            self.aws_secret_edit.clear()
            self.aws_secret_edit.setPlaceholderText("••••••••")
        else:
            self.s3_status_label.setText(f"✗ {message}")
            self.s3_status_label.setStyleSheet("color: red")

    def _clear_credentials(self) -> None:
        """Clear all stored credentials."""
        reply = QMessageBox.question(
            self,
            "Clear Credentials",
            "Are you sure you want to clear all stored credentials?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.auth_manager.logout()
            self.client_id_edit.clear()
            self.client_secret_edit.clear()
            self.client_secret_edit.setPlaceholderText("Enter Client Secret")
            self.aws_key_edit.clear()
            self.aws_secret_edit.clear()
            self.aws_secret_edit.setPlaceholderText("Enter Secret Access Key")
            self.oauth_status_label.setText("")
            self.s3_status_label.setText("")
            self._update_auth_status()

    def _update_auth_status(self) -> None:
        """Update authentication status indicators."""
        if self.auth_manager.is_authenticated():
            if not self.oauth_status_label.text():
                self.oauth_status_label.setText("✓ Connected")
                self.oauth_status_label.setStyleSheet("color: green")

        if self.auth_manager.has_aws_credentials():
            if not self.s3_status_label.text():
                self.s3_status_label.setText("✓ Configured")
                self.s3_status_label.setStyleSheet("color: green")

    def _reset_settings(self) -> None:
        """Reset settings to defaults."""
        self.default_cloud_spin.setValue(DEFAULT_CLOUD_COVER)
        self.default_days_spin.setValue(DEFAULT_DATE_RANGE_DAYS)
        self.default_results_spin.setValue(DEFAULT_MAX_RESULTS)
        self.download_dir_edit.setText("")
        self.concurrent_downloads_spin.setValue(MAX_CONCURRENT_DOWNLOADS)
        self._footprint_color = FOOTPRINT_COLOR
        self._update_color_button()
        self.opacity_slider.setValue(int(FOOTPRINT_OPACITY * 100))
        self.thumbnail_size_spin.setValue(THUMBNAIL_SIZE)

    def _browse_download_dir(self) -> None:
        """Browse for download directory."""
        current = self.download_dir_edit.text() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", current
        )
        if directory:
            self.download_dir_edit.setText(directory)

    def _choose_color(self) -> None:
        """Open color chooser dialog."""
        from qgis.PyQt.QtGui import QColor

        color = QColorDialog.getColor(QColor(self._footprint_color), self)
        if color.isValid():
            self._footprint_color = color.name()
            self._update_color_button()

    def _update_color_button(self) -> None:
        """Update color button background."""
        self.footprint_color_btn.setStyleSheet(
            f"background-color: {self._footprint_color}; border: 1px solid #888;"
        )

    def _on_opacity_changed(self, value: int) -> None:
        """Handle opacity slider change.

        Args:
            value: New slider value (0-100).
        """
        self.opacity_label.setText(f"{value}%")

    def update_auth_status(self) -> None:
        """Update the authentication status display (public method)."""
        self._update_auth_status()

    def get_default_download_dir(self) -> str:
        """Get the default download directory.

        Returns:
            Directory path or empty string.
        """
        return self.download_dir_edit.text()

    def get_footprint_color(self) -> str:
        """Get the footprint color.

        Returns:
            Color as hex string.
        """
        return self._footprint_color

    def get_footprint_opacity(self) -> float:
        """Get the footprint opacity.

        Returns:
            Opacity as float (0-1).
        """
        return self.opacity_slider.value() / 100.0

    def get_thumbnail_size(self) -> int:
        """Get the thumbnail size.

        Returns:
            Size in pixels.
        """
        return self.thumbnail_size_spin.value()
