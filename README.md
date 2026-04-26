# QGIS CDSE Plugin

A QGIS plugin for accessing Copernicus Data Space Ecosystem (CDSE) satellite imagery.

## Features

- **Search satellite data** from Sentinel-1/2/3/5P/6, Copernicus DEM, and Landsat collections
- **Dual API support**: STAC API for modern access, OData API for additional datasets
- **Interactive footprint visualization** on the map canvas
- **Batch download capabilities** with progress tracking
- **Cloud cover filtering** for optical data (Sentinel-2, Landsat, etc.)
- **Thumbnail previews** in search results

## Supported Datasets

### Via STAC API
- Sentinel-1 (SAR, RTC)
- Sentinel-2 (MSI L1C/L2A)
- Sentinel-3 (OLCI/SLSTR/SRAL)
- Sentinel-5P (TROPOMI)
- Sentinel-6 (Altimetry)
- Copernicus DEM
- Landsat 5/7/8/9

### Via OData API (additional)
- SMOS (Soil Moisture)
- ENVISAT (MERIS/ASAR)
- MODIS (Terra/Aqua)

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/opengeos/qgis-cdse-plugin.git
   cd qgis-cdse-plugin
   ```

2. Run the installation script:
   ```bash
   python install.py
   ```

3. Open QGIS, go to **Plugins > Manage and Install Plugins**, and enable "CDSE Plugin".

### Manual Installation

1. Download the latest release ZIP file
2. In QGIS, go to **Plugins > Manage and Install Plugins > Install from ZIP**
3. Select the downloaded ZIP file and click "Install Plugin"

## Usage

### Authentication

To download products, you need a CDSE account:

1. Register at [dataspace.copernicus.eu](https://dataspace.copernicus.eu)
2. In QGIS, go to **CDSE Settings** and click "Login"
3. Enter your credentials

### Searching Data

1. Click the CDSE icon in the toolbar to open the search panel
2. Select a mission and collection
3. Set date range and bounding box (or click "Get from Map Canvas")
4. Adjust cloud cover filter if applicable
5. Click "Search"

### Downloading Data

1. Select results in the results table
2. Click "Download Selected"
3. Choose an output directory
4. Click "Start Download"

## Requirements

- QGIS 3.22 or later (including QGIS 4.0+)
- Python 3.8+
- requests >= 2.28.0

## Development

### Project Structure

```
qgis-cdse-plugin/
├── cdse_plugin/
│   ├── api/           # API clients (STAC, OData, Auth)
│   ├── dialogs/       # UI components
│   ├── workers/       # Background thread workers
│   ├── utils/         # Utility modules
│   └── icons/         # SVG icons
├── install.py         # Installation script
├── package_plugin.py  # Packaging script
└── requirements.txt
```

### Building

To create a distributable ZIP file:

```bash
python package_plugin.py
```

The package will be created in the `dist/` directory.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu) for providing open access to satellite data
- [QGIS](https://qgis.org) for the excellent GIS platform
