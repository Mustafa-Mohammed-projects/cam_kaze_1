[app]

# ---------------------------------------------------------------------------
# General info
# ---------------------------------------------------------------------------
title = Secure Camera
package.name = securecamerakivy
package.domain = org.example.securecamerakivy

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,xml
source.include_patterns = assets/*,file_paths.xml,android_manifest_additions.xml

version = 0.1.0

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
# Compatibility notes (important):
#  - pyjnius, android: core p4a tooling, built locally for each architecture.
#  - cryptography: needs a dedicated p4a recipe (bundled by default:
#    recipes/cryptography) and depends on openssl, which is also built as a
#    recipe (pulled in automatically as a dependency).
#  - We use the system camera via an Intent rather than the camera4kivy
#    library, so it isn't required here. If you later want a live camera
#    preview embedded in the app, add: camera4kivy
requirements = python3,kivy==2.3.1,pyjnius,android,cryptography,openssl,pillow

# ---------------------------------------------------------------------------
# Permissions (Android 13+)
# ---------------------------------------------------------------------------
# Never add WRITE_EXTERNAL_STORAGE or READ_EXTERNAL_STORAGE:
#   - Capture via FileProvider needs no storage permission at all.
#   - Saving via SAF (ACTION_CREATE_DOCUMENT) needs no storage permission
#     either.
# CAMERA is requested at runtime from the code (utils/android_utils.py) only
# when needed, but it must be declared here so the system can grant it.
android.permissions = CAMERA

# ---------------------------------------------------------------------------
# API / SDK / NDK settings — Android 13/14 (API 33/34)
# ---------------------------------------------------------------------------
# targetSdkVersion. Use 34 (Android 14), which is compatible with Android 13+
# devices and matches current Google Play requirements as of writing. If
# Play Console later requires a higher API (35+), only raise this value once
# you've confirmed your buildozer/python-for-android version supports it.
android.api = 34

# Minimum supported version: 24 (Android 7) balances device compatibility
# with the ability to safely use modern Keystore/GCM features. Change it if
# you want to support older devices.
android.minapi = 24

# Deliberately left blank: buildozer will automatically use the NDK version
# recommended by the current python-for-android release (currently NDK 25b
# or newer), which is safer than pinning a number that may become
# unsupported later.
#android.ndk =
android.ndk_api = 24

android.archs = arm64-v8a

# AndroidX is required because FileProvider here is androidx.core.content.FileProvider
android.enable_androidx = True

# (Optional) Build an AAB instead of an APK if you later publish to Google Play
#android.release_artifact = aab

# ---------------------------------------------------------------------------
# FileProvider: injecting <provider> and res/xml/file_paths.xml
# ---------------------------------------------------------------------------
# buildozer has no declarative option to add a full <provider> element, so
# we use a post-build hook (buildozer_hooks.py) that automatically injects
# it into the final AndroidManifest.xml and copies file_paths.xml into
# res/xml/. Run it manually after any "buildozer android debug" if it isn't
# invoked automatically by your CI (the included
# .github/workflows/build.yml calls it explicitly as an extra step for
# compatibility across buildozer versions, since p4a.hook support for this
# varies):
#     python buildozer_hooks.py .buildozer/android/platform/build-<arch>/dists/<distname>

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
orientation = portrait
fullscreen = 0

# ---------------------------------------------------------------------------
[buildozer]
log_level = 2
warn_on_root = 1

[app:android.gradle_dependencies]
androidx.core:core:1.13.1

android.release_artifact = apk
android.keystore =
android.keystore_passwd =
android.keyalias =
android.keyalias_passwd =
