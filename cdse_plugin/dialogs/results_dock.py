"""Results dock widget for CDSE Plugin."""

from typing import TYPE_CHECKING, Dict, List, Optional

try:
    from qgis.PyQt.QtCore import QSize, Qt, pyqtSignal
    from qgis.PyQt.QtGui import QIcon, QPixmap
    from qgis.PyQt.QtWidgets import (
        QAbstractItemView,
        QAction,
        QDockWidget,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMenu,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    pass

if TYPE_CHECKING:
    from ..api.models import SearchResult

from ..utils.config import THUMBNAIL_SIZE


class NumericTableWidgetItem(QTableWidgetItem):
    """Table widget item that sorts numerically instead of alphabetically."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        """Compare items numerically.

        Args:
            other: Other item to compare with.

        Returns:
            True if this item is less than the other.
        """
        try:
            return float(self.text() or 0) < float(other.text() or 0)
        except ValueError:
            return self.text() < other.text()


class ResultsDock(QDockWidget):
    """Dock widget for displaying search results.

    This dock shows search results in a table with thumbnails,
    allowing selection for download and visualization.

    Signals:
        download_requested: Emitted when download is requested with list of SearchResult.
        zoom_to_requested: Emitted when zoom to item is requested with SearchResult.
        show_footprint_requested: Emitted when footprint display is requested with SearchResult.
        details_requested: Emitted when details are requested with SearchResult.
    """

    download_requested = pyqtSignal(list)  # List[SearchResult]
    zoom_to_requested = pyqtSignal(object)  # SearchResult
    show_footprint_requested = pyqtSignal(object)  # SearchResult
    details_requested = pyqtSignal(object)  # SearchResult
    view_cog_requested = pyqtSignal(object)  # SearchResult
    selection_changed = pyqtSignal(list)  # List[str] - list of selected result IDs

    def __init__(self, parent=None):
        """Initialize the results dock.

        Args:
            parent: Parent widget.
        """
        super().__init__("CDSE Results", parent)
        self._results: List["SearchResult"] = []
        self._thumbnails: Dict[str, QPixmap] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dock UI."""
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["", "Name", "Date", "Cloud %", "Size (MB)", "Collection"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._on_double_click)

        # Enable sorting by clicking on header
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)

        # Set icon size to match thumbnail size
        self.table.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, THUMBNAIL_SIZE + 8)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

        # Button bar
        button_layout = QHBoxLayout()

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self._on_download_selected)
        self.download_btn.setEnabled(False)
        button_layout.addWidget(self.download_btn)

        self.view_cog_btn = QPushButton("View COG")
        self.view_cog_btn.setToolTip("Stream COG assets without downloading")
        self.view_cog_btn.clicked.connect(self._on_view_cog)
        self.view_cog_btn.setEnabled(False)
        button_layout.addWidget(self.view_cog_btn)

        self.show_footprints_btn = QPushButton("Show All Footprints")
        self.show_footprints_btn.clicked.connect(self._on_show_all_footprints)
        self.show_footprints_btn.setEnabled(False)
        button_layout.addWidget(self.show_footprints_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_results)
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        self.setWidget(main_widget)

        # Connect selection change
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def set_results(self, results: List["SearchResult"]) -> None:
        """Set the search results to display.

        Args:
            results: List of SearchResult objects.
        """
        self._results = results
        self._thumbnails.clear()
        self._populate_table()

        self.status_label.setText(f"{len(results)} results")
        self.show_footprints_btn.setEnabled(len(results) > 0)

    def _populate_table(self) -> None:
        """Populate the results table."""
        # Disable sorting while populating
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._results))

        for row, result in enumerate(self._results):
            # Thumbnail placeholder - store result ID for mapping
            thumb_item = QTableWidgetItem()
            thumb_item.setData(Qt.ItemDataRole.UserRole, result.id)
            self.table.setItem(row, 0, thumb_item)
            self.table.setRowHeight(row, THUMBNAIL_SIZE + 8)

            # Name
            name_item = QTableWidgetItem(result.name)
            name_item.setToolTip(result.name)
            name_item.setData(Qt.ItemDataRole.UserRole, result.id)
            self.table.setItem(row, 1, name_item)

            # Date
            date_str = ""
            if result.datetime:
                date_str = result.datetime.strftime("%Y-%m-%d %H:%M")
            date_item = QTableWidgetItem(date_str)
            date_item.setData(Qt.ItemDataRole.UserRole, result.id)
            self.table.setItem(row, 2, date_item)

            # Cloud cover - use numeric sorting
            cloud_item = NumericTableWidgetItem()
            if result.cloud_cover is not None:
                cloud_item.setText(f"{result.cloud_cover:.1f}")
            cloud_item.setData(Qt.ItemDataRole.UserRole, result.id)
            self.table.setItem(row, 3, cloud_item)

            # Size - use numeric sorting
            size_item = NumericTableWidgetItem()
            if result.size_mb is not None:
                size_item.setText(f"{result.size_mb:.1f}")
            size_item.setData(Qt.ItemDataRole.UserRole, result.id)
            self.table.setItem(row, 4, size_item)

            # Collection
            collection_item = QTableWidgetItem(result.collection)
            collection_item.setData(Qt.ItemDataRole.UserRole, result.id)
            self.table.setItem(row, 5, collection_item)

        # Re-enable sorting
        self.table.setSortingEnabled(True)

    def set_thumbnail(self, item_id: str, pixmap: QPixmap) -> None:
        """Set a thumbnail for an item.

        Args:
            item_id: ID of the item.
            pixmap: Thumbnail pixmap.
        """
        self._thumbnails[item_id] = pixmap

        # Find row and update
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == item_id:
                item.setIcon(QIcon(pixmap))
                break

    def get_selected_results(self) -> List["SearchResult"]:
        """Get the currently selected results.

        Returns:
            List of selected SearchResult objects.
        """
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        return [self._results[row] for row in sorted(selected_rows)]

    def get_result_by_id(self, item_id: str) -> Optional["SearchResult"]:
        """Get a result by its ID.

        Args:
            item_id: ID of the result.

        Returns:
            SearchResult or None if not found.
        """
        for result in self._results:
            if result.id == item_id:
                return result
        return None

    def clear_results(self) -> None:
        """Clear all results."""
        self._results.clear()
        self._thumbnails.clear()
        self.table.setRowCount(0)
        self.status_label.setText("")
        self.download_btn.setEnabled(False)
        self.show_footprints_btn.setEnabled(False)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        has_selection = len(self.table.selectedItems()) > 0
        self.download_btn.setEnabled(has_selection)

        # Emit selection changed with list of selected result IDs
        selected_ids = []
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        for row in selected_rows:
            item = self.table.item(row, 0)
            if item:
                result_id = item.data(Qt.ItemDataRole.UserRole)
                if result_id:
                    selected_ids.append(result_id)
        self.selection_changed.emit(selected_ids)

        # Check if any selected result has COG assets
        has_cog = False
        selected_results = self.get_selected_results()
        for result in selected_results:
            if result.get_cog_assets():
                has_cog = True
                break
        self.view_cog_btn.setEnabled(has_cog)

    def _on_download_selected(self) -> None:
        """Handle download selected button click."""
        selected = self.get_selected_results()
        if selected:
            self.download_requested.emit(selected)

    def _on_view_cog(self) -> None:
        """Handle view COG button click."""
        selected = self.get_selected_results()
        # Find the first result with COG assets
        for result in selected:
            if result.get_cog_assets():
                self.view_cog_requested.emit(result)
                break

    def _on_show_all_footprints(self) -> None:
        """Handle show all footprints button click."""
        for result in self._results:
            self.show_footprint_requested.emit(result)

    def _on_double_click(self, index) -> None:
        """Handle double click on table row.

        Args:
            index: Model index of clicked item.
        """
        row = index.row()
        if 0 <= row < len(self._results):
            result = self._results[row]
            self.zoom_to_requested.emit(result)

    def _show_context_menu(self, position) -> None:
        """Show context menu for table.

        Args:
            position: Click position.
        """
        item = self.table.itemAt(position)
        if not item:
            return

        row = item.row()
        if row < 0 or row >= len(self._results):
            return

        result = self._results[row]

        menu = QMenu(self)

        zoom_action = QAction("Zoom to", self)
        zoom_action.triggered.connect(lambda: self.zoom_to_requested.emit(result))
        menu.addAction(zoom_action)

        footprint_action = QAction("Show Footprint", self)
        footprint_action.triggered.connect(
            lambda: self.show_footprint_requested.emit(result)
        )
        menu.addAction(footprint_action)

        menu.addSeparator()

        # View COG option (for streaming without download)
        cog_assets = result.get_cog_assets()
        if cog_assets:
            view_cog_action = QAction("View COG (Stream)", self)
            view_cog_action.triggered.connect(
                lambda: self.view_cog_requested.emit(result)
            )
            menu.addAction(view_cog_action)

        download_action = QAction("Download", self)
        download_action.triggered.connect(
            lambda: self.download_requested.emit([result])
        )
        menu.addAction(download_action)

        menu.addSeparator()

        details_action = QAction("View Details", self)
        details_action.triggered.connect(lambda: self.details_requested.emit(result))
        menu.addAction(details_action)

        menu.exec(self.table.mapToGlobal(position))

    def get_thumbnail_requests(self) -> List[tuple]:
        """Get list of thumbnail requests for results without thumbnails.

        Returns:
            List of (item_id, thumbnail_url) tuples.
        """
        requests = []
        for result in self._results:
            if result.id not in self._thumbnails and result.thumbnail_url:
                requests.append((result.id, result.thumbnail_url))
        return requests

    def select_by_ids(self, result_ids: List[str], emit_signal: bool = False) -> None:
        """Select table rows by result IDs.

        Args:
            result_ids: List of result IDs to select.
            emit_signal: Whether to emit selection_changed signal.
        """
        # Block signals temporarily if we don't want to emit
        if not emit_signal:
            self.table.blockSignals(True)

        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                result_id = item.data(Qt.ItemDataRole.UserRole)
                if result_id in result_ids:
                    self.table.selectRow(row)

        if not emit_signal:
            self.table.blockSignals(False)
            # Still need to update button state
            has_selection = len(self.table.selectedItems()) > 0
            self.download_btn.setEnabled(has_selection)

    @property
    def results(self) -> List["SearchResult"]:
        """Get all results.

        Returns:
            List of SearchResult objects.
        """
        return self._results.copy()
