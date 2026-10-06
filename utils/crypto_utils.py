"""
crypto_utils.py
===============
AES-256-GCM encryption for photo files.

Key strategy (in order):
1. Android Keystore: an AES-256 key that never leaves the Keystore. We use it
   to "wrap" a randomly generated data-encryption key (DEK, 32 bytes) stored
   encrypted in user_data_dir. This avoids Keystore's issues with large
   files, and works with AES/GCM/NoPadding.
2. Fallback: derive a key from the user's password via PBKDF2-HMAC-SHA256
   (600,000 iterations) with a random salt stored in a private file.

Encrypted file format (.enc):
    MAGIC (4) | VERSION (1) | NONCE (12) | CIPHERTEXT+TAG (tag = last 16 bytes)

Note: the `cryptography` library automatically appends the tag to the end of
the ciphertext, so "storing the tag with the data" is implicitly satisfied.

Library used: `cryptography` (has an official recipe in python-for-android).
"""
import os
import hashlib
import json

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"SCK1"
VERSION = b"\x01"
NONCE_SIZE = 12
KEY_SIZE = 32
PBKDF2_ITERATIONS = 600_000
KEYSTORE_ALIAS = "securecamera_master_key"
HEADER_SIZE = len(MAGIC) + len(VERSION) + NONCE_SIZE


class CryptoError(Exception):
    """General encryption/decryption error."""


# ---------------------------------------------------------------------------
# Key manager
# ---------------------------------------------------------------------------
class KeyManager:
    """Manages the data-encryption key (DEK), protected by Android Keystore or a password."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._dek = None
        self._dek_file = os.path.join(self.data_dir, "dek.bin")        # DEK wrapped by Keystore
        self._pw_file = os.path.join(self.data_dir, "pwmeta.json")     # salt + password check value
        self._mode_file = os.path.join(self.data_dir, "keymode.txt")

    # ---- State -------------------------------------------------------------
    @property
    def mode(self):
        if os.path.exists(self._mode_file):
            with open(self._mode_file, "r") as f:
                return f.read().strip()
        return None

    def _set_mode(self, mode):
        with open(self._mode_file, "w") as f:
            f.write(mode)

    def is_unlocked(self):
        return self._dek is not None

    def needs_password(self):
        return self.mode == "password"

    def is_initialized(self):
        return self.mode is not None

    def lock(self):
        self._dek = None

    # ---- Automatic Keystore initialization ----------------------------------
    def init_with_keystore(self):
        """Attempts to use Android Keystore. Returns True on success."""
        try:
            from utils.android_utils import is_android
            if not is_android():
                return False
            if self.mode == "keystore" and os.path.exists(self._dek_file):
                self._dek = self._keystore_unwrap(open(self._dek_file, "rb").read())
                return True
            if self.mode is None:
                dek = os.urandom(KEY_SIZE)
                wrapped = self._keystore_wrap(dek)
                with open(self._dek_file, "wb") as f:
                    f.write(wrapped)
                self._set_mode("keystore")
                self._dek = dek
                return True
        except Exception as e:  # noqa
            print("[crypto] Keystore not available:", repr(e))
        return False

    # ---- Fallback mode: password ---------------------------------------------
    def setup_password(self, password):
        if len(password) < 6:
            raise CryptoError("Password too short (6 characters minimum)")
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                  PBKDF2_ITERATIONS, dklen=KEY_SIZE)
        # Check value: ciphertext of a fixed string under the same key
        nonce = os.urandom(NONCE_SIZE)
        check = nonce + AESGCM(key).encrypt(nonce, b"SCK-OK", None)
        with open(self._pw_file, "w") as f:
            json.dump({"salt": salt.hex(), "check": check.hex(),
                       "iter": PBKDF2_ITERATIONS}, f)
        self._set_mode("password")
        self._dek = key

    def unlock_with_password(self, password):
        try:
            with open(self._pw_file, "r") as f:
                meta = json.load(f)
            salt = bytes.fromhex(meta["salt"])
            check = bytes.fromhex(meta["check"])
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                      int(meta.get("iter", PBKDF2_ITERATIONS)),
                                      dklen=KEY_SIZE)
            plain = AESGCM(key).decrypt(check[:NONCE_SIZE], check[NONCE_SIZE:], None)
            if plain != b"SCK-OK":
                return False
            self._dek = key
            return True
        except Exception:
            return False

    # ---- Android Keystore via pyjnius ----------------------------------------
    def _get_keystore_key(self):
        from jnius import autoclass
        KeyStore = autoclass("java.security.KeyStore")
        KeyProperties = autoclass("android.security.keystore.KeyProperties")
        KeyGenParameterSpecBuilder = autoclass(
            "android.security.keystore.KeyGenParameterSpec$Builder")
        KeyGenerator = autoclass("javax.crypto.KeyGenerator")

        ks = KeyStore.getInstance("AndroidKeyStore")
        ks.load(None)
        if not ks.containsAlias(KEYSTORE_ALIAS):
            purposes = KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
            builder = KeyGenParameterSpecBuilder(KEYSTORE_ALIAS, purposes)
            builder.setBlockModes([KeyProperties.BLOCK_MODE_GCM])
            builder.setEncryptionPaddings([KeyProperties.ENCRYPTION_PADDING_NONE])
            builder.setKeySize(256)
            builder.setRandomizedEncryptionRequired(True)
            kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,
                                          "AndroidKeyStore")
            kg.init(builder.build())
            kg.generateKey()
        return ks.getKey(KEYSTORE_ALIAS, None)

    def _keystore_wrap(self, dek):
        from jnius import autoclass
        Cipher = autoclass("javax.crypto.Cipher")
        cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, self._get_keystore_key())
        iv = bytes(bytearray([b & 0xFF for b in cipher.getIV()]))
        ct = cipher.doFinal(dek)
        ct = bytes(bytearray([b & 0xFF for b in ct]))
        return iv + ct

    def _keystore_unwrap(self, blob):
        from jnius import autoclass
        Cipher = autoclass("javax.crypto.Cipher")
        GCMParameterSpec = autoclass("javax.crypto.spec.GCMParameterSpec")
        iv, ct = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
        cipher = Cipher.getInstance("AES/GCM/NoPadding")
        spec = GCMParameterSpec(128, iv)
        cipher.init(Cipher.DECRYPT_MODE, self._get_keystore_key(), spec)
        out = cipher.doFinal(ct)
        return bytes(bytearray([b & 0xFF for b in out]))

    # ---- Encryption interface -------------------------------------------------
    def _require_key(self):
        if self._dek is None:
            raise CryptoError("App is locked: key not available")
        return self._dek

    def encrypt_bytes(self, data):
        key = self._require_key()
        nonce = os.urandom(NONCE_SIZE)
        ct = AESGCM(key).encrypt(nonce, data, MAGIC)  # AAD = MAGIC
        return MAGIC + VERSION + nonce + ct

    def decrypt_bytes(self, blob):
        key = self._require_key()
        if len(blob) < HEADER_SIZE + 16 or blob[:4] != MAGIC:
            raise CryptoError("Invalid encrypted file")
        nonce = blob[5:5 + NONCE_SIZE]
        ct = blob[HEADER_SIZE:]
        try:
            return AESGCM(key).decrypt(nonce, ct, MAGIC)
        except Exception as e:
            raise CryptoError("Decryption failed (corrupt file or wrong key)") from e

    def encrypt_file(self, src_path, dst_path):
        """Encrypts src to dst via a temp file then rename (atomic write)."""
        with open(src_path, "rb") as f:
            data = f.read()
        blob = self.encrypt_bytes(data)
        tmp = dst_path + ".part"
        with open(tmp, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dst_path)

    def decrypt_file(self, src_path, dst_path):
        with open(src_path, "rb") as f:
            blob = f.read()
        data = self.decrypt_bytes(blob)
        with open(dst_path, "wb") as f:
            f.write(data)
        return dst_path


def secure_delete(path):
    """Overwrites the file with zeros then deletes it (best-effort; not guaranteed on flash storage)."""
    try:
        if os.path.exists(path):
            size = os.path.getsize(path)
            with open(path, "r+b") as f:
                f.write(b"\x00" * size)
                f.flush()
                os.fsync(f.fileno())
            os.remove(path)
    except Exception as e:  # noqa
        print("[crypto] secure_delete:", repr(e))
        try:
            os.remove(path)
        except Exception:
            pass
