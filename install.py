#!/usr/bin/env python3
"""Cross-platform installation script for CDSE Plugin.

This script installs the CDSE Plugin to the QGIS plugins directory.
"""

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path


def get_qgis_plugins_dir() -> Path:
    """Get the QGIS plugins directory for the current platform.

    Returns:
        Path to the QGIS plugins directory.

    Raises:
        RuntimeError: If the plugins directory cannot be determined.
    """
    system = platform.system()

    if system == "Windows":
        # Windows: %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins
        appdata = os.environ.get("APPDATA")
        if appdata:
            return (
                Path(appdata)
                / "QGIS"
                / "QGIS3"
                / "profiles"
                / "default"
                / "python"
                / "plugins"
            )

    elif system == "Darwin":
        # macOS: ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "QGIS"
            / "QGIS3"
            / "profiles"
            / "default"
            / "python"
            / "plugins"
        )

    elif system == "Linux":
        # Linux: ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins
        return (
            Path.home()
            / ".local"
            / "share"
            / "QGIS"
            / "QGIS3"
            / "profiles"
            / "default"
            / "python"
            / "plugins"
        )

    raise RuntimeError(f"Unsupported platform: {system}")


def install_plugin(
    source_dir: Path,
    plugins_dir: Path,
    plugin_name: str = "cdse_plugin",
    force: bool = False,
) -> bool:
    """Install the plugin to the QGIS plugins directory.

    Args:
        source_dir: Path to the plugin source directory.
        plugins_dir: Path to the QGIS plugins directory.
        plugin_name: Name of the plugin directory.
        force: Whether to overwrite existing installation.

    Returns:
        True if installation succeeded, False otherwise.
    """
    target_dir = plugins_dir / plugin_name

    # Check if already installed
    if target_dir.exists():
        if force:
            print(f"Removing existing installation at {target_dir}")
            shutil.rmtree(target_dir)
        else:
            print(f"Plugin already installed at {target_dir}")
            print("Use --force to overwrite")
            return False

    # Create plugins directory if it doesn't exist
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # Copy plugin files
    print(f"Installing plugin to {target_dir}")
    shutil.copytree(source_dir, target_dir)

    print("Installation complete!")
    print("\nTo enable the plugin:")
    print("1. Open QGIS")
    print("2. Go to Plugins > Manage and Install Plugins")
    print("3. Find 'CDSE Plugin' and enable it")

    return True


def uninstall_plugin(plugins_dir: Path, plugin_name: str = "cdse_plugin") -> bool:
    """Uninstall the plugin from the QGIS plugins directory.

    Args:
        plugins_dir: Path to the QGIS plugins directory.
        plugin_name: Name of the plugin directory.

    Returns:
        True if uninstallation succeeded, False otherwise.
    """
    target_dir = plugins_dir / plugin_name

    if not target_dir.exists():
        print(f"Plugin not installed at {target_dir}")
        return False

    print(f"Removing plugin from {target_dir}")
    shutil.rmtree(target_dir)
    print("Uninstallation complete!")

    return True


def main():
    """Main entry point for the installation script."""
    parser = argparse.ArgumentParser(
        description="Install CDSE Plugin for QGIS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python install.py                 # Install the plugin
    python install.py --force         # Force reinstall
    python install.py --uninstall     # Uninstall the plugin
    python install.py --path /custom  # Install to custom path
        """,
    )

    parser.add_argument(
        "--name",
        default="cdse_plugin",
        help="Plugin directory name (default: cdse_plugin)",
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="Custom QGIS plugins directory path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing installation",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall the plugin",
    )

    args = parser.parse_args()

    # Get plugins directory
    try:
        plugins_dir = args.path or get_qgis_plugins_dir()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"QGIS plugins directory: {plugins_dir}")

    # Get source directory
    script_dir = Path(__file__).parent
    source_dir = script_dir / "cdse_plugin"

    if not source_dir.exists():
        print(
            f"Error: Plugin source directory not found at {source_dir}", file=sys.stderr
        )
        return 1

    # Install or uninstall
    if args.uninstall:
        success = uninstall_plugin(plugins_dir, args.name)
    else:
        success = install_plugin(source_dir, plugins_dir, args.name, args.force)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
