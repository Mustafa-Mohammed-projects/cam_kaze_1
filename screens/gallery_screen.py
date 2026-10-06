"""
gallery_screen.py
==================
Displays the list of encrypted photos. When a photo is selected:
  - It is decrypted to a temp file in cache_dir (never permanent storage).
  - It is shown via kivy.uix.image.Image.
  - The temp file is securely deleted on leaving the screen or app close.

Sharing and saving call into utils/share_utils.py, each of which decrypts
to its own separate temp file that is deleted afterwards (on returning to
the app after sharing, or immediately after saving).
"""
import os
import uuid

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.clock import Clock

from utils import android_utils as au
from utils import share_utils
from utils.crypto_utils import secure_delete


class GalleryScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self._open_tmp_files = []  # currently-open temp files to delete on exit

        root = BoxLayout(orientation="vertical", padding=16, spacing=12)

        top = BoxLayout(size_hint_y=None, height=56, spacing=8)
        back_btn = Button(text="Back")
        back_btn.bind(on_release=lambda *_: self.app.go_home())
        top.add_widget(back_btn)
        top.add_widget(Label(text="Gallery", font_size="20sp"))
        refresh_btn = Button(text="Refresh")
        refresh_btn.bind(on_release=lambda *_: self.refresh())
        top.add_widget(refresh_btn)
        root.add_widget(top)

        self.grid = GridLayout(cols=3, spacing=6, size_hint_y=None, padding=4)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.grid)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_enter(self):
        self.refresh()

    def on_leave(self):
        self._cleanup_tmp_files()

    def _cleanup_tmp_files(self):
        for p in self._open_tmp_files:
            if os.path.exists(p):
                secure_delete(p)
        self._open_tmp_files = []

    # ------------------------------------------------------------------
    def refresh(self):
        self.grid.clear_widgets()
        entries = self.app.storage.list_photos()
        if not entries:
            self.grid.cols = 1
            self.grid.add_widget(Label(text="No photos yet",
                                       size_hint_y=None, height=48))
            return
        self.grid.cols = 3
        for entry in entries:
            self.grid.add_widget(self._build_thumb_button(entry))

    def _build_thumb_button(self, entry):
        btn = Button(text="Photo\n%s" % entry["id"][:6], size_hint_y=None, height=120,
                    halign="center")
        btn.bind(on_release=lambda *_: self.open_photo(entry))
        return btn

    # ------------------------------------------------------------------
    def open_photo(self, entry):
        try:
            enc_path = self.app.storage.photo_path(entry)
            tmp_path = os.path.join(au.shared_tmp_dir(), "view_%s.jpg" % uuid.uuid4().hex[:10])
            self.app.key_manager.decrypt_file(enc_path, tmp_path)
            self._open_tmp_files.append(tmp_path)
            self._show_photo_popup(entry, tmp_path)
        except Exception as e:  # noqa
            au.toast("Failed to open photo")
            print("[gallery] open error:", repr(e))

    def _show_photo_popup(self, entry, tmp_path):
        box = BoxLayout(orientation="vertical", spacing=8, padding=8)
        img = Image(source=tmp_path)
        box.add_widget(img)

        btns = BoxLayout(size_hint_y=None, height=56, spacing=6)
        share_btn = Button(text="Share")
        save_btn = Button(text="Save to Phone")
        delete_btn = Button(text="Delete")
        close_btn = Button(text="Close")
        for b in (share_btn, save_btn, delete_btn, close_btn):
            btns.add_widget(b)
        box.add_widget(btns)

        popup = Popup(title="View Photo", content=box, size_hint=(0.9, 0.9))

        share_btn.bind(on_release=lambda *_: self._share(entry))
        save_btn.bind(on_release=lambda *_: self._save(entry))
        delete_btn.bind(on_release=lambda *_: self._delete(entry, popup))
        close_btn.bind(on_release=lambda *_: popup.dismiss())

        popup.open()

    # ------------------------------------------------------------------
    def _share(self, entry):
        if not au.is_android():
            au.toast("Sharing is only available on Android")
            return
        try:
            enc_path = self.app.storage.photo_path(entry)
            tmp_path = share_utils.share_image(self.app.key_manager, enc_path)
            self._open_tmp_files.append(tmp_path)
        except Exception as e:  # noqa
            au.toast("Sharing failed")
            print("[gallery] share error:", repr(e))

    def _save(self, entry):
        if not au.is_android():
            au.toast("Saving via SAF is only available on Android")
            return
        enc_path = self.app.storage.photo_path(entry)
        suggested = "SecureCamera_%s.jpg" % entry["id"][:8]

        def _result(success, message):
            def _notify(dt):
                au.toast(message)
            Clock.schedule_once(_notify, 0)

        share_utils.save_copy_via_saf(self.app.key_manager, enc_path, suggested, _result)

    def _delete(self, entry, popup):
        try:
            enc_path = self.app.storage.photo_path(entry)
            secure_delete(enc_path)
            thumb_path = self.app.storage.thumb_path(entry)
            if thumb_path:
                secure_delete(thumb_path)
            self.app.storage.remove_photo(entry["id"])
            popup.dismiss()
            self.refresh()
            au.toast("Deleted")
        except Exception as e:  # noqa
            au.toast("Delete failed")
            print("[gallery] delete error:", repr(e))
