"""Download dialog for CDSE Plugin."""

import os
from typing import TYPE_CHECKING, List, Optional

try:
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtWidgets import (
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QProgressBar,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )
except ImportError:
    pass

if TYPE_CHECKING:
    from ..api.auth import AuthManager
    from ..api.models import SearchResult


class DownloadDialog(QDialog):
    """Dialog for managing downloads.

    This dialog shows download progress and allows users to
    select output directory and manage downloads.

    Signals:
        download_started: Emitted when downloads start.
        download_completed: Emitted when all downloads complete with (successful, failed).
    """

    download_started = pyqtSignal()
    download_completed = pyqtSignal(int, int)  # successful, failed

    def __init__(
        self,
        results: List["SearchResult"],
        auth_manager: "AuthManager",
        parent=None,
    ):
        """Initialize the download dialog.

        Args:
            results: List of SearchResult objects to download.
            auth_manager: Authentication manager for authorized downloads.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.results = results
        self.auth_manager = auth_manager
        self._download_worker = None
        self._output_dir = ""
        self._downloadable_count = 0
        self._setup_ui()
        self._update_status()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Download Products")
        self.setMinimumSize(700, 500)
        self.resize(750, 550)
        # Make dialog non-modal so QGIS remains usable during downloads
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)

        # Output directory selection
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Output Directory:"))

        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        dir_layout.addWidget(self.dir_edit)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(self.browse_btn)

        layout.addLayout(dir_layout)

        # Downloads table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Size", "Status", "Progress", "URL"]
        )
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setColumnHidden(4, True)  # Hide URL column

        # Populate table
        self.table.setRowCount(len(self.results))
        self._downloadable_count = 0

        for row, result in enumerate(self.results):
            # Name
            name_item = QTableWidgetItem(result.name)
            name_item.setToolTip(result.name)
            self.table.setItem(row, 0, name_item)

            # Size
            size_str = "Unknown"
            if result.size_mb is not None:
                size_str = f"{result.size_mb:.1f} MB"
            self.table.setItem(row, 1, QTableWidgetItem(size_str))

            # Status - check if downloadable
            if result.download_url:
                status = "Ready"
                self._downloadable_count += 1
            else:
                status = "No download URL"
            self.table.setItem(row, 2, QTableWidgetItem(status))

            # Progress
            progress = QProgressBar()
            progress.setMinimum(0)
            progress.setMaximum(100)
            progress.setValue(0)
            self.table.setCellWidget(row, 3, progress)

            # URL (hidden)
            url_item = QTableWidgetItem(result.download_url or "")
            self.table.setItem(row, 4, url_item)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        # Overall progress
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Overall:"))

        self.overall_progress = QProgressBar()
        self.overall_progress.setMinimum(0)
        self.overall_progress.setMaximum(max(self._downloadable_count, 1))
        self.overall_progress.setValue(0)
        progress_layout.addWidget(self.overall_progress)

        layout.addLayout(progress_layout)

        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Download")
        self.start_btn.clicked.connect(self._start_downloads)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_downloads)
        button_layout.addWidget(self.cancel_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _update_status(self) -> None:
        """Update the status label."""
        # Check if any items are S3-only (eodata URLs)
        s3_only_count = 0
        for result in self.results:
            if (
                result.download_url
                and "eodata.dataspace.copernicus.eu" in result.download_url
            ):
                s3_only_count += 1

        if self._downloadable_count == 0:
            self.status_label.setText("No downloadable items found")
            self.start_btn.setEnabled(False)
        elif s3_only_count > 0:
            # S3-only items require S3 credentials
            if self.auth_manager.has_aws_credentials():
                self.status_label.setText(
                    f"{self._downloadable_count} items (S3 data) - select output directory"
                )
            else:
                self.status_label.setText(
                    f"⚠ {s3_only_count} item(s) require S3 credentials (configure in Settings)"
                )
                self.status_label.setStyleSheet("color: orange")
        elif not self._output_dir:
            self.status_label.setText(
                f"{self._downloadable_count} items ready - select output directory"
            )
        else:
            self.status_label.setText(
                f"{self._downloadable_count} items ready to download"
            )

    def _browse_directory(self) -> None:
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self._output_dir or os.path.expanduser("~"),
        )
        if directory:
            self._output_dir = directory
            self.dir_edit.setText(directory)
            if self._downloadable_count > 0:
                self.start_btn.setEnabled(True)
            self._update_status()

    def _start_downloads(self) -> None:
        """Start the download process."""
        if not self._output_dir:
            self.status_label.setText("Please select an output directory")
            return

        # Check authentication
        if not self.auth_manager.is_authenticated():
            self.status_label.setText("Authentication required. Please log in first.")
            return

        # Prepare downloads
        downloads = []
        for row, result in enumerate(self.results):
            if result.download_url:
                # Use ID for filename to avoid issues with special characters
                filename = f"{result.id}.zip"
                output_path = os.path.join(self._output_dir, filename)
                downloads.append((result.download_url, output_path))
                # Update status
                self.table.item(row, 2).setText("Queued")

        if not downloads:
            self.status_label.setText("No downloadable items")
            return

        # Disable controls
        self.start_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.close_btn.setEnabled(False)

        # Update overall progress max
        self.overall_progress.setMaximum(len(downloads))
        self.overall_progress.setValue(0)

        # Start worker
        from ..workers.download_worker import BatchDownloadWorker

        self._download_worker = BatchDownloadWorker(
            downloads=downloads,
            auth_manager=self.auth_manager,
            parent=self,
        )
        self._download_worker.item_started.connect(self._on_item_started)
        self._download_worker.item_progress.connect(self._on_item_progress)
        self._download_worker.item_finished.connect(self._on_item_finished)
        self._download_worker.item_error.connect(self._on_item_error)
        self._download_worker.all_finished.connect(self._on_all_finished)

        self.status_label.setText("Starting downloads...")
        self.download_started.emit()
        self._download_worker.start()

    def _cancel_downloads(self) -> None:
        """Cancel all downloads."""
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.cancel()
            self.status_label.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
        else:
            self.reject()

    def _on_item_started(self, index: int, url: str) -> None:
        """Handle item download started.

        Args:
            index: Index of the item.
            url: Download URL.
        """
        # Find the row with matching URL
        row = self._find_row_by_url(url)
        if row >= 0:
            self.table.item(row, 2).setText("Downloading...")

    def _on_item_progress(
        self, index: int, url: str, downloaded: int, total: int
    ) -> None:
        """Handle item download progress.

        Args:
            index: Index of the item.
            url: Download URL.
            downloaded: Bytes downloaded.
            total: Total bytes.
        """
        row = self._find_row_by_url(url)
        if row >= 0:
            progress = self.table.cellWidget(row, 3)
            if progress and total > 0:
                percent = int(downloaded / total * 100)
                progress.setValue(percent)
                # Update size if it was unknown
                if self.table.item(row, 1).text() == "Unknown":
                    size_mb = total / (1024 * 1024)
                    self.table.item(row, 1).setText(f"{size_mb:.1f} MB")

    def _on_item_finished(
        self, index: int, url: str, filepath: str, success: bool
    ) -> None:
        """Handle item download finished.

        Args:
            index: Index of the item.
            url: Download URL.
            filepath: Output file path.
            success: Whether download was successful.
        """
        row = self._find_row_by_url(url)
        if row >= 0:
            self.table.item(row, 2).setText("Completed" if success else "Failed")
            progress = self.table.cellWidget(row, 3)
            if progress:
                progress.setValue(100 if success else 0)

        self.overall_progress.setValue(self.overall_progress.value() + 1)

    def _on_item_error(self, index: int, url: str, error: str) -> None:
        """Handle item download error.

        Args:
            index: Index of the item.
            url: Download URL.
            error: Error message.
        """
        row = self._find_row_by_url(url)
        if row >= 0:
            self.table.item(row, 2).setText(f"Error: {error}")
            self.table.item(row, 2).setToolTip(error)

        self.overall_progress.setValue(self.overall_progress.value() + 1)

    def _on_all_finished(self, successful: int, failed: int) -> None:
        """Handle all downloads finished.

        Args:
            successful: Number of successful downloads.
            failed: Number of failed downloads.
        """
        self.status_label.setText(
            f"Download complete: {successful} successful, {failed} failed"
        )
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.download_completed.emit(successful, failed)

    def _find_row_by_url(self, url: str) -> int:
        """Find table row by download URL.

        Args:
            url: Download URL.

        Returns:
            Row index or -1 if not found.
        """
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 4)
            if item and item.text() == url:
                return row
        return -1

    def set_output_directory(self, directory: str) -> None:
        """Set the output directory.

        Args:
            directory: Directory path.
        """
        if directory and os.path.isdir(directory):
            self._output_dir = directory
            self.dir_edit.setText(directory)
            if self._downloadable_count > 0:
                self.start_btn.setEnabled(True)
            self._update_status()
