"""
buildozer_hooks.py
===================
A post-build hook for python-for-android that:
  1. Copies file_paths.xml into res/xml/file_paths.xml inside the APK/AAB.
  2. Injects a <provider> block (androidx.core.content.FileProvider) into
     the final AndroidManifest.xml, if not already present.

This solves a common problem: buildozer has no declarative way to add a
full <provider> element to AndroidManifest.xml, so we do it programmatically
and safely (idempotent: won't duplicate the insertion if the build runs
more than once).

Enabled via buildozer.spec:
    p4a.hook = buildozer_hooks.py
"""
import os
import re
import shutil


PROVIDER_BLOCK = """
    <provider
        android:name="androidx.core.content.FileProvider"
        android:authorities="${applicationId}.fileprovider"
        android:exported="false"
        android:grantUriPermissions="true">
        <meta-data
            android:name="android.support.FILE_PROVIDER_PATHS"
            android:resource="@xml/file_paths" />
    </provider>
"""


def _find_manifest(dist_dir):
    for root, _dirs, files in os.walk(dist_dir):
        if "AndroidManifest.xml" in files:
            return os.path.join(root, "AndroidManifest.xml")
    return None


def _find_res_dir(manifest_path):
    # AndroidManifest.xml is normally at the same level as the res/ folder
    base = os.path.dirname(manifest_path)
    res = os.path.join(base, "res")
    return res if os.path.isdir(res) else None


def inject_file_provider(dist_dir, project_dir):
    manifest_path = _find_manifest(dist_dir)
    if not manifest_path:
        print("[buildozer_hooks] AndroidManifest.xml not found")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "androidx.core.content.FileProvider" in content:
        print("[buildozer_hooks] FileProvider already present, skipping injection")
    else:
        content = re.sub(r"</application\s*>", PROVIDER_BLOCK + "</application>",
                         content, count=1)
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[buildozer_hooks] Injected FileProvider block into AndroidManifest.xml")

    res_dir = _find_res_dir(manifest_path)
    if res_dir:
        xml_dir = os.path.join(res_dir, "xml")
        os.makedirs(xml_dir, exist_ok=True)
        src = os.path.join(project_dir, "file_paths.xml")
        dst = os.path.join(xml_dir, "file_paths.xml")
        if os.path.exists(src):
            shutil.copyfile(src, dst)
            print("[buildozer_hooks] Copied file_paths.xml to", dst)
        else:
            print("[buildozer_hooks] Warning: file_paths.xml not found in", project_dir)
    else:
        print("[buildozer_hooks] Warning: res/ directory not found")


def after_apk_build(state):
    """Called automatically by p4a if its hook interface supports this name.
    We also support invoking this module directly as a post-build script
    (see below)."""
    try:
        dist_dir = state.dist_dir
        project_dir = os.path.dirname(os.path.abspath(__file__))
        inject_file_provider(dist_dir, project_dir)
    except Exception as e:  # noqa
        print("[buildozer_hooks] after_apk_build error:", repr(e))


if __name__ == "__main__":
    # Allows running it manually: python buildozer_hooks.py <dist_dir>
    import sys
    if len(sys.argv) > 1:
        inject_file_provider(sys.argv[1], os.path.dirname(os.path.abspath(__file__)))
