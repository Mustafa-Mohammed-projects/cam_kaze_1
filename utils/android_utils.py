"""
android_utils.py
================
Android helpers via pyjnius: permissions, the Activity, FileProvider, Intent
results, Toast, and private folders.
"""
import os
from kivy.utils import platform

_ACTIVITY_RESULT_HANDLERS = {}
_BOUND = False

REQUEST_CAMERA = 9001
REQUEST_SAVE = 9002


def is_android():
    return platform == "android"


# ---------------------------------------------------------------------------
# Activity + Context
# ---------------------------------------------------------------------------
def get_activity():
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    return PythonActivity.mActivity


def get_package_name():
    return get_activity().getPackageName()


def get_authority():
    """Must match the authorities declared for FileProvider in the manifest."""
    return get_package_name() + ".fileprovider"


# ---------------------------------------------------------------------------
# Intent results (onActivityResult)
# ---------------------------------------------------------------------------
def register_activity_result(request_code, callback):
    """callback(request_code, result_code, intent)"""
    global _BOUND
    if not is_android():
        return
    from android import activity  # noqa
    _ACTIVITY_RESULT_HANDLERS[request_code] = callback
    if not _BOUND:
        activity.bind(on_activity_result=_on_activity_result)
        _BOUND = True


def unregister_activity_result(request_code):
    _ACTIVITY_RESULT_HANDLERS.pop(request_code, None)


def _on_activity_result(request_code, result_code, intent):
    handler = _ACTIVITY_RESULT_HANDLERS.get(request_code)
    if handler:
        try:
            handler(request_code, result_code, intent)
        except Exception as e:  # noqa
            print("[android] activity result handler error:", repr(e))


RESULT_OK = -1  # Activity.RESULT_OK


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
def has_camera_permission():
    if not is_android():
        return True
    from android.permissions import check_permission, Permission  # noqa
    return check_permission(Permission.CAMERA)


def request_camera_permission(callback):
    """callback(granted: bool). Requested at runtime, only when needed."""
    if not is_android():
        callback(True)
        return
    from android.permissions import request_permissions, Permission, check_permission  # noqa
    if check_permission(Permission.CAMERA):
        callback(True)
        return

    def _cb(permissions, grants):
        callback(bool(grants) and all(grants))

    request_permissions([Permission.CAMERA], _cb)


# ---------------------------------------------------------------------------
# FileProvider
# ---------------------------------------------------------------------------
def file_to_content_uri(path):
    from jnius import autoclass
    File = autoclass("java.io.File")
    FileProvider = autoclass("androidx.core.content.FileProvider")
    return FileProvider.getUriForFile(get_activity(), get_authority(), File(path))


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------
def toast(message):
    if not is_android():
        print("[toast]", message)
        return
    from android.runnable import run_on_ui_thread  # noqa
    from jnius import autoclass, cast

    @run_on_ui_thread
    def _show():
        Toast = autoclass("android.widget.Toast")
        String = autoclass("java.lang.String")
        Toast.makeText(get_activity(), cast("java.lang.CharSequence", String(message)),
                       Toast.LENGTH_SHORT).show()

    _show()


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def cache_dir():
    """The app's private cache directory (matches cache-path in file_paths.xml)."""
    if is_android():
        return get_activity().getCacheDir().getAbsolutePath()
    import tempfile
    return tempfile.gettempdir()


def shared_tmp_dir():
    """The folder FileProvider is allowed to share files from: <cache>/shared/"""
    return ensure_dir(os.path.join(cache_dir(), "shared"))


def clear_shared_tmp():
    """Deletes all decrypted temp files (on startup/shutdown)."""
    d = os.path.join(cache_dir(), "shared")
    if not os.path.isdir(d):
        return
    for name in os.listdir(d):
        p = os.path.join(d, name)
        try:
            if os.path.isfile(p):
                # Zero-overwrite then delete
                from utils.crypto_utils import secure_delete
                secure_delete(p)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Prevent screenshots (optional)
# ---------------------------------------------------------------------------
def set_secure_window(enabled=True):
    """FLAG_SECURE blocks screenshots and the recent-apps thumbnail preview."""
    if not is_android():
        return
    from android.runnable import run_on_ui_thread  # noqa
    from jnius import autoclass

    @run_on_ui_thread
    def _apply():
        LayoutParams = autoclass("android.view.WindowManager$LayoutParams")
        window = get_activity().getWindow()
        if enabled:
            window.addFlags(LayoutParams.FLAG_SECURE)
        else:
            window.clearFlags(LayoutParams.FLAG_SECURE)

    _apply()


# ---------------------------------------------------------------------------
# Reading/writing a URI via ContentResolver (for SAF)
# ---------------------------------------------------------------------------
def write_bytes_to_uri(uri, data):
    """Writes bytes to a content:// URI. Uses ParcelFileDescriptor + FileOutputStream."""
    from jnius import autoclass, cast
    resolver = get_activity().getContentResolver()
    stream = resolver.openOutputStream(uri, "wt")
    try:
        # Write in chunks to avoid huge single conversions
        chunk = 64 * 1024
        for i in range(0, len(data), chunk):
            part = data[i:i + chunk]
            stream.write(part, 0, len(part))
        stream.flush()
    finally:
        stream.close()
