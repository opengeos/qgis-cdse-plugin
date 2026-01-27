"""Utility modules for CDSE Plugin."""

from .config import (
    CLOUD_COVER_KEYWORDS,
    COLLECTION_CATEGORIES,
    GITHUB_BRANCH,
    GITHUB_REPO,
    ODATA_API_URL,
    PLUGIN_PATH,
    STAC_API_URL,
    TOKEN_URL,
)
from .geometry import bbox_to_polygon, geojson_to_qgs_geometry, wkt_from_extent
from .layer_utils import (
    add_footprint_layer,
    get_selected_feature_ids,
    select_features_by_id,
    style_footprint_layer,
)

__all__ = [
    "STAC_API_URL",
    "ODATA_API_URL",
    "TOKEN_URL",
    "COLLECTION_CATEGORIES",
    "CLOUD_COVER_KEYWORDS",
    "GITHUB_REPO",
    "GITHUB_BRANCH",
    "PLUGIN_PATH",
    "bbox_to_polygon",
    "wkt_from_extent",
    "geojson_to_qgs_geometry",
    "add_footprint_layer",
    "style_footprint_layer",
    "select_features_by_id",
    "get_selected_feature_ids",
]
