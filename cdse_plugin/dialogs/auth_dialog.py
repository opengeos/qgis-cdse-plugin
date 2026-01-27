"""Authentication dialog for CDSE Plugin."""

try:
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )

from ..api.auth import AuthManager


class AuthDialog(QDialog):
    """Dialog for CDSE authentication.

    This dialog allows users to log in to their CDSE account.

    Attributes:
        auth_manager: Authentication manager instance.
        username_edit: Username input field.
        password_edit: Password input field.
    """

    def __init__(self, auth_manager: AuthManager, parent=None):
        """Initialize the authentication dialog.

        Args:
            auth_manager: Authentication manager instance.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.auth_manager = auth_manager
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("CDSE Login")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "Enter your Copernicus Data Space Ecosystem credentials.\n"
            "Don't have an account? Register at dataspace.copernicus.eu"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Form layout for credentials
        form_layout = QFormLayout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Email address")
        form_layout.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Password")
        form_layout.addRow("Password:", self.password_edit)

        layout.addLayout(form_layout)

        # Status label
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Buttons
        button_box = QDialogButtonBox()

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self._on_login)
        button_box.addButton(self.login_button, QDialogButtonBox.AcceptRole)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_box.addButton(self.cancel_button, QDialogButtonBox.RejectRole)

        layout.addWidget(button_box)

        # Pre-fill username if available
        if self.auth_manager.username:
            self.username_edit.setText(self.auth_manager.username)
            self.password_edit.setFocus()
        else:
            self.username_edit.setFocus()

        # Connect enter key
        self.password_edit.returnPressed.connect(self._on_login)

    def _on_login(self) -> None:
        """Handle login button click."""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        if not username:
            self.status_label.setText("Please enter your username")
            self.status_label.setStyleSheet("color: red")
            return

        if not password:
            self.status_label.setText("Please enter your password")
            self.status_label.setStyleSheet("color: red")
            return

        # Disable UI during login
        self.login_button.setEnabled(False)
        self.username_edit.setEnabled(False)
        self.password_edit.setEnabled(False)
        self.status_label.setText("Logging in...")
        self.status_label.setStyleSheet("")

        # Process events to update UI
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()

        # Attempt login
        success, message = self.auth_manager.login(username, password)

        if success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: green")
            self.accept()
        else:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: red")
            self.login_button.setEnabled(True)
            self.username_edit.setEnabled(True)
            self.password_edit.setEnabled(True)
            self.password_edit.setFocus()
            self.password_edit.selectAll()

    def get_credentials(self) -> tuple:
        """Get the entered credentials.

        Returns:
            Tuple of (username, password).
        """
        return self.username_edit.text().strip(), self.password_edit.text()


class LogoutConfirmDialog(QDialog):
    """Dialog to confirm logout."""

    def __init__(self, username: str, parent=None):
        """Initialize the logout confirmation dialog.

        Args:
            username: Current username.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Confirm Logout")

        layout = QVBoxLayout(self)

        label = QLabel(
            f"Are you sure you want to log out?\n\nCurrently logged in as: {username}"
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
