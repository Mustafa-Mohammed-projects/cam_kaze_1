"""
camera_screen.py
=================
Captures a photo via Intent.ACTION_IMAGE_CAPTURE (the system camera app)
instead of Kivy's built-in Camera widget, because Kivy Camera is unstable
on Android 13+ with the modern camera2 stack and doesn't yield good quality.
Using the system camera:
  - Works across virtually all devices and permission models.
  - No need to manage TextureView/SurfaceView manually.
  - Requires FileProvider to give the system a place to write the photo to.

Workflow:
  1. Request CAMERA permission at runtime, only when needed.
  2. Create an empty file in cache_dir (never saved permanently).
  3. Get a content:// URI for it via FileProvider and pass it as EXTRA_OUTPUT.
  4. Once the system camera returns (onActivityResult), encrypt the file
     immediately.
  5. Securely delete the unencrypted temp file (zero-overwrite then remove).
"""
import os
import uuid

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock

from utils import android_utils as au
from utils.crypto_utils import secure_delete


class CameraScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self._pending_tmp_path = None

        root = BoxLayout(orientation="vertical", padding=24, spacing=16)
        root.add_widget(Label(text="Capture a secure photo", font_size="22sp",
                              size_hint_y=None, height=48))

        self.status_label = Label(text="Tap to start")
        root.add_widget(self.status_label)

        capture_btn = Button(text="Open Camera", size_hint_y=None, height=64)
        capture_btn.bind(on_release=lambda *_: self.start_capture())
        root.add_widget(capture_btn)

        back_btn = Button(text="Back", size_hint_y=None, height=56)
        back_btn.bind(on_release=lambda *_: self.app.go_home())
        root.add_widget(back_btn)

        self.add_widget(root)

    def set_status(self, text):
        self.status_label.text = text

    # ------------------------------------------------------------------
    def start_capture(self):
        au.request_camera_permission(self._on_permission_result)

    def _on_permission_result(self, granted):
        if not granted:
            self.set_status("Camera permission denied")
            au.toast("Cannot open camera without permission")
            return
        self._launch_camera_intent()

    def _launch_camera_intent(self):
        if not au.is_android():
            self.set_status("Camera only available on Android (test run)")
            return
        try:
            from jnius import autoclass, cast

            Intent = autoclass("android.content.Intent")
            MediaStore = autoclass("android.provider.MediaStore")
            File = autoclass("java.io.File")

            tmp_name = "capture_%s.jpg" % uuid.uuid4().hex[:10]
            tmp_dir = au.ensure_dir(os.path.join(au.cache_dir(), "captures"))
            tmp_path = os.path.join(tmp_dir, tmp_name)
            # Pre-create the file so FileProvider can locate it
            open(tmp_path, "wb").close()
            self._pending_tmp_path = tmp_path

            uri = au.file_to_content_uri(tmp_path)

            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            intent.putExtra(MediaStore.EXTRA_OUTPUT, cast("android.os.Parcelable", uri))
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)

            au.register_activity_result(au.REQUEST_CAMERA, self._on_camera_result)
            au.get_activity().startActivityForResult(intent, au.REQUEST_CAMERA)
            self.set_status("Opening camera...")
        except Exception as e:  # noqa
            self.set_status("Failed to open camera: %s" % e)
            au.toast("Camera error")

    def _on_camera_result(self, request_code, result_code, data):
        au.unregister_activity_result(au.REQUEST_CAMERA)
        tmp_path = self._pending_tmp_path
        self._pending_tmp_path = None

        if result_code != au.RESULT_OK:
            self.set_status("Photo capture cancelled")
            if tmp_path and os.path.exists(tmp_path):
                secure_delete(tmp_path)
            return

        # Defer encryption by one frame via Clock so the UI doesn't freeze
        # while reading/writing (AES is fast, but this keeps things smooth).
        Clock.schedule_once(lambda dt: self._encrypt_and_store(tmp_path), 0)

    def _encrypt_and_store(self, tmp_path):
        try:
            if not tmp_path or not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                self.set_status("No photo was found")
                return

            storage = self.app.storage
            km = self.app.key_manager

            enc_name = storage.new_enc_filename()
            enc_path = storage.photo_path({"filename": enc_name})
            km.encrypt_file(tmp_path, enc_path)

            storage.add_photo(enc_name)

            self.set_status("Photo captured and encrypted successfully")
            au.toast("Saved securely")
        except Exception as e:  # noqa
            self.set_status("Encryption failed: %s" % e)
            au.toast("An error occurred during encryption")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                secure_delete(tmp_path)
