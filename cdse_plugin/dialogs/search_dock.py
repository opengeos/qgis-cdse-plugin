"""Search dock widget for CDSE Plugin."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

try:
    from qgis.core import QgsProject, QgsRectangle
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtWidgets import (
        QApplication,
        QComboBox,
        QDateEdit,
        QDockWidget,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSlider,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    pass

if TYPE_CHECKING:
    from ..api.models import SearchParameters
    from ..api.stac_client import STACClient

from ..api.models import SearchParameters
from ..utils.config import (
    DEFAULT_CLOUD_COVER,
    DEFAULT_DATE_RANGE_DAYS,
    DEFAULT_MAX_RESULTS,
)


class SearchDock(QDockWidget):
    """Dock widget for search parameters.

    This dock provides UI for setting search parameters including
    collection, date range, bounding box, and cloud cover.

    Signals:
        search_requested: Emitted when search is triggered with SearchParameters.
        bbox_from_canvas_requested: Emitted when user wants bbox from map canvas.
    """

    search_requested = pyqtSignal(object)  # SearchParameters
    bbox_from_canvas_requested = pyqtSignal()

    def __init__(self, iface, stac_client: Optional["STACClient"] = None, parent=None):
        """Initialize the search dock.

        Args:
            iface: QGIS interface instance.
            stac_client: STAC client for fetching collections.
            parent: Parent widget.
        """
        super().__init__("CDSE Search", parent)
        self.iface = iface
        self.stac_client = stac_client
        self._collections_by_category: Dict[str, List] = {}
        self._setup_ui()

    def set_stac_client(self, client: "STACClient") -> None:
        """Set the STAC client and load collections.

        Args:
            client: STAC client instance.
        """
        self.stac_client = client
        self.load_collections()

    def _setup_ui(self) -> None:
        """Set up the dock UI."""
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Collection selection
        collection_group = QGroupBox("Collection")
        collection_layout = QVBoxLayout(collection_group)

        # Refresh button and category
        category_row = QHBoxLayout()
        category_row.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        category_row.addWidget(self.category_combo, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setMaximumWidth(60)
        self.refresh_btn.clicked.connect(self._refresh_collections)
        category_row.addWidget(self.refresh_btn)

        collection_layout.addLayout(category_row)

        # Collection dropdown
        collection_row = QHBoxLayout()
        collection_row.addWidget(QLabel("Collection:"))
        self.collection_combo = QComboBox()
        self.collection_combo.currentIndexChanged.connect(self._on_collection_changed)
        collection_row.addWidget(self.collection_combo, 1)
        collection_layout.addLayout(collection_row)

        layout.addWidget(collection_group)

        # Date range
        date_group = QGroupBox("Date Range")
        date_layout = QFormLayout(date_group)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(
            (datetime.now() - timedelta(days=DEFAULT_DATE_RANGE_DAYS)).date()
        )
        date_layout.addRow("Start:", self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(datetime.now().date())
        date_layout.addRow("End:", self.end_date)

        layout.addWidget(date_group)

        # Bounding box
        bbox_group = QGroupBox("Bounding Box")
        bbox_layout = QVBoxLayout(bbox_group)

        bbox_form = QFormLayout()

        self.minx_edit = QLineEdit()
        self.minx_edit.setPlaceholderText("-180")
        bbox_form.addRow("Min X:", self.minx_edit)

        self.miny_edit = QLineEdit()
        self.miny_edit.setPlaceholderText("-90")
        bbox_form.addRow("Min Y:", self.miny_edit)

        self.maxx_edit = QLineEdit()
        self.maxx_edit.setPlaceholderText("180")
        bbox_form.addRow("Max X:", self.maxx_edit)

        self.maxy_edit = QLineEdit()
        self.maxy_edit.setPlaceholderText("90")
        bbox_form.addRow("Max Y:", self.maxy_edit)

        bbox_layout.addLayout(bbox_form)

        self.bbox_from_canvas_btn = QPushButton("Get from Map Canvas")
        self.bbox_from_canvas_btn.clicked.connect(self._get_bbox_from_canvas)
        bbox_layout.addWidget(self.bbox_from_canvas_btn)

        layout.addWidget(bbox_group)

        # Cloud cover
        self.cloud_group = QGroupBox("Cloud Cover")
        cloud_layout = QVBoxLayout(self.cloud_group)

        slider_layout = QHBoxLayout()

        self.cloud_slider = QSlider(Qt.Horizontal)
        self.cloud_slider.setMinimum(0)
        self.cloud_slider.setMaximum(100)
        self.cloud_slider.setValue(DEFAULT_CLOUD_COVER)
        self.cloud_slider.valueChanged.connect(self._on_cloud_slider_changed)
        slider_layout.addWidget(self.cloud_slider)

        self.cloud_label = QLabel(f"{DEFAULT_CLOUD_COVER}%")
        self.cloud_label.setMinimumWidth(40)
        slider_layout.addWidget(self.cloud_label)

        cloud_layout.addLayout(slider_layout)

        layout.addWidget(self.cloud_group)

        # Max results
        results_group = QGroupBox("Results")
        results_layout = QFormLayout(results_group)

        self.max_results_spin = QSpinBox()
        self.max_results_spin.setMinimum(1)
        self.max_results_spin.setMaximum(1000)
        self.max_results_spin.setValue(DEFAULT_MAX_RESULTS)
        results_layout.addRow("Max results:", self.max_results_spin)

        layout.addWidget(results_group)

        # Search button
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._on_search)
        layout.addWidget(self.search_btn)

        # Status label
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Stretch at bottom
        layout.addStretch()

        self.setWidget(main_widget)

    def load_collections(self) -> None:
        """Load collections from the STAC API."""
        if not self.stac_client:
            self.status_label.setText("No STAC client available")
            return

        self.status_label.setText("Loading collections...")
        self.refresh_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            self._collections_by_category = (
                self.stac_client.get_collections_by_category(use_cache=False)
            )
            self._populate_categories()
            self.status_label.setText(
                f"Loaded {sum(len(c) for c in self._collections_by_category.values())} collections"
            )
        except Exception as e:
            self.status_label.setText(f"Error loading collections: {str(e)}")
        finally:
            self.refresh_btn.setEnabled(True)

    def _populate_categories(self) -> None:
        """Populate the category combo box."""
        self.category_combo.blockSignals(True)
        self.category_combo.clear()

        # Add "All" option
        self.category_combo.addItem("All")

        # Add categories
        for category in sorted(self._collections_by_category.keys()):
            count = len(self._collections_by_category[category])
            self.category_combo.addItem(f"{category} ({count})")

        self.category_combo.blockSignals(False)

        # Trigger population of collections
        self._on_category_changed(self.category_combo.currentText())

    def _on_category_changed(self, category_text: str) -> None:
        """Handle category selection change.

        Args:
            category_text: Selected category text.
        """
        self.collection_combo.blockSignals(True)
        self.collection_combo.clear()

        if category_text == "All":
            # Show all collections
            for category, collections in sorted(self._collections_by_category.items()):
                for collection in collections:
                    display_name = collection.title or collection.id
                    self.collection_combo.addItem(display_name, collection.id)
        else:
            # Extract category name (remove count)
            category = category_text.split(" (")[0]
            collections = self._collections_by_category.get(category, [])
            for collection in collections:
                display_name = collection.title or collection.id
                self.collection_combo.addItem(display_name, collection.id)

        self.collection_combo.blockSignals(False)

        # Trigger collection changed
        if self.collection_combo.count() > 0:
            self._on_collection_changed(0)

    def _on_collection_changed(self, index: int) -> None:
        """Handle collection selection change.

        Args:
            index: Selected index.
        """
        collection_id = self.collection_combo.currentData()

        # Enable/disable cloud cover based on collection
        if collection_id and self.stac_client:
            supports_cloud = self.stac_client.supports_cloud_cover(collection_id)
            self.cloud_group.setEnabled(supports_cloud)
        else:
            self.cloud_group.setEnabled(False)

    def _refresh_collections(self) -> None:
        """Refresh collections from the API."""
        if self.stac_client:
            self.stac_client.clear_cache()
        self.load_collections()

    def _on_cloud_slider_changed(self, value: int) -> None:
        """Handle cloud cover slider change.

        Args:
            value: New slider value.
        """
        self.cloud_label.setText(f"{value}%")

    def _get_bbox_from_canvas(self) -> None:
        """Get bounding box from current map canvas extent."""
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()

        # Transform to EPSG:4326 if needed
        canvas_crs = canvas.mapSettings().destinationCrs()
        if canvas_crs.authid() != "EPSG:4326":
            from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform

            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(canvas_crs, wgs84, QgsProject.instance())
            extent = transform.transformBoundingBox(extent)

        self.minx_edit.setText(f"{extent.xMinimum():.6f}")
        self.miny_edit.setText(f"{extent.yMinimum():.6f}")
        self.maxx_edit.setText(f"{extent.xMaximum():.6f}")
        self.maxy_edit.setText(f"{extent.yMaximum():.6f}")

    def _on_search(self) -> None:
        """Handle search button click."""
        params = self.get_search_parameters()
        if params:
            self.search_requested.emit(params)

    def get_search_parameters(self) -> Optional[SearchParameters]:
        """Get current search parameters.

        Returns:
            SearchParameters object or None if validation fails.
        """
        collection_id = self.collection_combo.currentData()
        if not collection_id:
            self.status_label.setText("Please select a collection")
            return None

        # Parse bbox
        bbox = None
        try:
            minx = self.minx_edit.text().strip()
            miny = self.miny_edit.text().strip()
            maxx = self.maxx_edit.text().strip()
            maxy = self.maxy_edit.text().strip()

            if minx and miny and maxx and maxy:
                bbox = [float(minx), float(miny), float(maxx), float(maxy)]
        except ValueError:
            self.status_label.setText("Invalid bounding box values")
            return None

        # Parse dates
        start_date = datetime.combine(
            self.start_date.date().toPyDate(), datetime.min.time()
        )
        end_date = datetime.combine(
            self.end_date.date().toPyDate(), datetime.max.time()
        )

        if start_date > end_date:
            self.status_label.setText("Start date must be before end date")
            return None

        # Cloud cover (only if enabled)
        max_cloud_cover = None
        if self.cloud_group.isEnabled():
            max_cloud_cover = self.cloud_slider.value()

        self.status_label.setText("")

        return SearchParameters(
            collection=collection_id,
            bbox=bbox,
            start_date=start_date,
            end_date=end_date,
            max_cloud_cover=max_cloud_cover,
            max_results=self.max_results_spin.value(),
            api="stac",
        )

    def set_status(self, message: str) -> None:
        """Set the status message.

        Args:
            message: Status message to display.
        """
        self.status_label.setText(message)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the search controls.

        Args:
            enabled: Whether to enable controls.
        """
        self.search_btn.setEnabled(enabled)
        self.category_combo.setEnabled(enabled)
        self.collection_combo.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
