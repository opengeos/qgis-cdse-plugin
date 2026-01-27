"""Configuration constants for CDSE Plugin."""

# API URLs
STAC_API_URL = "https://stac.dataspace.copernicus.eu/v1/"
ODATA_API_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

# GitHub repository info for update checker
GITHUB_REPO = "opengeos/qgis-cdse-plugin"
GITHUB_BRANCH = "main"
PLUGIN_PATH = "cdse_plugin"

# OAuth2 client ID
CLIENT_ID = "cdse-public"

# Default search parameters
DEFAULT_CLOUD_COVER = 30
DEFAULT_DATE_RANGE_DAYS = 30
DEFAULT_MAX_RESULTS = 100

# Collection categories for organizing in UI (maps prefix to display category)
COLLECTION_CATEGORIES = {
    "sentinel-1": "Sentinel-1",
    "sentinel-2": "Sentinel-2",
    "sentinel-3": "Sentinel-3",
    "sentinel-5p": "Sentinel-5P",
    "sentinel-6": "Sentinel-6",
    "cop-dem": "Copernicus DEM",
    "landsat": "Landsat",
    "global-mosaics": "Global Mosaics",
}

# Keywords that indicate cloud cover support
CLOUD_COVER_KEYWORDS = ["sentinel-2", "sentinel-3-olci", "landsat"]

# Download settings
DEFAULT_DOWNLOAD_DIR = ""
MAX_CONCURRENT_DOWNLOADS = 3
CHUNK_SIZE = 8192

# UI settings
THUMBNAIL_SIZE = 64
FOOTPRINT_COLOR = "#3388ff"
FOOTPRINT_OPACITY = 0.3
