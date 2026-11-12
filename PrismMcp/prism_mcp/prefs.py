"""Where Prism keeps the user's settings, found the way Prism finds them (PrismCore.getUserPrefDir)."""

import json
import os


def documents_dir():
    """The user's Documents folder from the Windows Shell (right also when Documents is redirected, e.g. to OneDrive)."""
    try:
        import ctypes
        import ctypes.wintypes

        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL, SHGFP_TYPE_CURRENT
        if buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def user_prefs_dir():
    return os.environ.get("PRISM_USER_PREFS") or os.path.join(documents_dir(), "Prism2")


def user_config():
    """The user's Prism.json as a dict ({} when it does not exist or cannot be read)."""
    try:
        with open(os.path.join(user_prefs_dir(), "Prism.json"), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}
