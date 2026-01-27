"""Thumbnail worker thread for CDSE Plugin."""

from typing import Optional

import requests

try:
    from qgis.PyQt.QtCore import QThread, pyqtSignal
    from qgis.PyQt.QtGui import QPixmap
except ImportError:
    from PyQt5.QtCore import QThread, pyqtSignal
    from PyQt5.QtGui import QPixmap


class ThumbnailWorker(QThread):
    """Background worker for fetching thumbnails.

    This worker fetches thumbnail images in a separate thread.

    Signals:
        finished: Emitted when thumbnail is fetched with (item_id, pixmap).
        error: Emitted when an error occurs with (item_id, error_message).
    """

    finished = pyqtSignal(str, QPixmap)  # item_id, pixmap
    error = pyqtSignal(str, str)  # item_id, error_message

    def __init__(
        self,
        item_id: str = "",
        url: str = "",
        size: int = 64,
        parent=None,
    ):
        """Initialize the thumbnail worker.

        Args:
            item_id: ID of the item this thumbnail belongs to.
            url: URL of the thumbnail image.
            size: Target size for the thumbnail.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.item_id = item_id
        self.url = url
        self.size = size
        self._cancelled = False

    def set_thumbnail(self, item_id: str, url: str) -> None:
        """Set thumbnail parameters.

        Args:
            item_id: ID of the item this thumbnail belongs to.
            url: URL of the thumbnail image.
        """
        self.item_id = item_id
        self.url = url

    def cancel(self) -> None:
        """Cancel the thumbnail fetch."""
        self._cancelled = True

    def run(self) -> None:
        """Fetch the thumbnail image."""
        if not self.url:
            self.error.emit(self.item_id, "No thumbnail URL")
            return

        self._cancelled = False

        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()

            if self._cancelled:
                return

            # Load image data into QPixmap
            pixmap = QPixmap()
            if pixmap.loadFromData(response.content):
                # Scale to target size
                scaled = pixmap.scaled(
                    self.size,
                    self.size,
                    aspectRatioMode=1,  # Qt.KeepAspectRatio
                    transformMode=1,  # Qt.SmoothTransformation
                )
                self.finished.emit(self.item_id, scaled)
            else:
                self.error.emit(self.item_id, "Failed to load image")

        except requests.exceptions.Timeout:
            self.error.emit(self.item_id, "Timeout")
        except requests.exceptions.RequestException as e:
            if not self._cancelled:
                self.error.emit(self.item_id, str(e))
        except Exception as e:
            if not self._cancelled:
                self.error.emit(self.item_id, str(e))


class ThumbnailBatchWorker(QThread):
    """Background worker for fetching multiple thumbnails.

    This worker fetches multiple thumbnail images sequentially.

    Signals:
        thumbnail_ready: Emitted when a thumbnail is fetched with (item_id, pixmap).
        thumbnail_error: Emitted when an error occurs with (item_id, error_message).
        all_finished: Emitted when all thumbnails are processed.
    """

    thumbnail_ready = pyqtSignal(str, QPixmap)  # item_id, pixmap
    thumbnail_error = pyqtSignal(str, str)  # item_id, error_message
    all_finished = pyqtSignal()

    def __init__(
        self,
        thumbnails: Optional[list] = None,
        size: int = 64,
        parent=None,
    ):
        """Initialize the batch thumbnail worker.

        Args:
            thumbnails: List of (item_id, url) tuples.
            size: Target size for thumbnails.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.thumbnails = thumbnails or []
        self.size = size
        self._cancelled = False

    def set_thumbnails(self, thumbnails: list) -> None:
        """Set thumbnails to fetch.

        Args:
            thumbnails: List of (item_id, url) tuples.
        """
        self.thumbnails = thumbnails

    def cancel(self) -> None:
        """Cancel all thumbnail fetches."""
        self._cancelled = True

    def run(self) -> None:
        """Fetch all thumbnails."""
        self._cancelled = False

        for item_id, url in self.thumbnails:
            if self._cancelled:
                break

            if not url:
                continue

            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                if self._cancelled:
                    break

                pixmap = QPixmap()
                if pixmap.loadFromData(response.content):
                    scaled = pixmap.scaled(
                        self.size,
                        self.size,
                        aspectRatioMode=1,
                        transformMode=1,
                    )
                    self.thumbnail_ready.emit(item_id, scaled)
                else:
                    self.thumbnail_error.emit(item_id, "Failed to load image")

            except Exception as e:
                if not self._cancelled:
                    self.thumbnail_error.emit(item_id, str(e))

        if not self._cancelled:
            self.all_finished.emit()
