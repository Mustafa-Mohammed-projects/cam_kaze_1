# SecureCameraKivy

A Kivy app that captures photos and immediately encrypts them with
**AES-256-GCM**, storing them only inside the app's private storage space.
It supports sharing photos (WhatsApp, Messenger, etc.) and saving a copy to
the phone via Storage Access Framework — with no external storage
permission required. Built to be compatible with **Android 13/14
(API 33/34)**.

## Project structure

```
main.py                       Entry point + home screen
screens/
  camera_screen.py            Photo capture via system camera + immediate encryption
  gallery_screen.py           View/decrypt/share/save/delete photos
  settings_screen.py          Set up/unlock password (fallback mode)
utils/
  crypto_utils.py             AES-256-GCM + key management (Keystore or password)
  android_utils.py            Permissions, Activity results, FileProvider, Toast
  share_utils.py              Sharing (ACTION_SEND) and saving (ACTION_CREATE_DOCUMENT)
  storage_manager.py          JSON index of encrypted photos (metadata only)
buildozer.spec                Build settings (API 34 / minAPI 24)
android_manifest_additions.xml Reference for the <provider> block (auto-injected, see below)
file_paths.xml                FileProvider paths (captures/ and shared/)
buildozer_hooks.py             Script that auto-injects FileProvider into AndroidManifest.xml
.github/workflows/build.yml    Automatic APK build via GitHub Actions
```

## How the encryption works

1. On first launch, the app tries to generate an AES-256 key inside
   **Android Keystore** (never leaves the device, and generally can't be
   extracted even with root access).
2. If that fails (a device/emulator without Keystore support), the app asks
   the user to set a **password**, from which a key is derived via
   PBKDF2-HMAC-SHA256 (600,000 iterations).
3. Every photo is encrypted with AES-256-GCM using a random nonce per file;
   the 16-byte tag is automatically appended to the end of the ciphertext by
   the `cryptography` library.
4. No key is ever written explicitly in the source code.

## Building locally

```bash
pip install buildozer cython
sudo apt-get install -y git zip unzip openjdk-17-jdk autoconf libtool \
    pkg-config zlib1g-dev libffi-dev libssl-dev build-essential
buildozer android debug
```

The output (`bin/*.apk`) is produced by python-for-android, which
automatically downloads the SDK/NDK on first run (this can take a while).

### FileProvider injection

`buildozer.spec` has no declarative way to add a full `<provider>` element
to AndroidManifest.xml. After `buildozer android debug`, run:

```bash
python buildozer_hooks.py .buildozer/android/platform/build-*/dists/*
```

(the included GitHub Actions workflow does this automatically as an extra
safety step).

## Building via GitHub Actions

Push to the `main` or `master` branch, or trigger the workflow manually from
the Actions tab. The output (`SecureCameraKivy-debug-apk`) appears as a
downloadable **Artifact** on the run's page in GitHub.

The first run may take 20–40 minutes (downloading the SDK/NDK and building
every dependency from source); subsequent runs are faster thanks to
`actions/cache`.

## Known notes and expected limitations on Android 13/14

- **Camera**: we use `Intent.ACTION_IMAGE_CAPTURE` (the system camera app)
  instead of `kivy.uix.camera.Camera`, since the latter is unstable with the
  modern camera2 API on Android 13+. This means the capture UI is the
  device's default camera app, not something embedded inside the app's own
  screen.
- **`targetSdkVersion`**: set to 34 (Android 14) in `buildozer.spec`. If you
  plan to publish on Google Play later, check current Play requirements —
  you may eventually be required to raise it to 35; only do so once you've
  confirmed your buildozer/p4a version supports that level.
- **Permissions**: `CAMERA` only, requested at runtime. No storage
  permissions at all.
- **Android Keystore via pyjnius**: works reliably on most real devices
  from API 23+ onward. On some emulators (especially without Google Play
  Services) key generation may fail; in that case the app automatically
  falls back to password mode.
- **Android Auto Backup**: `user_data_dir` data (including encrypted photos
  and the wrapped Keystore key) may be included in Google's automatic
  backup by default. If privacy is critical, add
  `android:allowBackup="false"` to `<application>` in AndroidManifest.xml
  (this can be added by extending `buildozer_hooks.py` using the same
  approach as the `<provider>` injection).
- **Unit testing**: `utils/crypto_utils.py` and `utils/storage_manager.py`
  don't depend on Android and can be tested directly with plain Python on
  any development machine (as was done while building this project).
