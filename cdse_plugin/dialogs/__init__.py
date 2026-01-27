"""UI dialog components for CDSE Plugin."""

from .cog_viewer_dialog import COGViewerDialog, show_cog_viewer
from .download_dialog import DownloadDialog
from .results_dock import ResultsDock
from .search_dock import SearchDock
from .settings_dock import SettingsDock
from .update_checker import (
    UpdateCheckerDialog,
    check_for_updates,
    get_current_version,
    show_update_dialog,
)

__all__ = [
    "SearchDock",
    "ResultsDock",
    "SettingsDock",
    "DownloadDialog",
    "UpdateCheckerDialog",
    "check_for_updates",
    "get_current_version",
    "show_update_dialog",
    "COGViewerDialog",
    "show_cog_viewer",
]
