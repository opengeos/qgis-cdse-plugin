"""OData API client for CDSE Plugin."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from ..utils.config import ODATA_API_URL
from .auth import AuthManager
from .base_client import BaseClient
from .models import Collection, SearchParameters, SearchResult


class ODataClient(BaseClient):
    """Client for the CDSE OData API.

    This client provides access to additional datasets not available via STAC,
    including SMOS, ENVISAT, and MODIS data.

    Attributes:
        base_url: OData API base URL.
        auth_manager: Authentication manager for authenticated requests.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        auth_manager: Optional[AuthManager] = None,
        base_url: str = ODATA_API_URL,
        timeout: int = 30,
    ):
        """Initialize the OData client.

        Args:
            auth_manager: Optional authentication manager for authenticated requests.
            base_url: Base URL for the OData API.
            timeout: Request timeout in seconds.
        """
        super().__init__(auth_manager)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(self, params: SearchParameters) -> List[SearchResult]:
        """Search for products using the OData API.

        Args:
            params: Search parameters including collection, bbox, dates, etc.

        Returns:
            List of SearchResult objects matching the criteria.

        Raises:
            requests.exceptions.RequestException: If the search request fails.
        """
        # Build filter query
        filters = []

        # Collection filter
        if params.collection:
            filters.append(f"Collection/Name eq '{params.collection}'")

        # Date filter
        if params.start_date:
            start_str = params.start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            filters.append(f"ContentDate/Start ge {start_str}")

        if params.end_date:
            end_str = params.end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            filters.append(f"ContentDate/Start le {end_str}")

        # Cloud cover filter
        if params.max_cloud_cover is not None:
            filters.append(
                f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/Value le {params.max_cloud_cover})"
            )

        # Product type filter
        if params.product_type:
            filters.append(
                f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/Value eq '{params.product_type}')"
            )

        # Spatial filter (bbox to WKT polygon)
        if params.bbox:
            minx, miny, maxx, maxy = params.bbox
            wkt = f"POLYGON(({minx} {miny},{maxx} {miny},{maxx} {maxy},{minx} {maxy},{minx} {miny}))"
            filters.append(f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')")

        # Build query string
        query_params = {
            "$top": min(params.max_results, 1000),
            "$orderby": "ContentDate/Start desc",
            "$expand": "Attributes",
        }

        if filters:
            query_params["$filter"] = " and ".join(filters)

        # Execute request
        results = []
        skip = 0

        while True:
            query_params["$skip"] = skip
            response = requests.get(
                self.base_url,
                params=query_params,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            # Parse products
            for product in data.get("value", []):
                result = SearchResult.from_odata_product(product)
                results.append(result)

            # Check if we have enough results
            if len(results) >= params.max_results:
                results = results[: params.max_results]
                break

            # Check for more pages
            if "@odata.nextLink" not in data:
                break

            skip += query_params["$top"]

        return results

    def get_collections(self) -> List[Collection]:
        """Get available collections from the OData API.

        Returns:
            List of Collection objects.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Collections"
        response = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        collections = []

        for coll_dict in data.get("value", []):
            collection = Collection(
                id=coll_dict.get("Name", ""),
                title=coll_dict.get("Name", ""),
                description=coll_dict.get("Description"),
            )
            collections.append(collection)

        return collections

    def get_collection(self, collection_id: str) -> Optional[Collection]:
        """Get details for a specific collection.

        Args:
            collection_id: ID of the collection to retrieve.

        Returns:
            Collection object or None if not found.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Collections('{collection_id}')"

        try:
            response = requests.get(
                url, headers=self._get_headers(), timeout=self.timeout
            )
            response.raise_for_status()
            coll_dict = response.json()
            return Collection(
                id=coll_dict.get("Name", ""),
                title=coll_dict.get("Name", ""),
                description=coll_dict.get("Description"),
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_product(self, product_id: str) -> Optional[SearchResult]:
        """Get a specific product by ID.

        Args:
            product_id: UUID of the product to retrieve.

        Returns:
            SearchResult object or None if not found.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = f"{self.base_url}({product_id})"

        try:
            response = requests.get(
                url,
                params={"$expand": "Attributes"},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return SearchResult.from_odata_product(response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_download_url(self, result: SearchResult) -> str:
        """Get the download URL for a search result.

        Args:
            result: SearchResult to get download URL for.

        Returns:
            Download URL string.
        """
        if result.download_url:
            return result.download_url
        return f"https://download.dataspace.copernicus.eu/odata/v1/Products({result.id})/$value"

    def get_quicklook_url(self, product_id: str) -> str:
        """Get the quicklook/thumbnail URL for a product.

        Args:
            product_id: UUID of the product.

        Returns:
            Quicklook URL string.
        """
        return f"{self.base_url}({product_id})/Quicklook/$value"

    def search_by_name(
        self,
        name_pattern: str,
        collection: Optional[str] = None,
        max_results: int = 100,
    ) -> List[SearchResult]:
        """Search for products by name pattern.

        Args:
            name_pattern: Name pattern to search for (supports wildcards).
            collection: Optional collection to filter by.
            max_results: Maximum number of results.

        Returns:
            List of SearchResult objects.
        """
        filters = [f"contains(Name,'{name_pattern}')"]

        if collection:
            filters.append(f"Collection/Name eq '{collection}'")

        query_params = {
            "$filter": " and ".join(filters),
            "$top": min(max_results, 1000),
            "$orderby": "ContentDate/Start desc",
            "$expand": "Attributes",
        }

        response = requests.get(
            self.base_url,
            params=query_params,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()

        results = []
        for product in response.json().get("value", []):
            results.append(SearchResult.from_odata_product(product))

        return results

    def count_products(
        self,
        collection: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count products matching the given criteria.

        Args:
            collection: Optional collection to filter by.
            start_date: Optional start date.
            end_date: Optional end date.

        Returns:
            Number of matching products.
        """
        filters = []

        if collection:
            filters.append(f"Collection/Name eq '{collection}'")

        if start_date:
            start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            filters.append(f"ContentDate/Start ge {start_str}")

        if end_date:
            end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            filters.append(f"ContentDate/Start le {end_str}")

        query_params = {"$count": "true", "$top": 0}

        if filters:
            query_params["$filter"] = " and ".join(filters)

        response = requests.get(
            self.base_url,
            params=query_params,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()

        return response.json().get("@odata.count", 0)
