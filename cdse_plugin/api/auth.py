"""Authentication manager for CDSE Plugin."""

import os
import time
from typing import Optional, Tuple

import requests

try:
    from qgis.core import QgsSettings
except ImportError:
    QgsSettings = None

from ..utils.config import TOKEN_URL

# Environment variable names (these are variable names, not secret values).
ENV_CLIENT_ID = "CDSE_CLIENT_ID"
ENV_CLIENT_SECRET = "CDSE_CLIENT_SECRET"  # nosec B105
ENV_AWS_ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID"
ENV_AWS_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"  # nosec B105


class AuthManager:
    """Manages authentication with the CDSE OAuth2 service.

    Supports two authentication methods:
    1. OAuth2 Client Credentials flow (client_id + client_secret)
    2. AWS S3 credentials for direct S3 access (access_key_id + secret_access_key)

    Credentials are stored persistently using QgsSettings.

    Attributes:
        access_token: Current OAuth2 access token.
        token_expiry: Unix timestamp when the access token expires.
    """

    SETTINGS_PREFIX = "cdse_plugin"

    def __init__(self):
        """Initialize the AuthManager."""
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._aws_access_key_id: Optional[str] = None
        self._aws_secret_access_key: Optional[str] = None
        self._load_stored_credentials()

    def _load_stored_credentials(self) -> None:
        """Load stored credentials from QgsSettings and environment variables.

        Priority: QgsSettings > Environment Variables
        """
        # Load from QgsSettings first
        if QgsSettings is not None:
            settings = QgsSettings()
            self._client_id = settings.value(f"{self.SETTINGS_PREFIX}/client_id", None)
            self._client_secret = settings.value(
                f"{self.SETTINGS_PREFIX}/client_secret", None
            )
            self._aws_access_key_id = settings.value(
                f"{self.SETTINGS_PREFIX}/aws_access_key_id", None
            )
            self._aws_secret_access_key = settings.value(
                f"{self.SETTINGS_PREFIX}/aws_secret_access_key", None
            )

        # Fall back to environment variables if not set
        if not self._client_id:
            self._client_id = os.environ.get(ENV_CLIENT_ID)
        if not self._client_secret:
            self._client_secret = os.environ.get(ENV_CLIENT_SECRET)
        if not self._aws_access_key_id:
            self._aws_access_key_id = os.environ.get(ENV_AWS_ACCESS_KEY_ID)
        if not self._aws_secret_access_key:
            self._aws_secret_access_key = os.environ.get(ENV_AWS_SECRET_ACCESS_KEY)

        # Configure GDAL with S3 credentials if available
        if self._aws_access_key_id and self._aws_secret_access_key:
            self._configure_gdal_s3()

        # Try to authenticate with stored/env credentials
        if self._client_id and self._client_secret:
            self._authenticate_with_client_credentials()

    def _save_credentials(self) -> None:
        """Save credentials to QgsSettings."""
        if QgsSettings is None:
            return

        settings = QgsSettings()
        if self._client_id:
            settings.setValue(f"{self.SETTINGS_PREFIX}/client_id", self._client_id)
        if self._client_secret:
            settings.setValue(
                f"{self.SETTINGS_PREFIX}/client_secret", self._client_secret
            )
        if self._aws_access_key_id:
            settings.setValue(
                f"{self.SETTINGS_PREFIX}/aws_access_key_id", self._aws_access_key_id
            )
        if self._aws_secret_access_key:
            settings.setValue(
                f"{self.SETTINGS_PREFIX}/aws_secret_access_key",
                self._aws_secret_access_key,
            )

    def _clear_credentials(self) -> None:
        """Clear stored credentials from QgsSettings."""
        if QgsSettings is None:
            return

        settings = QgsSettings()
        settings.remove(f"{self.SETTINGS_PREFIX}/client_id")
        settings.remove(f"{self.SETTINGS_PREFIX}/client_secret")
        settings.remove(f"{self.SETTINGS_PREFIX}/aws_access_key_id")
        settings.remove(f"{self.SETTINGS_PREFIX}/aws_secret_access_key")
        # Also remove old credentials if any
        settings.remove(f"{self.SETTINGS_PREFIX}/username")
        settings.remove(f"{self.SETTINGS_PREFIX}/refresh_token")
        settings.remove(f"{self.SETTINGS_PREFIX}/password")

    def set_oauth_credentials(
        self, client_id: str, client_secret: str
    ) -> Tuple[bool, str]:
        """Set OAuth2 client credentials and authenticate.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.

        Returns:
            Tuple of (success: bool, message: str).
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._save_credentials()

        return self._authenticate_with_client_credentials()

    def _authenticate_with_client_credentials(self) -> Tuple[bool, str]:
        """Authenticate using client credentials flow.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if not self._client_id or not self._client_secret:
            return False, "Client ID and secret are required"

        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 600)
                self.token_expiry = time.time() + expires_in - 60  # 60s buffer

                return True, "Authentication successful"

            elif response.status_code == 401:
                return False, "Invalid client ID or secret"
            else:
                error_msg = response.json().get("error_description", response.text)
                return False, f"Authentication failed: {error_msg}"

        except requests.exceptions.Timeout:
            return False, "Connection timed out"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to authentication server"
        except requests.exceptions.RequestException as e:
            return False, f"Authentication error: {str(e)}"

    def set_aws_credentials(
        self, access_key_id: str, secret_access_key: str
    ) -> Tuple[bool, str]:
        """Set AWS S3 credentials for direct S3 access.

        Args:
            access_key_id: AWS access key ID.
            secret_access_key: AWS secret access key.

        Returns:
            Tuple of (success: bool, message: str).
        """
        self._aws_access_key_id = access_key_id
        self._aws_secret_access_key = secret_access_key
        self._save_credentials()

        # Configure GDAL for S3 access
        self._configure_gdal_s3()

        return True, "AWS credentials saved"

    def _configure_gdal_s3(self) -> None:
        """Configure GDAL for S3 access with stored credentials."""
        if not self._aws_access_key_id or not self._aws_secret_access_key:
            return

        try:
            from osgeo import gdal

            gdal.SetConfigOption("AWS_ACCESS_KEY_ID", self._aws_access_key_id)
            gdal.SetConfigOption("AWS_SECRET_ACCESS_KEY", self._aws_secret_access_key)
            gdal.SetConfigOption("AWS_S3_ENDPOINT", "eodata.dataspace.copernicus.eu")
            gdal.SetConfigOption("AWS_HTTPS", "YES")
            gdal.SetConfigOption("AWS_VIRTUAL_HOSTING", "FALSE")
        except ImportError:
            pass

    def refresh_access_token(self) -> Tuple[bool, str]:
        """Refresh the access token using client credentials.

        Returns:
            Tuple of (success: bool, message: str).
        """
        return self._authenticate_with_client_credentials()

    def get_access_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary.

        Returns:
            Access token string or None if not authenticated.
        """
        if not self._client_id or not self._client_secret:
            return None

        # Check if token is expired or about to expire
        if not self.access_token or time.time() >= self.token_expiry:
            success, _ = self.refresh_access_token()
            if not success:
                return None

        return self.access_token

    def get_auth_header(self) -> Optional[dict]:
        """Get the Authorization header for API requests.

        Returns:
            Dict with Authorization header or None if not authenticated.
        """
        token = self.get_access_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return None

    def logout(self) -> None:
        """Clear authentication state and stored credentials."""
        self.access_token = None
        self.token_expiry = 0
        self._client_id = None
        self._client_secret = None
        self._aws_access_key_id = None
        self._aws_secret_access_key = None
        self._clear_credentials()

        # Clear GDAL config
        try:
            from osgeo import gdal

            gdal.SetConfigOption("AWS_ACCESS_KEY_ID", None)
            gdal.SetConfigOption("AWS_SECRET_ACCESS_KEY", None)
            gdal.SetConfigOption("GDAL_HTTP_HEADERS", None)
        except ImportError:
            pass

    def is_authenticated(self) -> bool:
        """Check if the user is currently authenticated with OAuth.

        Returns:
            True if authenticated with a valid token, False otherwise.
        """
        return self.get_access_token() is not None

    def has_aws_credentials(self) -> bool:
        """Check if AWS S3 credentials are configured.

        Returns:
            True if AWS credentials are set, False otherwise.
        """
        return bool(self._aws_access_key_id and self._aws_secret_access_key)

    @property
    def client_id(self) -> Optional[str]:
        """Get the current client ID.

        Returns:
            Client ID string or None if not set.
        """
        return self._client_id

    @property
    def aws_access_key_id(self) -> Optional[str]:
        """Get the current AWS access key ID.

        Returns:
            AWS access key ID or None if not set.
        """
        return self._aws_access_key_id

    @property
    def username(self) -> Optional[str]:
        """Get the current username (client ID for display).

        Returns:
            Client ID string or None if not logged in.
        """
        return self._client_id

    def test_connection(self) -> Tuple[bool, str]:
        """Test the authentication by making a simple API request.

        Returns:
            Tuple of (success: bool, message: str).
        """
        token = self.get_access_token()
        if not token:
            return False, "Not authenticated"

        try:
            # Test with a simple STAC request
            response = requests.get(
                "https://stac.dataspace.copernicus.eu/v1/collections",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if response.status_code == 200:
                return True, "OAuth connection successful"
            else:
                return False, f"Token validation failed: {response.status_code}"

        except requests.exceptions.RequestException as e:
            return False, f"Connection test failed: {str(e)}"

    def test_s3_connection(self) -> Tuple[bool, str]:
        """Test the S3 credentials by making a simple request.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if not self.has_aws_credentials():
            return False, "AWS credentials not configured"

        # Configure GDAL first
        self._configure_gdal_s3()

        try:
            from osgeo import gdal

            # Try to open a known DEM file
            test_path = "/vsis3/eodata/auxdata/CopDEM_COG/copernicus-dem-30m/"
            ds = gdal.OpenEx(test_path, gdal.OF_READONLY | gdal.OF_VERBOSE_ERROR)

            if ds is not None:
                ds = None  # Close
                return True, "S3 connection successful"
            else:
                return False, "S3 connection failed - check credentials"

        except Exception as e:
            return False, f"S3 test failed: {str(e)}"

    def apply_gdal_config(self) -> None:
        """Apply all stored credentials to GDAL configuration.

        This should be called when the plugin initializes to ensure
        GDAL has access to S3 credentials.
        """
        self._configure_gdal_s3()

        # Also set OAuth token for HTTP requests if available
        token = self.get_access_token()
        if token:
            try:
                from osgeo import gdal

                gdal.SetConfigOption(
                    "GDAL_HTTP_HEADERS", f"Authorization: Bearer {token}"
                )
            except ImportError:
                pass
