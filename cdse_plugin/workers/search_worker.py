"""Search worker thread for CDSE Plugin."""

from typing import TYPE_CHECKING, List, Optional

try:
    from qgis.PyQt.QtCore import QThread, pyqtSignal
except ImportError:
    from PyQt5.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from ..api.models import SearchParameters, SearchResult
    from ..api.odata_client import ODataClient
    from ..api.stac_client import STACClient


class SearchWorker(QThread):
    """Background worker for search operations.

    This worker runs search queries in a separate thread to keep the UI responsive.

    Signals:
        finished: Emitted when search completes with list of results.
        error: Emitted when an error occurs with error message.
        progress: Emitted during search with progress message.
    """

    finished = pyqtSignal(list)  # List[SearchResult]
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(
        self,
        stac_client: Optional["STACClient"] = None,
        odata_client: Optional["ODataClient"] = None,
        params: Optional["SearchParameters"] = None,
        parent=None,
    ):
        """Initialize the search worker.

        Args:
            stac_client: STAC API client instance.
            odata_client: OData API client instance.
            params: Search parameters.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.stac_client = stac_client
        self.odata_client = odata_client
        self.params = params
        self._cancelled = False

    def set_params(self, params: "SearchParameters") -> None:
        """Set search parameters.

        Args:
            params: Search parameters.
        """
        self.params = params

    def cancel(self) -> None:
        """Cancel the search operation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute the search operation."""
        if not self.params:
            self.error.emit("No search parameters provided")
            return

        self._cancelled = False

        try:
            self.progress.emit(f"Searching {self.params.collection}...")

            results: List["SearchResult"] = []

            if self.params.api == "stac" and self.stac_client:
                results = self.stac_client.search(self.params)
            elif self.params.api == "odata" and self.odata_client:
                results = self.odata_client.search(self.params)
            else:
                self.error.emit(f"No client available for API: {self.params.api}")
                return

            if self._cancelled:
                self.progress.emit("Search cancelled")
                return

            self.progress.emit(f"Found {len(results)} results")
            self.finished.emit(results)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))
