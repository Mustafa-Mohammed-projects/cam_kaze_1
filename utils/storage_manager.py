"""
storage_manager.py
===================
Manages the index of encrypted photos (metadata only: id, filename, created_at).
The index itself is not sensitive (it holds no photo content), so it's stored
as plain JSON; you can easily encrypt it too if you want (swap json.dump for
key_manager.encrypt_bytes).
"""
import json
import os
import time
import uuid


class StorageManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.photos_dir = os.path.join(base_dir, "encrypted_photos")
        self.thumbs_dir = os.path.join(base_dir, "encrypted_thumbs")
        self.index_path = os.path.join(base_dir, "photos_index.json")
        os.makedirs(self.photos_dir, exist_ok=True)
        os.makedirs(self.thumbs_dir, exist_ok=True)
        if not os.path.exists(self.index_path):
            self._write_index([])

    def _read_index(self):
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write_index(self, items):
        tmp = self.index_path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.index_path)

    def list_photos(self):
        """Newest first."""
        items = self._read_index()
        return sorted(items, key=lambda x: x.get("created_at", 0), reverse=True)

    def add_photo(self, enc_filename, thumb_filename=None):
        items = self._read_index()
        entry = {
            "id": uuid.uuid4().hex,
            "filename": enc_filename,
            "thumb": thumb_filename,
            "created_at": time.time(),
        }
        items.append(entry)
        self._write_index(items)
        return entry

    def remove_photo(self, photo_id):
        items = self._read_index()
        items = [i for i in items if i["id"] != photo_id]
        self._write_index(items)

    def photo_path(self, entry):
        return os.path.join(self.photos_dir, entry["filename"])

    def thumb_path(self, entry):
        if entry.get("thumb"):
            return os.path.join(self.thumbs_dir, entry["thumb"])
        return None

    def new_enc_filename(self):
        return "%s.enc" % uuid.uuid4().hex

    def new_thumb_filename(self):
        return "%s.thumb.enc" % uuid.uuid4().hex
