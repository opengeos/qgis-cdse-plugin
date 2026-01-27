"""Geometry conversion utilities for CDSE Plugin."""

import json
from typing import List, Optional, Tuple, Union

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsGeometry,
        QgsPointXY,
        QgsProject,
        QgsRectangle,
    )
except ImportError:
    # For type checking outside QGIS
    pass


def bbox_to_polygon(
    bbox: Union[List[float], Tuple[float, float, float, float]],
) -> List[List[List[float]]]:
    """Convert a bounding box to a GeoJSON polygon coordinates.

    Args:
        bbox: Bounding box as [minx, miny, maxx, maxy].

    Returns:
        GeoJSON polygon coordinates as [[[x1,y1], [x2,y2], ...]].
    """
    minx, miny, maxx, maxy = bbox
    return [
        [
            [minx, miny],
            [maxx, miny],
            [maxx, maxy],
            [minx, maxy],
            [minx, miny],
        ]
    ]


def wkt_from_extent(extent: "QgsRectangle", source_crs: Optional[str] = None) -> str:
    """Create a WKT polygon string from a QGIS extent.

    Args:
        extent: QGIS rectangle extent.
        source_crs: Source CRS as EPSG code string (e.g., "EPSG:3857").
            If provided, transforms to EPSG:4326.

    Returns:
        WKT POLYGON string in EPSG:4326.
    """
    minx = extent.xMinimum()
    miny = extent.yMinimum()
    maxx = extent.xMaximum()
    maxy = extent.yMaximum()

    if source_crs and source_crs != "EPSG:4326":
        src_crs = QgsCoordinateReferenceSystem(source_crs)
        dst_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())

        # Transform corner points
        min_point = transform.transform(QgsPointXY(minx, miny))
        max_point = transform.transform(QgsPointXY(maxx, maxy))

        minx, miny = min_point.x(), min_point.y()
        maxx, maxy = max_point.x(), max_point.y()

    wkt = f"POLYGON(({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
    return wkt


def extent_to_bbox(
    extent: "QgsRectangle", source_crs: Optional[str] = None
) -> List[float]:
    """Convert a QGIS extent to a bounding box list.

    Args:
        extent: QGIS rectangle extent.
        source_crs: Source CRS as EPSG code string (e.g., "EPSG:3857").
            If provided, transforms to EPSG:4326.

    Returns:
        Bounding box as [minx, miny, maxx, maxy] in EPSG:4326.
    """
    minx = extent.xMinimum()
    miny = extent.yMinimum()
    maxx = extent.xMaximum()
    maxy = extent.yMaximum()

    if source_crs and source_crs != "EPSG:4326":
        src_crs = QgsCoordinateReferenceSystem(source_crs)
        dst_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())

        min_point = transform.transform(QgsPointXY(minx, miny))
        max_point = transform.transform(QgsPointXY(maxx, maxy))

        minx, miny = min_point.x(), min_point.y()
        maxx, maxy = max_point.x(), max_point.y()

    return [minx, miny, maxx, maxy]


def geojson_to_qgs_geometry(geojson: dict) -> "QgsGeometry":
    """Convert a GeoJSON geometry to a QGIS geometry.

    Args:
        geojson: GeoJSON geometry dictionary with 'type' and 'coordinates'.

    Returns:
        QgsGeometry object.
    """
    geojson_str = json.dumps(geojson)
    geometry = QgsGeometry.fromWkt(geojson_to_wkt(geojson))
    if geometry.isNull():
        # Fallback: try direct GeoJSON parsing
        geometry = QgsGeometry.fromJson(geojson_str)
    return geometry


def geojson_to_wkt(geojson: dict) -> str:
    """Convert a GeoJSON geometry to WKT.

    Args:
        geojson: GeoJSON geometry dictionary.

    Returns:
        WKT string representation.
    """
    geom_type = geojson.get("type", "").upper()
    coords = geojson.get("coordinates", [])

    if geom_type == "POINT":
        return f"POINT({coords[0]} {coords[1]})"

    elif geom_type == "LINESTRING":
        points = ", ".join(f"{c[0]} {c[1]}" for c in coords)
        return f"LINESTRING({points})"

    elif geom_type == "POLYGON":
        rings = []
        for ring in coords:
            points = ", ".join(f"{c[0]} {c[1]}" for c in ring)
            rings.append(f"({points})")
        return f"POLYGON({', '.join(rings)})"

    elif geom_type == "MULTIPOLYGON":
        polygons = []
        for polygon in coords:
            rings = []
            for ring in polygon:
                points = ", ".join(f"{c[0]} {c[1]}" for c in ring)
                rings.append(f"({points})")
            polygons.append(f"({', '.join(rings)})")
        return f"MULTIPOLYGON({', '.join(polygons)})"

    elif geom_type == "MULTIPOINT":
        points = ", ".join(f"({c[0]} {c[1]})" for c in coords)
        return f"MULTIPOINT({points})"

    elif geom_type == "MULTILINESTRING":
        lines = []
        for line in coords:
            points = ", ".join(f"{c[0]} {c[1]}" for c in line)
            lines.append(f"({points})")
        return f"MULTILINESTRING({', '.join(lines)})"

    else:
        raise ValueError(f"Unsupported geometry type: {geom_type}")


def validate_bbox(bbox: List[float]) -> bool:
    """Validate a bounding box.

    Args:
        bbox: Bounding box as [minx, miny, maxx, maxy].

    Returns:
        True if valid, False otherwise.
    """
    if len(bbox) != 4:
        return False

    minx, miny, maxx, maxy = bbox

    # Check valid coordinate ranges
    if not (-180 <= minx <= 180 and -180 <= maxx <= 180):
        return False
    if not (-90 <= miny <= 90 and -90 <= maxy <= 90):
        return False

    # Check min < max
    if minx >= maxx or miny >= maxy:
        return False

    return True
