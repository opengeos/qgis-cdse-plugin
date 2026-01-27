"""Data models for CDSE Plugin."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# Default S3 to HTTPS mapping for CDSE
CDSE_S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"


@dataclass
class Asset:
    """Represents a downloadable asset from a search result.

    Attributes:
        name: Asset name/key.
        href: Download URL.
        type: MIME type of the asset.
        title: Human-readable title.
        size: Size in bytes.
        roles: List of asset roles (e.g., 'data', 'thumbnail').
        alternate: Alternate access URLs (e.g., HTTPS for COGs).
        storage_refs: List of storage reference keys.
        storage_schemes: Storage scheme definitions from item properties.
    """

    name: str
    href: str
    type: Optional[str] = None
    title: Optional[str] = None
    size: Optional[int] = None
    roles: List[str] = field(default_factory=list)
    alternate: Optional[Dict[str, Any]] = None
    storage_refs: List[str] = field(default_factory=list)
    storage_schemes: Optional[Dict[str, Any]] = None

    @classmethod
    def from_stac(
        cls,
        name: str,
        asset_dict: Dict[str, Any],
        storage_schemes: Optional[Dict[str, Any]] = None,
    ) -> "Asset":
        """Create an Asset from a STAC asset dictionary.

        Args:
            name: Asset name/key.
            asset_dict: STAC asset dictionary.
            storage_schemes: Storage schemes from item properties.

        Returns:
            Asset instance.
        """
        return cls(
            name=name,
            href=asset_dict.get("href", ""),
            type=asset_dict.get("type"),
            title=asset_dict.get("title"),
            size=asset_dict.get("file:size"),
            roles=asset_dict.get("roles", []),
            alternate=asset_dict.get("alternate"),
            storage_refs=asset_dict.get("storage:refs", []),
            storage_schemes=storage_schemes,
        )

    def get_https_url(self) -> Optional[str]:
        """Get the HTTPS URL for this asset (for COG access).

        Returns:
            HTTPS URL or None if not available.
        """
        # Priority 1: Check alternate URLs
        if self.alternate and "https" in self.alternate:
            return self.alternate["https"].get("href")

        # Priority 2: If href is already HTTPS, return it
        if self.href and self.href.startswith("https://"):
            return self.href

        # Priority 3: Convert S3 URL to HTTPS using storage schemes
        if self.href and self.href.startswith("s3://"):
            return self._convert_s3_to_https(self.href)

        return None

    def _convert_s3_to_https(self, s3_url: str) -> Optional[str]:
        """Convert an S3 URL to HTTPS URL.

        Args:
            s3_url: S3 URL (e.g., s3://eodata/path/to/file).

        Returns:
            HTTPS URL or None if conversion fails.
        """
        # Parse S3 URL: s3://bucket/path -> bucket, path
        if not s3_url.startswith("s3://"):
            return None

        path = s3_url[5:]  # Remove 's3://'

        # Try to find the HTTPS endpoint from storage schemes
        endpoint = CDSE_S3_ENDPOINT  # Default

        if self.storage_schemes and self.storage_refs:
            # Prefer cdse-s3 over creodias-s3 (creodias is requester_pays)
            for ref in ["cdse-s3", "creodias-s3"]:
                if ref in self.storage_refs and ref in self.storage_schemes:
                    scheme = self.storage_schemes[ref]
                    platform = scheme.get("platform", "")
                    if platform:
                        endpoint = platform
                        break

        # Build HTTPS URL
        # S3 URL: s3://eodata/path/to/file
        # HTTPS URL: https://endpoint/path/to/file (without bucket name for CDSE)
        # The bucket name 'eodata' is part of the endpoint subdomain
        if path.startswith("eodata/"):
            path = path[7:]  # Remove 'eodata/'

        return f"{endpoint}/{path}"


@dataclass
class Collection:
    """Represents a CDSE data collection.

    Attributes:
        id: Collection identifier.
        title: Human-readable title.
        description: Collection description.
        keywords: List of keywords.
        license: License identifier.
        extent: Spatial and temporal extent.
        links: Related links.
        supports_cloud_cover: Whether collection supports cloud cover filtering.
    """

    id: str
    title: str
    description: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    license: Optional[str] = None
    extent: Optional[Dict[str, Any]] = None
    links: List[Dict[str, str]] = field(default_factory=list)
    supports_cloud_cover: bool = False

    @classmethod
    def from_stac(cls, collection_dict: Dict[str, Any]) -> "Collection":
        """Create a Collection from a STAC collection dictionary.

        Args:
            collection_dict: STAC collection dictionary.

        Returns:
            Collection instance.
        """
        collection_id = collection_dict.get("id", "")
        from ..utils.config import CLOUD_COVER_KEYWORDS

        # Check if collection supports cloud cover filtering
        collection_id_lower = collection_id.lower()
        supports_cloud = any(kw in collection_id_lower for kw in CLOUD_COVER_KEYWORDS)

        return cls(
            id=collection_id,
            title=collection_dict.get("title", collection_id),
            description=collection_dict.get("description"),
            keywords=collection_dict.get("keywords", []),
            license=collection_dict.get("license"),
            extent=collection_dict.get("extent"),
            links=collection_dict.get("links", []),
            supports_cloud_cover=supports_cloud,
        )


@dataclass
class SearchResult:
    """Represents a search result item.

    Attributes:
        id: Unique item identifier.
        name: Item name/title.
        collection: Parent collection ID.
        datetime: Acquisition datetime.
        geometry: GeoJSON geometry dictionary.
        bbox: Bounding box [minx, miny, maxx, maxy].
        cloud_cover: Cloud cover percentage (0-100).
        size_mb: File size in megabytes.
        thumbnail_url: URL to thumbnail image.
        download_url: URL for downloading the item.
        assets: Dictionary of available assets.
        properties: Additional properties.
        api_source: Source API ('stac' or 'odata').
    """

    id: str
    name: str
    collection: str
    datetime: Optional[datetime] = None
    geometry: Optional[Dict[str, Any]] = None
    bbox: Optional[List[float]] = None
    cloud_cover: Optional[float] = None
    size_mb: Optional[float] = None
    thumbnail_url: Optional[str] = None
    download_url: Optional[str] = None
    assets: Dict[str, Asset] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    api_source: str = "stac"

    @classmethod
    def from_stac_item(cls, item_dict: Dict[str, Any]) -> "SearchResult":
        """Create a SearchResult from a STAC item dictionary.

        Args:
            item_dict: STAC item dictionary.

        Returns:
            SearchResult instance.
        """
        properties = item_dict.get("properties", {})

        # Parse datetime
        dt = None
        datetime_str = properties.get("datetime")
        if datetime_str:
            try:
                # Handle various datetime formats
                if datetime_str.endswith("Z"):
                    datetime_str = datetime_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Extract cloud cover
        cloud_cover = properties.get("eo:cloud_cover")
        if cloud_cover is None:
            cloud_cover = properties.get("cloudCover")

        # Get storage schemes from properties (needed for S3 URL conversion)
        storage_schemes = properties.get("storage:schemes")

        # Extract assets with storage schemes
        assets = {}
        for name, asset_dict in item_dict.get("assets", {}).items():
            assets[name] = Asset.from_stac(name, asset_dict, storage_schemes)

        # Find thumbnail URL
        thumbnail_url = None
        if "thumbnail" in assets:
            thumbnail_url = assets["thumbnail"].href
        elif "rendered_preview" in assets:
            thumbnail_url = assets["rendered_preview"].href

        # Find download URL - look for "Product" asset (capitalized)
        download_url = None
        size_mb = None
        download_asset = None

        # Priority 1: Product asset (full product download)
        if "Product" in assets:
            download_asset = assets["Product"]

        # Priority 2: lowercase product
        elif "product" in assets:
            download_asset = assets["product"]

        # Priority 3: data asset (for COG-only collections like DEM)
        elif "data" in assets:
            download_asset = assets["data"]

        if download_asset:
            # Get HTTPS URL (handles S3 to HTTPS conversion)
            download_url = download_asset.get_https_url()
            # Fallback to original href if no HTTPS available
            if not download_url:
                download_url = download_asset.href
            if download_asset.size:
                size_mb = download_asset.size / (1024 * 1024)

        return cls(
            id=item_dict.get("id", ""),
            name=properties.get("title", item_dict.get("id", "")),
            collection=item_dict.get("collection", ""),
            datetime=dt,
            geometry=item_dict.get("geometry"),
            bbox=item_dict.get("bbox"),
            cloud_cover=cloud_cover,
            size_mb=size_mb,
            thumbnail_url=thumbnail_url,
            download_url=download_url,
            assets=assets,
            properties=properties,
            api_source="stac",
        )

    @classmethod
    def from_odata_product(cls, product_dict: Dict[str, Any]) -> "SearchResult":
        """Create a SearchResult from an OData product dictionary.

        Args:
            product_dict: OData product dictionary.

        Returns:
            SearchResult instance.
        """
        # Parse datetime
        dt = None
        datetime_str = product_dict.get("ContentDate", {}).get("Start")
        if datetime_str:
            try:
                dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Extract geometry from Footprint (WKT)
        geometry = None
        footprint = product_dict.get("Footprint")
        if footprint:
            geometry = _wkt_to_geojson(footprint)

        # Extract cloud cover from attributes
        cloud_cover = None
        for attr in product_dict.get("Attributes", []):
            if attr.get("Name") == "cloudCover":
                try:
                    cloud_cover = float(attr.get("Value", 0))
                except (ValueError, TypeError):
                    pass
                break

        # Size in bytes to MB
        size_bytes = product_dict.get("ContentLength", 0)
        size_mb = size_bytes / (1024 * 1024) if size_bytes else None

        # Build download URL
        product_id = product_dict.get("Id", "")
        download_url = (
            f"https://download.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
            if product_id
            else None
        )

        # Thumbnail URL
        thumbnail_url = None
        quicklook = product_dict.get("Quicklook")
        if quicklook:
            thumbnail_url = quicklook

        return cls(
            id=product_id,
            name=product_dict.get("Name", ""),
            collection=product_dict.get("Collection", {}).get("Name", ""),
            datetime=dt,
            geometry=geometry,
            bbox=None,
            cloud_cover=cloud_cover,
            size_mb=size_mb,
            thumbnail_url=thumbnail_url,
            download_url=download_url,
            assets={},
            properties=product_dict,
            api_source="odata",
        )

    def get_cog_assets(self) -> Dict[str, Asset]:
        """Get assets that are likely COG files (bands, visual).

        Returns:
            Dictionary of COG-compatible assets.
        """
        cog_assets = {}
        for name, asset in self.assets.items():
            # Include band data and visual assets
            if any(role in asset.roles for role in ["data", "visual", "reflectance"]):
                # Exclude metadata and archive files
                if "metadata" not in asset.roles and "archive" not in asset.roles:
                    # Check if it's a COG-compatible asset:
                    # 1. Has HTTPS alternate URL
                    # 2. Is a band file (ends with resolution suffix)
                    # 3. Is a GeoTIFF/COG file type
                    # 4. Has S3 URL that can be converted to HTTPS
                    is_cog = False

                    if asset.alternate:
                        is_cog = True
                    elif name.endswith(("_10m", "_20m", "_60m")):
                        is_cog = True
                    elif asset.type and "geotiff" in asset.type.lower():
                        is_cog = True
                    elif asset.type and "cloud-optimized" in asset.type.lower():
                        is_cog = True
                    elif asset.href and asset.href.startswith("s3://"):
                        # S3 URLs can be converted to HTTPS
                        is_cog = True

                    if is_cog:
                        cog_assets[name] = asset
        return cog_assets

    def get_visual_asset(self) -> Optional[Asset]:
        """Get the true color image (TCI) asset if available.

        Returns:
            TCI asset or None.
        """
        # Look for TCI (True Color Image) assets
        for name in ["TCI_10m", "TCI_20m", "TCI_60m", "visual", "TCI"]:
            if name in self.assets:
                return self.assets[name]
        return None


def _wkt_to_geojson(wkt: str) -> Optional[Dict[str, Any]]:
    """Convert WKT string to GeoJSON geometry.

    Args:
        wkt: WKT geometry string.

    Returns:
        GeoJSON geometry dictionary or None if parsing fails.
    """
    wkt = wkt.strip()

    if wkt.upper().startswith("POLYGON"):
        try:
            # Extract coordinates from POLYGON((x1 y1, x2 y2, ...))
            coords_str = wkt[wkt.index("((") + 2 : wkt.rindex("))")]
            rings = []
            for ring_str in coords_str.split("),("):
                ring_str = ring_str.replace("(", "").replace(")", "")
                ring = []
                for point_str in ring_str.split(","):
                    parts = point_str.strip().split()
                    if len(parts) >= 2:
                        ring.append([float(parts[0]), float(parts[1])])
                rings.append(ring)
            return {"type": "Polygon", "coordinates": rings}
        except (ValueError, IndexError):
            pass

    elif wkt.upper().startswith("MULTIPOLYGON"):
        try:
            # Extract coordinates from MULTIPOLYGON(((x1 y1, ...)),((x2 y2, ...)))
            coords_str = wkt[wkt.index("(((") + 3 : wkt.rindex(")))")]
            polygons = []
            for poly_str in coords_str.split(")),(("):
                rings = []
                for ring_str in poly_str.split("),("):
                    ring_str = ring_str.replace("(", "").replace(")", "")
                    ring = []
                    for point_str in ring_str.split(","):
                        parts = point_str.strip().split()
                        if len(parts) >= 2:
                            ring.append([float(parts[0]), float(parts[1])])
                    rings.append(ring)
                polygons.append(rings)
            return {"type": "MultiPolygon", "coordinates": polygons}
        except (ValueError, IndexError):
            pass

    return None


@dataclass
class SearchParameters:
    """Parameters for a search query.

    Attributes:
        collection: Collection ID to search.
        bbox: Bounding box [minx, miny, maxx, maxy].
        start_date: Start datetime for temporal filter.
        end_date: End datetime for temporal filter.
        max_cloud_cover: Maximum cloud cover percentage.
        max_results: Maximum number of results to return.
        api: API to use ('stac' or 'odata').
        product_type: Optional product type filter.
    """

    collection: str
    bbox: Optional[List[float]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_cloud_cover: Optional[float] = None
    max_results: int = 100
    api: str = "stac"
    product_type: Optional[str] = None
