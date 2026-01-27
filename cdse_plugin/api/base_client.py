"""Abstract base client for CDSE API clients."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .auth import AuthManager
    from .models import Collection, SearchParameters, SearchResult


class BaseClient(ABC):
    """Abstract base class for CDSE API clients.

    This class defines the interface that all API clients must implement.

    Attributes:
        auth_manager: Authentication manager for handling credentials.
        base_url: Base URL for the API.
    """

    def __init__(self, auth_manager: Optional["AuthManager"] = None):
        """Initialize the base client.

        Args:
            auth_manager: Optional authentication manager for authenticated requests.
        """
        self.auth_manager = auth_manager
        self.base_url: str = ""

    @abstractmethod
    def search(self, params: "SearchParameters") -> List["SearchResult"]:
        """Search for products matching the given parameters.

        Args:
            params: Search parameters including collection, bbox, dates, etc.

        Returns:
            List of SearchResult objects matching the criteria.

        Raises:
            Exception: If the search request fails.
        """
        pass

    @abstractmethod
    def get_collections(self) -> List["Collection"]:
        """Get available collections from the API.

        Returns:
            List of Collection objects.

        Raises:
            Exception: If the request fails.
        """
        pass

    @abstractmethod
    def get_collection(self, collection_id: str) -> Optional["Collection"]:
        """Get details for a specific collection.

        Args:
            collection_id: ID of the collection to retrieve.

        Returns:
            Collection object or None if not found.

        Raises:
            Exception: If the request fails.
        """
        pass

    def _get_headers(self, authenticated: bool = False) -> dict:
        """Get HTTP headers for requests.

        Args:
            authenticated: Whether to include authentication header.

        Returns:
            Dictionary of HTTP headers.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if authenticated and self.auth_manager:
            auth_header = self.auth_manager.get_auth_header()
            if auth_header:
                headers.update(auth_header)

        return headers
