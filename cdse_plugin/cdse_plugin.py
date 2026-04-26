"""Main plugin class for CDSE Plugin."""

import os
from typing import List, Optional

try:
    from qgis.core import QgsProject
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QIcon
    from qgis.PyQt.QtWidgets import QAction, QMessageBox
except ImportError:
    pass

from .api.auth import AuthManager
from .api.models import SearchParameters, SearchResult
from .api.odata_client import ODataClient
from .api.stac_client import STACClient
from .dialogs.cog_viewer_dialog import show_cog_viewer
from .dialogs.download_dialog import DownloadDialog
from .dialogs.results_dock import ResultsDock
from .dialogs.search_dock import SearchDock
from .dialogs.settings_dock import SettingsDock
from .dialogs.update_checker import check_for_updates, show_update_dialog
from .utils.layer_utils import (
    add_footprint_layer,
    get_selected_feature_ids,
    select_features_by_id,
    zoom_to_feature,
)
from .workers.search_worker import SearchWorker
from .workers.thumbnail_worker import ThumbnailBatchWorker


class CDSEPlugin:
    """Main plugin class for CDSE Plugin.

    This class handles plugin initialization, UI setup, and coordination
    between the various components.

    Attributes:
        iface: QGIS interface instance.
        plugin_dir: Path to the plugin directory.
        auth_manager: Authentication manager instance.
        stac_client: STAC API client instance.
        odata_client: OData API client instance.
    """

    def __init__(self, iface):
        """Initialize the plugin.

        Args:
            iface: QGIS interface instance.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # API clients
        self.auth_manager = AuthManager()
        self.stac_client = STACClient(auth_manager=self.auth_manager)
        self.odata_client = ODataClient(auth_manager=self.auth_manager)

        # UI components
        self.search_dock: Optional[SearchDock] = None
        self.results_dock: Optional[ResultsDock] = None
        self.settings_dock: Optional[SettingsDock] = None

        # Workers
        self.search_worker: Optional[SearchWorker] = None
        self.thumbnail_worker: Optional[ThumbnailBatchWorker] = None

        # Actions
        self.actions: List[QAction] = []
        self.menu_name = "CDSE"

        # Footprint layer
        self._footprint_layer = None

        # Flag to prevent circular selection updates
        self._updating_selection = False

        # Keep reference to download dialog to prevent garbage collection
        self._download_dialog: Optional[DownloadDialog] = None

    def initGui(self) -> None:
        """Initialize the plugin GUI."""
        # Apply GDAL configuration for S3 access (uses stored/env credentials)
        self.auth_manager.apply_gdal_config()

        # Create toolbar actions
        icon_path = os.path.join(self.plugin_dir, "icons", "icon.svg")

        # Main action (toggle search dock)
        self.action_search = QAction(
            QIcon(icon_path), "CDSE Search", self.iface.mainWindow()
        )
        self.action_search.setCheckable(True)
        self.action_search.triggered.connect(self._toggle_search_dock)
        self.iface.addToolBarIcon(self.action_search)
        self.iface.addPluginToWebMenu(self.menu_name, self.action_search)
        self.actions.append(self.action_search)

        # Settings action
        settings_icon = os.path.join(self.plugin_dir, "icons", "settings.svg")
        self.action_settings = QAction(
            QIcon(settings_icon), "CDSE Settings", self.iface.mainWindow()
        )
        self.action_settings.setCheckable(True)
        self.action_settings.triggered.connect(self._toggle_settings_dock)
        self.iface.addPluginToWebMenu(self.menu_name, self.action_settings)
        self.actions.append(self.action_settings)

        # Check for Updates action
        self.action_update = QAction("Check for Updates...", self.iface.mainWindow())
        self.action_update.triggered.connect(self._check_for_updates)
        self.iface.addPluginToWebMenu(self.menu_name, self.action_update)
        self.actions.append(self.action_update)

        # About action
        about_icon = os.path.join(self.plugin_dir, "icons", "about.svg")
        self.action_about = QAction(
            QIcon(about_icon), "About CDSE Plugin", self.iface.mainWindow()
        )
        self.action_about.triggered.connect(self._show_about)
        self.iface.addPluginToWebMenu(self.menu_name, self.action_about)
        self.actions.append(self.action_about)

        # Check for updates at startup (silent)
        check_for_updates(self.iface.mainWindow(), silent=True)

    def unload(self) -> None:
        """Unload the plugin."""
        # Remove toolbar and menu items
        for action in self.actions:
            self.iface.removePluginWebMenu(self.menu_name, action)
            self.iface.removeToolBarIcon(action)

        # Close docks
        if self.search_dock:
            self.iface.removeDockWidget(self.search_dock)
            self.search_dock.deleteLater()
            self.search_dock = None

        if self.results_dock:
            self.iface.removeDockWidget(self.results_dock)
            self.results_dock.deleteLater()
            self.results_dock = None

        if self.settings_dock:
            self.iface.removeDockWidget(self.settings_dock)
            self.settings_dock.deleteLater()
            self.settings_dock = None

        # Cancel workers
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()
            self.search_worker.wait()

        if self.thumbnail_worker and self.thumbnail_worker.isRunning():
            self.thumbnail_worker.cancel()
            self.thumbnail_worker.wait()

    def _toggle_search_dock(self, checked: bool) -> None:
        """Toggle the search dock visibility.

        Args:
            checked: Whether the action is checked.
        """
        if checked:
            if not self.search_dock:
                self._create_search_dock()
            self.search_dock.show()

            # Also show results dock
            if not self.results_dock:
                self._create_results_dock()
            self.results_dock.show()
        else:
            if self.search_dock:
                self.search_dock.hide()
            if self.results_dock:
                self.results_dock.hide()

    def _toggle_settings_dock(self, checked: bool) -> None:
        """Toggle the settings dock visibility.

        Args:
            checked: Whether the action is checked.
        """
        if checked:
            if not self.settings_dock:
                self._create_settings_dock()
            self.settings_dock.show()
        else:
            if self.settings_dock:
                self.settings_dock.hide()

    def _create_search_dock(self) -> None:
        """Create the search dock widget."""
        self.search_dock = SearchDock(
            self.iface, stac_client=self.stac_client, parent=self.iface.mainWindow()
        )
        self.search_dock.search_requested.connect(self._on_search_requested)
        self.search_dock.visibilityChanged.connect(
            lambda v: self.action_search.setChecked(v)
        )
        self.iface.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.search_dock
        )

        # Load collections from API
        self.search_dock.load_collections()

    def _create_results_dock(self) -> None:
        """Create the results dock widget."""
        self.results_dock = ResultsDock(self.iface.mainWindow())
        self.results_dock.download_requested.connect(self._on_download_requested)
        self.results_dock.zoom_to_requested.connect(self._on_zoom_to_requested)
        self.results_dock.show_footprint_requested.connect(
            self._on_show_footprint_requested
        )
        self.results_dock.details_requested.connect(self._on_details_requested)
        self.results_dock.view_cog_requested.connect(self._on_view_cog_requested)
        self.results_dock.selection_changed.connect(self._on_table_selection_changed)
        self.iface.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.results_dock
        )

    def _create_settings_dock(self) -> None:
        """Create the settings dock widget."""
        self.settings_dock = SettingsDock(self.auth_manager, self.iface.mainWindow())
        self.settings_dock.visibilityChanged.connect(
            lambda v: self.action_settings.setChecked(v)
        )
        self.iface.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.settings_dock
        )

    def _on_search_requested(self, params: SearchParameters) -> None:
        """Handle search request.

        Args:
            params: Search parameters.
        """
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()
            self.search_worker.wait()

        # Update UI
        if self.search_dock:
            self.search_dock.set_status("Searching...")
            self.search_dock.set_enabled(False)

        # Create and start worker
        self.search_worker = SearchWorker(
            stac_client=self.stac_client,
            odata_client=self.odata_client,
            params=params,
            parent=self.iface.mainWindow(),
        )
        self.search_worker.finished.connect(self._on_search_finished)
        self.search_worker.error.connect(self._on_search_error)
        self.search_worker.progress.connect(self._on_search_progress)
        self.search_worker.start()

    def _on_search_finished(self, results: List[SearchResult]) -> None:
        """Handle search completion.

        Args:
            results: List of search results.
        """
        if self.search_dock:
            self.search_dock.set_status(f"Found {len(results)} results")
            self.search_dock.set_enabled(True)

        if self.results_dock:
            self.results_dock.set_results(results)

            # Start thumbnail fetching
            thumbnail_requests = self.results_dock.get_thumbnail_requests()
            if thumbnail_requests:
                self._fetch_thumbnails(thumbnail_requests)

        # Add footprints to map
        if results:
            self._add_footprints(results)

    def _on_search_error(self, error: str) -> None:
        """Handle search error.

        Args:
            error: Error message.
        """
        if self.search_dock:
            self.search_dock.set_status(f"Error: {error}")
            self.search_dock.set_enabled(True)

        QMessageBox.warning(
            self.iface.mainWindow(), "Search Error", f"Search failed: {error}"
        )

    def _on_search_progress(self, message: str) -> None:
        """Handle search progress update.

        Args:
            message: Progress message.
        """
        if self.search_dock:
            self.search_dock.set_status(message)

    def _fetch_thumbnails(self, requests: List[tuple]) -> None:
        """Fetch thumbnails for results.

        Args:
            requests: List of (item_id, url) tuples.
        """
        if self.thumbnail_worker and self.thumbnail_worker.isRunning():
            self.thumbnail_worker.cancel()
            self.thumbnail_worker.wait()

        size = 64
        if self.settings_dock:
            size = self.settings_dock.get_thumbnail_size()

        self.thumbnail_worker = ThumbnailBatchWorker(
            thumbnails=requests, size=size, parent=self.iface.mainWindow()
        )
        self.thumbnail_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self.thumbnail_worker.start()

    def _on_thumbnail_ready(self, item_id: str, pixmap) -> None:
        """Handle thumbnail ready.

        Args:
            item_id: Item ID.
            pixmap: Thumbnail pixmap.
        """
        if self.results_dock:
            self.results_dock.set_thumbnail(item_id, pixmap)

    def _add_footprints(self, results: List[SearchResult]) -> None:
        """Add search result footprints to the map.

        Args:
            results: List of search results.
        """
        # Remove existing footprint layer
        if self._footprint_layer:
            try:
                self._footprint_layer.selectionChanged.disconnect(
                    self._on_layer_selection_changed
                )
            except TypeError:
                pass
            project = QgsProject.instance()
            project.removeMapLayer(self._footprint_layer.id())
            self._footprint_layer = None

        # Get styling from settings
        color = "#3388ff"
        opacity = 0.3
        if self.settings_dock:
            color = self.settings_dock.get_footprint_color()
            opacity = self.settings_dock.get_footprint_opacity()

        # Add new layer
        from .utils.layer_utils import add_footprint_layer, style_footprint_layer

        self._footprint_layer = add_footprint_layer(
            results, layer_name="CDSE Search Results"
        )
        style_footprint_layer(self._footprint_layer, color=color, opacity=opacity)

        # Connect selection changed signal for bidirectional highlighting
        self._footprint_layer.selectionChanged.connect(self._on_layer_selection_changed)

        # Zoom to layer
        from .utils.layer_utils import zoom_to_layer

        zoom_to_layer(self._footprint_layer, self.iface)

    def _on_download_requested(self, results: List[SearchResult]) -> None:
        """Handle download request.

        Args:
            results: List of search results to download.
        """
        # Check authentication
        if not self.auth_manager.is_authenticated():
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Authentication Required",
                "Please configure OAuth2 credentials in CDSE Settings to download products.",
            )
            # Show settings dock if not visible
            if not self.settings_dock:
                self._create_settings_dock()
            self.settings_dock.show()
            self.action_settings.setChecked(True)
            return

        # Show download dialog (non-modal so QGIS remains usable)
        self._download_dialog = DownloadDialog(
            results, self.auth_manager, self.iface.mainWindow()
        )

        # Set default directory from settings
        if self.settings_dock:
            default_dir = self.settings_dock.get_default_download_dir()
            if default_dir:
                self._download_dialog.set_output_directory(default_dir)

        # Show non-modal dialog
        self._download_dialog.show()
        self._download_dialog.raise_()
        self._download_dialog.activateWindow()

    def _on_zoom_to_requested(self, result: SearchResult) -> None:
        """Handle zoom to request.

        Args:
            result: Search result to zoom to.
        """
        if self._footprint_layer:
            zoom_to_feature(self._footprint_layer, result.id, self.iface)

    def _on_show_footprint_requested(self, result: SearchResult) -> None:
        """Handle show footprint request.

        Args:
            result: Search result to show footprint for.
        """
        # Already handled by _add_footprints
        pass

    def _on_details_requested(self, result: SearchResult) -> None:
        """Handle details request.

        Args:
            result: Search result to show details for.
        """
        # Show a simple message box with details
        details = f"""
Name: {result.name}
ID: {result.id}
Collection: {result.collection}
Date: {result.datetime.isoformat() if result.datetime else 'N/A'}
Cloud Cover: {result.cloud_cover if result.cloud_cover is not None else 'N/A'}%
Size: {result.size_mb if result.size_mb is not None else 'N/A'} MB
API Source: {result.api_source}
"""
        if result.download_url:
            details += f"\nDownload URL: {result.download_url}"

        QMessageBox.information(
            self.iface.mainWindow(), "Product Details", details.strip()
        )

    def _on_view_cog_requested(self, result: SearchResult) -> None:
        """Handle COG viewing request.

        Args:
            result: Search result to view as COG.
        """
        show_cog_viewer(result, self.auth_manager, self.iface.mainWindow())

    def _on_table_selection_changed(self, selected_ids: List[str]) -> None:
        """Handle selection change in results table.

        Highlights corresponding footprints on the map.

        Args:
            selected_ids: List of selected result IDs.
        """
        if self._updating_selection:
            return

        self._updating_selection = True
        try:
            if self._footprint_layer:
                select_features_by_id(self._footprint_layer, selected_ids)
        finally:
            self._updating_selection = False

    def _on_layer_selection_changed(self) -> None:
        """Handle selection change in footprint layer.

        Selects corresponding rows in the results table.
        """
        if self._updating_selection:
            return

        self._updating_selection = True
        try:
            if self._footprint_layer and self.results_dock:
                selected_ids = get_selected_feature_ids(self._footprint_layer)
                self.results_dock.select_by_ids(selected_ids, emit_signal=False)
        finally:
            self._updating_selection = False

    def _check_for_updates(self) -> None:
        """Show the update checker dialog."""
        show_update_dialog(self.iface.mainWindow())

    def _show_about(self) -> None:
        """Show the about dialog."""
        from .dialogs.update_checker import get_current_version

        version = get_current_version() or "Unknown"

        about_text = f"""
<h3>CDSE Plugin</h3>
<p>Version: {version}</p>
<p>A QGIS plugin for accessing Copernicus Data Space Ecosystem (CDSE) satellite imagery.</p>
<p><b>Features:</b></p>
<ul>
<li>Search Sentinel-1/2/3/5P/6, Copernicus DEM, and Landsat data</li>
<li>Support for both STAC and OData APIs</li>
<li>Interactive footprint visualization</li>
<li>Batch download capabilities</li>
<li>Cloud cover filtering for optical data</li>
</ul>
<p><b>Author:</b> Qiusheng Wu</p>
<p><b>Repository:</b> <a href="https://github.com/opengeos/qgis-cdse-plugin">github.com/opengeos/qgis-cdse-plugin</a></p>
<p><b>License:</b> MIT</p>
"""
        QMessageBox.about(self.iface.mainWindow(), "About CDSE Plugin", about_text)
