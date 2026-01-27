"""
CDSE Plugin - Copernicus Data Space Ecosystem Plugin for QGIS.

This plugin provides access to satellite data from the Copernicus Data Space
Ecosystem (CDSE), including Sentinel-1/2/3/5P/6, Copernicus DEM, and Landsat data.
"""


def classFactory(iface):
    """Load the CDSE Plugin class.

    Args:
        iface: A QGIS interface instance providing access to the QGIS
            application components.

    Returns:
        CDSEPlugin: The plugin instance.
    """
    from .cdse_plugin import CDSEPlugin

    return CDSEPlugin(iface)
