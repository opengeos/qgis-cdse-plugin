"""COG viewer dialog for CDSE Plugin."""

from typing import TYPE_CHECKING, Dict, List, Optional

try:
    from qgis.core import QgsProject, QgsRasterLayer
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )
except ImportError:
    pass

if TYPE_CHECKING:
    from ..api.auth import AuthManager
    from ..api.models import Asset, SearchResult


class COGViewerDialog(QDialog):
    """Dialog for viewing COG assets without downloading.

    This dialog allows users to select which bands/assets to load
    as raster layers in QGIS using VSICURL.
    """

    layer_added = pyqtSignal(str)  # layer name

    def __init__(
        self,
        result: "SearchResult",
        auth_manager: "AuthManager",
        parent=None,
    ):
        """Initialize the COG viewer dialog.

        Args:
            result: SearchResult with COG assets.
            auth_manager: Authentication manager for authorized access.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.result = result
        self.auth_manager = auth_manager
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle(f"View COG - {self.result.name}")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "Select assets to add as raster layers. COGs are streamed directly\n"
            "from the server without downloading the full file."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Quick add buttons
        quick_group = QGroupBox("Quick Add")
        quick_layout = QHBoxLayout(quick_group)

        self.add_tci_btn = QPushButton("True Color (TCI)")
        self.add_tci_btn.clicked.connect(self._add_tci)
        quick_layout.addWidget(self.add_tci_btn)

        self.add_rgb_btn = QPushButton("RGB (B4-B3-B2)")
        self.add_rgb_btn.clicked.connect(self._add_rgb)
        quick_layout.addWidget(self.add_rgb_btn)

        self.add_ndvi_ready_btn = QPushButton("NIR + Red (B8-B4)")
        self.add_ndvi_ready_btn.clicked.connect(self._add_ndvi_bands)
        quick_layout.addWidget(self.add_ndvi_ready_btn)

        layout.addWidget(quick_group)

        # Resolution filter
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution:"))

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["All", "10m", "20m", "60m"])
        self.resolution_combo.currentTextChanged.connect(self._filter_assets)
        res_layout.addWidget(self.resolution_combo)
        res_layout.addStretch()

        layout.addLayout(res_layout)

        # Asset list
        self.asset_list = QListWidget()
        self.asset_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.asset_list)

        # Populate asset list
        self._populate_assets()

        # Buttons
        button_layout = QHBoxLayout()

        self.add_selected_btn = QPushButton("Add Selected Layers")
        self.add_selected_btn.clicked.connect(self._add_selected)
        button_layout.addWidget(self.add_selected_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Check authentication
        if not self.auth_manager.is_authenticated():
            self.status_label.setText(
                "Warning: Not logged in. Some assets may require authentication."
            )
            self.status_label.setStyleSheet("color: orange")

    def _populate_assets(self, resolution_filter: str = "All") -> None:
        """Populate the asset list.

        Args:
            resolution_filter: Filter by resolution ("All", "10m", "20m", "60m").
        """
        self.asset_list.clear()

        cog_assets = self.result.get_cog_assets()

        for name, asset in sorted(cog_assets.items()):
            # Apply resolution filter
            if resolution_filter != "All":
                if not name.endswith(f"_{resolution_filter}"):
                    continue

            # Get HTTPS URL
            https_url = asset.get_https_url()
            if not https_url:
                continue

            # Create list item
            size_str = ""
            if asset.size:
                size_mb = asset.size / (1024 * 1024)
                size_str = f" ({size_mb:.1f} MB)"

            item = QListWidgetItem(f"{name}{size_str}")
            item.setData(Qt.UserRole, {"name": name, "asset": asset, "url": https_url})
            item.setToolTip(https_url)
            self.asset_list.addItem(item)

        if self.asset_list.count() == 0:
            self.status_label.setText("No COG assets available for this product")

    def _filter_assets(self, resolution: str) -> None:
        """Filter assets by resolution.

        Args:
            resolution: Resolution filter.
        """
        self._populate_assets(resolution)

    def _add_tci(self) -> None:
        """Add True Color Image (TCI) layer."""
        tci_asset = self.result.get_visual_asset()
        if tci_asset:
            self._add_cog_layer(tci_asset.name, tci_asset)
        else:
            self.status_label.setText("No TCI asset available")

    def _add_rgb(self) -> None:
        """Add RGB bands (B4, B3, B2) at 10m resolution."""
        bands = ["B04_10m", "B03_10m", "B02_10m"]
        added = 0
        for band in bands:
            if band in self.result.assets:
                asset = self.result.assets[band]
                if self._add_cog_layer(band, asset):
                    added += 1

        if added == 0:
            self.status_label.setText("RGB bands not available")
        else:
            self.status_label.setText(f"Added {added} RGB bands")

    def _add_ndvi_bands(self) -> None:
        """Add NIR and Red bands for NDVI calculation."""
        bands = ["B08_10m", "B04_10m"]  # NIR and Red
        added = 0
        for band in bands:
            if band in self.result.assets:
                asset = self.result.assets[band]
                if self._add_cog_layer(band, asset):
                    added += 1

        if added == 0:
            self.status_label.setText("NDVI bands not available")
        else:
            self.status_label.setText(f"Added {added} bands for NDVI")

    def _add_selected(self) -> None:
        """Add selected assets as layers."""
        selected_items = self.asset_list.selectedItems()
        if not selected_items:
            self.status_label.setText("No assets selected")
            return

        added = 0
        for item in selected_items:
            data = item.data(Qt.UserRole)
            if data:
                name = data["name"]
                asset = data["asset"]
                if self._add_cog_layer(name, asset):
                    added += 1

        self.status_label.setText(f"Added {added} of {len(selected_items)} layers")

    def _add_cog_layer(self, name: str, asset: "Asset") -> bool:
        """Add a COG as a raster layer.

        Args:
            name: Layer name.
            asset: Asset object with href and metadata.

        Returns:
            True if layer was added successfully.
        """
        try:
            # Build VSI path with appropriate authentication
            vsi_path = self._build_vsi_path(asset)

            # Create layer name
            layer_name = f"{self.result.id}_{name}"

            # Create raster layer
            layer = QgsRasterLayer(vsi_path, layer_name)

            if not layer.isValid():
                # Provide more specific error message
                is_s3 = asset.href.startswith("s3://") or "eodata" in asset.href
                if is_s3 and not self.auth_manager.has_aws_credentials():
                    self.status_label.setText(
                        f"Failed to load {name} - configure S3 credentials in Settings"
                    )
                    self.status_label.setStyleSheet("color: orange")
                elif is_s3:
                    self.status_label.setText(
                        f"Failed to load {name} - S3 access denied, check credentials"
                    )
                    self.status_label.setStyleSheet("color: red")
                else:
                    self.status_label.setText(
                        f"Failed to load {name} - may require authentication"
                    )
                return False

            # Add to project
            QgsProject.instance().addMapLayer(layer)
            self.layer_added.emit(layer_name)
            self.status_label.setText(f"Added {name}")
            self.status_label.setStyleSheet("color: green")

            return True

        except Exception as e:
            self.status_label.setText(f"Error loading {name}: {str(e)}")
            self.status_label.setStyleSheet("color: red")
            return False

    def _build_vsi_path(self, asset: "Asset") -> str:
        """Build a VSI path for accessing the asset.

        For S3-based assets, uses /vsis3/ with proper authentication.
        For HTTPS URLs, uses /vsicurl/.

        Args:
            asset: Asset object with href and storage info.

        Returns:
            VSI path string.
        """
        from osgeo import gdal

        href = asset.href

        # Check if this is an S3 URL
        if href.startswith("s3://"):
            # Use /vsis3/ for S3 access
            # S3 URL format: s3://bucket/path -> /vsis3/bucket/path
            s3_path = href[5:]  # Remove 's3://'

            # Configure GDAL for CDSE S3 endpoint
            if self.auth_manager.has_aws_credentials():
                self.auth_manager.apply_gdal_config()
            else:
                # Set endpoint even without credentials (for error message)
                gdal.SetConfigOption(
                    "AWS_S3_ENDPOINT", "eodata.dataspace.copernicus.eu"
                )
                gdal.SetConfigOption("AWS_HTTPS", "YES")
                gdal.SetConfigOption("AWS_VIRTUAL_HOSTING", "FALSE")

            return f"/vsis3/{s3_path}"

        # Check if this is an eodata HTTPS URL (converted from S3)
        elif "eodata.dataspace.copernicus.eu" in href:
            # This URL needs S3 auth, convert back to S3 path
            # https://eodata.dataspace.copernicus.eu/path -> s3://eodata/path
            path = href.replace("https://eodata.dataspace.copernicus.eu/", "")

            if self.auth_manager.has_aws_credentials():
                self.auth_manager.apply_gdal_config()
            else:
                gdal.SetConfigOption(
                    "AWS_S3_ENDPOINT", "eodata.dataspace.copernicus.eu"
                )
                gdal.SetConfigOption("AWS_HTTPS", "YES")
                gdal.SetConfigOption("AWS_VIRTUAL_HOSTING", "FALSE")

            return f"/vsis3/eodata/{path}"

        # Regular HTTPS URL - use /vsicurl/
        else:
            # Set OAuth token for HTTP headers if available
            if self.auth_manager.is_authenticated():
                token = self.auth_manager.get_access_token()
                if token:
                    gdal.SetConfigOption(
                        "GDAL_HTTP_HEADERS", f"Authorization: Bearer {token}"
                    )

            return f"/vsicurl/{href}"


def show_cog_viewer(
    result: "SearchResult",
    auth_manager: "AuthManager",
    parent=None,
) -> None:
    """Show the COG viewer dialog for a search result.

    Args:
        result: SearchResult with COG assets.
        auth_manager: Authentication manager.
        parent: Parent widget.
    """
    # Check if result has COG assets
    cog_assets = result.get_cog_assets()
    if not cog_assets:
        QMessageBox.information(
            parent,
            "No COG Assets",
            "This product does not have any COG assets available for streaming.",
        )
        return

    dialog = COGViewerDialog(result, auth_manager, parent)
    dialog.exec_()
