"""
settings_screen.py
===================
Simple screen showing the current encryption mode (Keystore or password),
and lets the user set/change a password if Android Keystore isn't usable
on this device.
"""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from utils import android_utils as au
from utils.crypto_utils import CryptoError


class SettingsScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

        self.root_box = BoxLayout(orientation="vertical", padding=24, spacing=16)
        self.add_widget(self.root_box)
        self._build()

    def on_enter(self):
        self._build()

    def _build(self):
        self.root_box.clear_widgets()
        km = self.app.key_manager

        self.root_box.add_widget(Label(text="Settings", font_size="22sp",
                                       size_hint_y=None, height=48))

        mode_text = {
            "keystore": "Key mode: Android Keystore (system-level security)",
            "password": "Key mode: Password",
            None: "Encryption not initialized yet",
        }.get(km.mode, "Unknown")
        self.root_box.add_widget(Label(text=mode_text))

        if km.mode == "password":
            self.pw_input = TextInput(hint_text="Enter password", password=True,
                                      multiline=False, size_hint_y=None, height=48)
            self.root_box.add_widget(self.pw_input)
            unlock_btn = Button(text="Unlock", size_hint_y=None, height=56)
            unlock_btn.bind(on_release=lambda *_: self._unlock())
            self.root_box.add_widget(unlock_btn)

        if km.mode is None:
            self.new_pw_input = TextInput(hint_text="New password (6+ characters)",
                                          password=True, multiline=False,
                                          size_hint_y=None, height=48)
            self.root_box.add_widget(self.new_pw_input)
            setup_btn = Button(text="Set Password", size_hint_y=None, height=56)
            setup_btn.bind(on_release=lambda *_: self._setup_password())
            self.root_box.add_widget(setup_btn)

        back_btn = Button(text="Back", size_hint_y=None, height=56)
        back_btn.bind(on_release=lambda *_: self.app.go_home())
        self.root_box.add_widget(back_btn)

    def _setup_password(self):
        try:
            self.app.key_manager.setup_password(self.new_pw_input.text)
            au.toast("Password set")
            self.app.go_home()
        except CryptoError as e:
            au.toast(str(e))

    def _unlock(self):
        ok = self.app.key_manager.unlock_with_password(self.pw_input.text)
        if ok:
            au.toast("Unlocked")
            self.app.go_home()
        else:
            au.toast("Wrong password")
