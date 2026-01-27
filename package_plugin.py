#!/usr/bin/env python3
"""Packaging script for CDSE Plugin.

This script creates a distributable ZIP file for the QGIS plugin repository.
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path


def get_version_from_metadata(metadata_path: Path) -> str:
    """Extract version from metadata.txt.

    Args:
        metadata_path: Path to metadata.txt file.

    Returns:
        Version string.

    Raises:
        ValueError: If version cannot be found.
    """
    with open(metadata_path, "r") as f:
        for line in f:
            if line.startswith("version="):
                return line.split("=", 1)[1].strip()
    raise ValueError("Version not found in metadata.txt")


def should_include_file(filepath: Path, exclude_patterns: list) -> bool:
    """Check if a file should be included in the package.

    Args:
        filepath: Path to the file.
        exclude_patterns: List of patterns to exclude.

    Returns:
        True if file should be included, False otherwise.
    """
    filepath_str = str(filepath)

    for pattern in exclude_patterns:
        if re.search(pattern, filepath_str):
            return False

    return True


def create_package(
    source_dir: Path,
    output_dir: Path,
    plugin_name: str = "cdse_plugin",
    exclude_patterns: list = None,
) -> Path:
    """Create a ZIP package for the plugin.

    Args:
        source_dir: Path to the plugin source directory.
        output_dir: Path to the output directory for the ZIP file.
        plugin_name: Name of the plugin directory in the ZIP.
        exclude_patterns: List of regex patterns to exclude.

    Returns:
        Path to the created ZIP file.
    """
    if exclude_patterns is None:
        exclude_patterns = [
            r"__pycache__",
            r"\.pyc$",
            r"\.pyo$",
            r"\.git",
            r"\.DS_Store",
            r"\.env$",
            r"\.venv",
            r"\.idea",
            r"\.vscode",
            r"\.pytest_cache",
            r"\.mypy_cache",
            r"\.ruff_cache",
            r"\.coverage",
            r"htmlcov",
            r"\.egg-info",
            r"dist/",
            r"build/",
            r"tests/",
        ]

    # Get version from metadata
    metadata_path = source_dir / "metadata.txt"
    version = get_version_from_metadata(metadata_path)

    # Create output filename
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_filename = f"{plugin_name}-{version}.zip"
    zip_path = output_dir / zip_filename

    print(f"Creating package: {zip_path}")

    # Create ZIP file
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            # Filter directories in-place
            dirs[:] = [
                d for d in dirs if should_include_file(Path(root) / d, exclude_patterns)
            ]

            for file in files:
                filepath = Path(root) / file

                if not should_include_file(filepath, exclude_patterns):
                    continue

                # Calculate archive path
                rel_path = filepath.relative_to(source_dir.parent)
                print(f"  Adding: {rel_path}")
                zf.write(filepath, rel_path)

    print(f"\nPackage created: {zip_path}")
    print(f"Size: {zip_path.stat().st_size / 1024:.1f} KB")

    return zip_path


def validate_package(zip_path: Path, plugin_name: str = "cdse_plugin") -> bool:
    """Validate that the package contains required files.

    Args:
        zip_path: Path to the ZIP file.
        plugin_name: Expected plugin directory name.

    Returns:
        True if valid, False otherwise.
    """
    required_files = [
        f"{plugin_name}/__init__.py",
        f"{plugin_name}/metadata.txt",
        f"{plugin_name}/cdse_plugin.py",
    ]

    print(f"\nValidating package: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        for required in required_files:
            if required not in names:
                print(f"  MISSING: {required}")
                return False
            print(f"  OK: {required}")

    print("Validation passed!")
    return True


def main():
    """Main entry point for the packaging script."""
    parser = argparse.ArgumentParser(
        description="Package CDSE Plugin for distribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python package_plugin.py                    # Create package in dist/
    python package_plugin.py --output ./build   # Custom output directory
    python package_plugin.py --no-validate      # Skip validation
        """,
    )

    parser.add_argument(
        "--source",
        type=Path,
        help="Plugin source directory (default: ./cdse_plugin)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist"),
        help="Output directory for ZIP file (default: ./dist)",
    )
    parser.add_argument(
        "--name",
        default="cdse_plugin",
        help="Plugin directory name in ZIP (default: cdse_plugin)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip package validation",
    )

    args = parser.parse_args()

    # Get source directory
    script_dir = Path(__file__).parent
    source_dir = args.source or (script_dir / "cdse_plugin")

    if not source_dir.exists():
        print(f"Error: Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    # Create package
    try:
        zip_path = create_package(source_dir, args.output, args.name)
    except Exception as e:
        print(f"Error creating package: {e}", file=sys.stderr)
        return 1

    # Validate
    if not args.no_validate:
        if not validate_package(zip_path, args.name):
            print("Package validation failed!", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
