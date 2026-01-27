"""Download worker thread for CDSE Plugin."""

import os
from typing import TYPE_CHECKING, Optional

import requests

try:
    from qgis.PyQt.QtCore import QThread, pyqtSignal
except ImportError:
    from PyQt5.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from ..api.auth import AuthManager

from ..utils.config import CHUNK_SIZE


class DownloadWorker(QThread):
    """Background worker for file downloads.

    This worker handles file downloads in a separate thread with progress reporting.

    Signals:
        finished: Emitted when download completes with (url, filepath, success).
        error: Emitted when an error occurs with (url, error_message).
        progress: Emitted during download with (url, bytes_downloaded, total_bytes).
    """

    finished = pyqtSignal(str, str, bool)  # url, filepath, success
    error = pyqtSignal(str, str)  # url, error_message
    progress = pyqtSignal(str, int, int)  # url, downloaded, total

    def __init__(
        self,
        url: str = "",
        output_path: str = "",
        auth_manager: Optional["AuthManager"] = None,
        parent=None,
    ):
        """Initialize the download worker.

        Args:
            url: URL to download from.
            output_path: Local file path to save to.
            auth_manager: Authentication manager for authorized downloads.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.url = url
        self.output_path = output_path
        self.auth_manager = auth_manager
        self._cancelled = False

    def set_download(self, url: str, output_path: str) -> None:
        """Set download parameters.

        Args:
            url: URL to download from.
            output_path: Local file path to save to.
        """
        self.url = url
        self.output_path = output_path

    def cancel(self) -> None:
        """Cancel the download operation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute the download operation."""
        if not self.url or not self.output_path:
            self.error.emit(self.url, "Missing URL or output path")
            return

        self._cancelled = False

        try:
            # Prepare headers
            headers = {}
            if self.auth_manager:
                auth_header = self.auth_manager.get_auth_header()
                if auth_header:
                    headers.update(auth_header)

            # Start download with streaming
            response = requests.get(
                self.url,
                headers=headers,
                stream=True,
                timeout=30,
            )
            response.raise_for_status()

            # Get total file size
            total_size = int(response.headers.get("content-length", 0))

            # Ensure output directory exists
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

            # Download with progress
            downloaded = 0
            with open(self.output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if self._cancelled:
                        f.close()
                        # Clean up partial file
                        if os.path.exists(self.output_path):
                            os.remove(self.output_path)
                        return

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(self.url, downloaded, total_size)

            self.finished.emit(self.url, self.output_path, True)

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Authentication required. Please log in."
            elif e.response.status_code == 403:
                # Check if this is an S3 endpoint that needs different auth
                if "eodata.dataspace.copernicus.eu" in self.url:
                    error_msg = (
                        "Access denied. This data requires S3 credentials. "
                        "Generate S3 keys from the CDSE portal."
                    )
                else:
                    error_msg = "Access denied. Check your credentials."
            self.error.emit(self.url, error_msg)

        except requests.exceptions.Timeout:
            self.error.emit(self.url, "Download timed out")

        except requests.exceptions.ConnectionError:
            self.error.emit(self.url, "Connection error")

        except OSError as e:
            self.error.emit(self.url, f"File error: {str(e)}")

        except Exception as e:
            if not self._cancelled:
                self.error.emit(self.url, str(e))


class BatchDownloadWorker(QThread):
    """Background worker for batch file downloads.

    This worker handles multiple file downloads sequentially with progress reporting.

    Signals:
        item_started: Emitted when an item download starts with (index, url).
        item_finished: Emitted when an item completes with (index, url, filepath, success).
        item_error: Emitted when an item fails with (index, url, error_message).
        item_progress: Emitted during item download with (index, url, bytes_downloaded, total_bytes).
        all_finished: Emitted when all downloads complete with (successful_count, failed_count).
    """

    item_started = pyqtSignal(int, str)  # index, url
    item_finished = pyqtSignal(int, str, str, bool)  # index, url, filepath, success
    item_error = pyqtSignal(int, str, str)  # index, url, error_message
    item_progress = pyqtSignal(int, str, int, int)  # index, url, downloaded, total
    all_finished = pyqtSignal(int, int)  # successful, failed

    def __init__(
        self,
        downloads: list = None,
        auth_manager: Optional["AuthManager"] = None,
        parent=None,
    ):
        """Initialize the batch download worker.

        Args:
            downloads: List of (url, output_path) tuples.
            auth_manager: Authentication manager for authorized downloads.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.downloads = downloads or []
        self.auth_manager = auth_manager
        self._cancelled = False

    def set_downloads(self, downloads: list) -> None:
        """Set downloads list.

        Args:
            downloads: List of (url, output_path) tuples.
        """
        self.downloads = downloads

    def cancel(self) -> None:
        """Cancel all downloads."""
        self._cancelled = True

    def run(self) -> None:
        """Execute all download operations."""
        self._cancelled = False
        successful = 0
        failed = 0

        for index, (url, output_path) in enumerate(self.downloads):
            if self._cancelled:
                break

            self.item_started.emit(index, url)

            try:
                # Prepare headers
                headers = {}
                if self.auth_manager:
                    auth_header = self.auth_manager.get_auth_header()
                    if auth_header:
                        headers.update(auth_header)

                # Start download
                response = requests.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=30,
                )
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                downloaded = 0
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if self._cancelled:
                            f.close()
                            if os.path.exists(output_path):
                                os.remove(output_path)
                            break

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            self.item_progress.emit(index, url, downloaded, total_size)

                if not self._cancelled:
                    self.item_finished.emit(index, url, output_path, True)
                    successful += 1

            except requests.exceptions.HTTPError as e:
                if not self._cancelled:
                    error_msg = f"HTTP {e.response.status_code}"
                    if e.response.status_code == 401:
                        error_msg = "Authentication required"
                    elif e.response.status_code == 403:
                        if "eodata.dataspace.copernicus.eu" in url:
                            error_msg = "Requires S3 credentials (not OAuth)"
                        else:
                            error_msg = "Access denied"
                    self.item_error.emit(index, url, error_msg)
                    failed += 1

            except Exception as e:
                if not self._cancelled:
                    self.item_error.emit(index, url, str(e))
                    failed += 1

        self.all_finished.emit(successful, failed)
