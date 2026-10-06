"""
main.py
=======
Entry point for the SecureCameraKivy app.

Startup flow:
  1. Initialize StorageManager (photo index) and KeyManager (encryption key).
  2. Try to activate Android Keystore automatically (no user interaction needed).
  3. If that fails (older device without Keystore support), show the Settings
     screen so the user can set a password on first run.
  4. Show the home screen with: Capture Photo / Gallery / Settings.
"""
import os

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock

from utils import android_utils as au
from utils.crypto_utils import KeyManager
from utils.storage_manager import StorageManager


class HomeScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        root = BoxLayout(orientation="vertical", padding=32, spacing=20)

        root.add_widget(Label(text="Secure Camera", font_size="26sp",
                              size_hint_y=None, height=64))

        capture_btn = Button(text="Capture Photo", size_hint_y=None, height=72)
        capture_btn.bind(on_release=lambda *_: self.app.go_capture())
        root.add_widget(capture_btn)

        gallery_btn = Button(text="Gallery", size_hint_y=None, height=72)
        gallery_btn.bind(on_release=lambda *_: self.app.go_gallery())
        root.add_widget(gallery_btn)

        settings_btn = Button(text="Settings", size_hint_y=None, height=64)
        settings_btn.bind(on_release=lambda *_: self.app.go_settings())
        root.add_widget(settings_btn)

        root.add_widget(BoxLayout())  # spacer
        self.add_widget(root)


class SecureCameraApp(App):
    title = "Secure Camera"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.storage = None
        self.key_manager = None
        self.sm = None

    # ------------------------------------------------------------------
    def build(self):
        data_dir = self.user_data_dir
        os.makedirs(data_dir, exist_ok=True)

        self.storage = StorageManager(data_dir)
        self.key_manager = KeyManager(data_dir)

        # Clean up any leftover temp files from a previous session (e.g. a crash)
        au.clear_shared_tmp()

        self.sm = ScreenManager(transition=NoTransition())

        from screens.camera_screen import CameraScreen
        from screens.gallery_screen import GalleryScreen
        from screens.settings_screen import SettingsScreen

        self.sm.add_widget(HomeScreen(self, name="home"))
        self.sm.add_widget(CameraScreen(self, name="camera"))
        self.sm.add_widget(GalleryScreen(self, name="gallery"))
        self.sm.add_widget(SettingsScreen(self, name="settings"))

        Clock.schedule_once(lambda dt: self._init_key(), 0.1)

        return self.sm

    def _init_key(self):
        ok = self.key_manager.init_with_keystore()
        if ok:
            return
        if self.key_manager.mode == "password":
            au.toast("Please unlock from Settings")
            self.go_settings()
        elif self.key_manager.mode is None:
            au.toast("Please set a password in Settings")
            self.go_settings()

    # ------------------------------------------------------------------
    def go_home(self):
        self.sm.current = "home"

    def go_capture(self):
        if not self.key_manager.is_unlocked():
            au.toast("Please unlock from Settings first")
            self.go_settings()
            return
        self.sm.current = "camera"

    def go_gallery(self):
        if not self.key_manager.is_unlocked():
            au.toast("Please unlock from Settings first")
            self.go_settings()
            return
        self.sm.current = "gallery"

    def go_settings(self):
        self.sm.current = "settings"

    # ------------------------------------------------------------------
    def on_pause(self):
        # Allows returning to the app (e.g. after sharing via WhatsApp)
        # without terminating it
        return True

    def on_stop(self):
        au.clear_shared_tmp()
        if self.key_manager:
            self.key_manager.lock()


if __name__ == "__main__":
    SecureCameraApp().run()
