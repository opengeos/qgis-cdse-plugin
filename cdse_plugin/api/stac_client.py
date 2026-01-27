"""STAC API client for CDSE Plugin."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..utils.config import CLOUD_COVER_KEYWORDS, COLLECTION_CATEGORIES, STAC_API_URL
from .auth import AuthManager
from .base_client import BaseClient
from .models import Collection, SearchParameters, SearchResult


class STACClient(BaseClient):
    """Client for the CDSE STAC API.

    This client provides access to Sentinel-1/2/3/5P/6, Copernicus DEM,
    and Landsat data through the STAC API.

    Attributes:
        base_url: STAC API base URL.
        auth_manager: Authentication manager for downloads.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        auth_manager: Optional[AuthManager] = None,
        base_url: str = STAC_API_URL,
        timeout: int = 30,
    ):
        """Initialize the STAC client.

        Args:
            auth_manager: Optional authentication manager for authenticated requests.
            base_url: Base URL for the STAC API.
            timeout: Request timeout in seconds.
        """
        super().__init__(auth_manager)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._collections_cache: Optional[List[Collection]] = None

    def search(self, params: SearchParameters) -> List[SearchResult]:
        """Search for products using the STAC API.

        Args:
            params: Search parameters including collection, bbox, dates, etc.

        Returns:
            List of SearchResult objects matching the criteria.

        Raises:
            requests.exceptions.RequestException: If the search request fails.
        """
        search_url = f"{self.base_url}/search"

        # Build search body
        body: Dict[str, Any] = {
            "limit": min(params.max_results, 100),
        }

        # Add collection filter
        if params.collection:
            body["collections"] = [params.collection]

        # Add bbox filter
        if params.bbox:
            body["bbox"] = params.bbox

        # Add datetime filter
        if params.start_date or params.end_date:
            start = (
                params.start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                if params.start_date
                else ".."
            )
            end = (
                params.end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                if params.end_date
                else ".."
            )
            body["datetime"] = f"{start}/{end}"

        # Add cloud cover filter using query parameter (simpler than CQL2)
        if params.max_cloud_cover is not None:
            body["query"] = {"eo:cloud_cover": {"lte": params.max_cloud_cover}}

        # Execute search
        results = []
        next_token = None

        while True:
            if next_token:
                body["token"] = next_token

            response = requests.post(
                search_url,
                json=body,
                headers=self._get_headers(),
                timeout=self.timeout,
            )

            response.raise_for_status()
            data = response.json()

            # Parse features
            for feature in data.get("features", []):
                result = SearchResult.from_stac_item(feature)
                results.append(result)

            # Check if we have enough results
            if len(results) >= params.max_results:
                results = results[: params.max_results]
                break

            # Check for next page using token from next link
            next_token = None
            for link in data.get("links", []):
                if link.get("rel") == "next":
                    # Extract token from the body if present
                    link_body = link.get("body", {})
                    next_token = link_body.get("token")
                    break

            if not next_token:
                break

        return results

    def get_collections(self, use_cache: bool = True) -> List[Collection]:
        """Get available collections from the STAC API.

        Args:
            use_cache: Whether to use cached collections if available.

        Returns:
            List of Collection objects.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        if use_cache and self._collections_cache is not None:
            return self._collections_cache

        url = f"{self.base_url}/collections"
        response = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        collections = []

        for coll_dict in data.get("collections", []):
            collection = Collection.from_stac(coll_dict)
            collections.append(collection)

        # Sort by title
        collections.sort(key=lambda c: c.title or c.id)

        self._collections_cache = collections
        return collections

    def get_collections_by_category(
        self, use_cache: bool = True
    ) -> Dict[str, List[Collection]]:
        """Get collections organized by category.

        Args:
            use_cache: Whether to use cached collections if available.

        Returns:
            Dictionary mapping category names to lists of collections.
        """
        collections = self.get_collections(use_cache=use_cache)
        categorized: Dict[str, List[Collection]] = {}

        for collection in collections:
            category = self._get_category(collection.id)
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(collection)

        # Sort categories
        return dict(sorted(categorized.items()))

    def _get_category(self, collection_id: str) -> str:
        """Determine the category for a collection ID.

        Args:
            collection_id: Collection ID.

        Returns:
            Category name.
        """
        collection_id_lower = collection_id.lower()

        for prefix, category in COLLECTION_CATEGORIES.items():
            if collection_id_lower.startswith(prefix):
                return category

        return "Other"

    def supports_cloud_cover(self, collection_id: str) -> bool:
        """Check if a collection supports cloud cover filtering.

        Args:
            collection_id: Collection ID.

        Returns:
            True if collection supports cloud cover filtering.
        """
        collection_id_lower = collection_id.lower()
        return any(kw in collection_id_lower for kw in CLOUD_COVER_KEYWORDS)

    def clear_cache(self) -> None:
        """Clear the collections cache."""
        self._collections_cache = None

    def get_collection(self, collection_id: str) -> Optional[Collection]:
        """Get details for a specific collection.

        Args:
            collection_id: ID of the collection to retrieve.

        Returns:
            Collection object or None if not found.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = f"{self.base_url}/collections/{collection_id}"

        try:
            response = requests.get(
                url, headers=self._get_headers(), timeout=self.timeout
            )
            response.raise_for_status()
            return Collection.from_stac(response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_item(self, collection_id: str, item_id: str) -> Optional[SearchResult]:
        """Get a specific item by ID.

        Args:
            collection_id: ID of the collection containing the item.
            item_id: ID of the item to retrieve.

        Returns:
            SearchResult object or None if not found.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = f"{self.base_url}/collections/{collection_id}/items/{item_id}"

        try:
            response = requests.get(
                url, headers=self._get_headers(), timeout=self.timeout
            )
            response.raise_for_status()
            return SearchResult.from_stac_item(response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_download_url(self, result: SearchResult) -> Optional[str]:
        """Get the download URL for a search result.

        Args:
            result: SearchResult to get download URL for.

        Returns:
            Download URL string or None if not available.
        """
        # Check for direct download URL
        if result.download_url:
            return result.download_url

        # Look for product/data asset
        for asset_key in ["product", "data", "download"]:
            if asset_key in result.assets:
                return result.assets[asset_key].href

        # Return first asset with 'data' role
        for asset in result.assets.values():
            if "data" in asset.roles:
                return asset.href

        return None

    def get_thumbnail_url(self, result: SearchResult) -> Optional[str]:
        """Get the thumbnail URL for a search result.

        Args:
            result: SearchResult to get thumbnail URL for.

        Returns:
            Thumbnail URL string or None if not available.
        """
        if result.thumbnail_url:
            return result.thumbnail_url

        for asset_key in ["thumbnail", "rendered_preview", "overview"]:
            if asset_key in result.assets:
                return result.assets[asset_key].href

        return None

    def search_by_bbox(
        self,
        collection: str,
        bbox: List[float],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_cloud_cover: Optional[float] = None,
        max_results: int = 100,
    ) -> List[SearchResult]:
        """Convenience method for searching by bounding box.

        Args:
            collection: Collection ID to search.
            bbox: Bounding box [minx, miny, maxx, maxy].
            start_date: Optional start date.
            end_date: Optional end date.
            max_cloud_cover: Optional maximum cloud cover percentage.
            max_results: Maximum number of results.

        Returns:
            List of SearchResult objects.
        """
        params = SearchParameters(
            collection=collection,
            bbox=bbox,
            start_date=start_date,
            end_date=end_date,
            max_cloud_cover=max_cloud_cover,
            max_results=max_results,
            api="stac",
        )
        return self.search(params)
