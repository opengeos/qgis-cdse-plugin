"""QGIS layer utilities for CDSE Plugin."""

from typing import TYPE_CHECKING, List, Optional

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsGeometry,
        QgsProject,
        QgsSymbol,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
    from qgis.PyQt.QtGui import QColor
except ImportError:
    pass

if TYPE_CHECKING:
    from ..api.models import SearchResult

from .config import FOOTPRINT_COLOR, FOOTPRINT_OPACITY


def add_footprint_layer(
    results: List["SearchResult"],
    layer_name: str = "CDSE Search Results",
    group_name: Optional[str] = None,
) -> "QgsVectorLayer":
    """Create a vector layer with search result footprints.

    Args:
        results: List of SearchResult objects with geometry.
        layer_name: Name for the created layer.
        group_name: Optional layer group name.

    Returns:
        QgsVectorLayer with footprint geometries.
    """
    # Create memory layer with polygon geometry
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", layer_name, "memory")
    provider = layer.dataProvider()

    # Add attribute fields
    fields = [
        QgsField("id", QVariant.String),
        QgsField("name", QVariant.String),
        QgsField("collection", QVariant.String),
        QgsField("datetime", QVariant.String),
        QgsField("cloud_cover", QVariant.Double),
        QgsField("size_mb", QVariant.Double),
        QgsField("thumbnail_url", QVariant.String),
        QgsField("download_url", QVariant.String),
    ]
    provider.addAttributes(fields)
    layer.updateFields()

    # Add features
    features = []
    for result in results:
        if result.geometry:
            feature = QgsFeature()

            # Convert geometry
            from .geometry import geojson_to_qgs_geometry

            qgs_geom = geojson_to_qgs_geometry(result.geometry)
            feature.setGeometry(qgs_geom)

            # Set attributes
            feature.setAttributes(
                [
                    result.id,
                    result.name,
                    result.collection,
                    result.datetime.isoformat() if result.datetime else "",
                    result.cloud_cover,
                    result.size_mb,
                    result.thumbnail_url or "",
                    result.download_url or "",
                ]
            )
            features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()

    # Apply styling
    style_footprint_layer(layer)

    # Add to project
    project = QgsProject.instance()

    if group_name:
        root = project.layerTreeRoot()
        group = root.findGroup(group_name)
        if not group:
            group = root.insertGroup(0, group_name)
        project.addMapLayer(layer, False)
        group.addLayer(layer)
    else:
        project.addMapLayer(layer)

    return layer


def style_footprint_layer(
    layer: "QgsVectorLayer",
    color: str = FOOTPRINT_COLOR,
    opacity: float = FOOTPRINT_OPACITY,
) -> None:
    """Apply styling to a footprint layer.

    Args:
        layer: Vector layer to style.
        color: Fill color as hex string.
        opacity: Fill opacity (0-1).
    """
    # Create symbol
    symbol = QgsSymbol.defaultSymbol(layer.geometryType())

    # Set fill color with opacity
    fill_color = QColor(color)
    fill_color.setAlphaF(opacity)
    symbol.setColor(fill_color)

    # Set stroke color (full opacity)
    stroke_color = QColor(color)
    symbol.symbolLayer(0).setStrokeColor(stroke_color)
    symbol.symbolLayer(0).setStrokeWidth(0.5)

    # Apply renderer
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def remove_footprint_layer(layer_name: str = "CDSE Search Results") -> bool:
    """Remove a footprint layer by name.

    Args:
        layer_name: Name of the layer to remove.

    Returns:
        True if layer was found and removed, False otherwise.
    """
    project = QgsProject.instance()
    layers = project.mapLayersByName(layer_name)

    if layers:
        for layer in layers:
            project.removeMapLayer(layer.id())
        return True
    return False


def zoom_to_layer(layer: "QgsVectorLayer", iface) -> None:
    """Zoom the map canvas to a layer's extent.

    Args:
        layer: Layer to zoom to.
        iface: QGIS interface instance.
    """
    if layer and layer.featureCount() > 0:
        extent = layer.extent()
        # Add a small buffer
        extent.scale(1.1)

        canvas = iface.mapCanvas()
        canvas_crs = canvas.mapSettings().destinationCrs()
        layer_crs = layer.crs()

        if canvas_crs != layer_crs:
            from qgis.core import QgsCoordinateTransform

            transform = QgsCoordinateTransform(
                layer_crs, canvas_crs, QgsProject.instance()
            )
            extent = transform.transformBoundingBox(extent)

        canvas.setExtent(extent)
        canvas.refresh()


def zoom_to_feature(
    layer: "QgsVectorLayer", feature_id: str, iface, id_field: str = "id"
) -> bool:
    """Zoom to a specific feature in a layer.

    Args:
        layer: Vector layer containing the feature.
        feature_id: ID value of the feature to zoom to.
        iface: QGIS interface instance.
        id_field: Name of the ID field.

    Returns:
        True if feature was found and zoomed to, False otherwise.
    """
    for feature in layer.getFeatures():
        if feature[id_field] == feature_id:
            extent = feature.geometry().boundingBox()
            extent.scale(1.5)

            canvas = iface.mapCanvas()
            canvas_crs = canvas.mapSettings().destinationCrs()
            layer_crs = layer.crs()

            if canvas_crs != layer_crs:
                from qgis.core import QgsCoordinateTransform

                transform = QgsCoordinateTransform(
                    layer_crs, canvas_crs, QgsProject.instance()
                )
                extent = transform.transformBoundingBox(extent)

            canvas.setExtent(extent)
            canvas.refresh()
            return True

    return False


def select_features_by_id(
    layer: "QgsVectorLayer",
    feature_ids: List[str],
    id_field: str = "id",
) -> None:
    """Select features in a layer by their ID values.

    Args:
        layer: Vector layer to select features in.
        feature_ids: List of ID values to select.
        id_field: Name of the ID field.
    """
    if not layer:
        return

    # Find feature IDs (internal QGIS IDs) that match the given IDs
    fids_to_select = []
    for feature in layer.getFeatures():
        if feature[id_field] in feature_ids:
            fids_to_select.append(feature.id())

    # Select the features
    layer.selectByIds(fids_to_select)


def get_selected_feature_ids(
    layer: "QgsVectorLayer",
    id_field: str = "id",
) -> List[str]:
    """Get the ID values of selected features in a layer.

    Args:
        layer: Vector layer to get selected features from.
        id_field: Name of the ID field.

    Returns:
        List of ID values from selected features.
    """
    if not layer:
        return []

    selected_ids = []
    for feature in layer.selectedFeatures():
        selected_ids.append(feature[id_field])

    return selected_ids
