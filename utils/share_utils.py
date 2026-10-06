"""
share_utils.py
==============
- Share a photo via ACTION_SEND + FileProvider.
- Save a decrypted copy via Storage Access Framework (ACTION_CREATE_DOCUMENT).
"""
import os
import uuid

from utils import android_utils as au


def share_image(key_manager, enc_path, on_done=None):
    """
    Decrypts the photo into <cache>/shared then opens the share chooser.
    Returns the temp file path (deleted when returning to the app or on close).
    """
    from jnius import autoclass, cast

    tmp_path = os.path.join(au.shared_tmp_dir(), "share_%s.jpg" % uuid.uuid4().hex[:10])
    key_manager.decrypt_file(enc_path, tmp_path)

    Intent = autoclass("android.content.Intent")
    uri = au.file_to_content_uri(tmp_path)

    intent = Intent(Intent.ACTION_SEND)
    intent.setType("image/jpeg")
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

    chooser = Intent.createChooser(intent, cast("java.lang.CharSequence",
                                                autoclass("java.lang.String")("Share photo via")))
    chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    au.get_activity().startActivity(chooser)
    return tmp_path


def save_copy_via_saf(key_manager, enc_path, suggested_name, on_result=None):
    """
    Opens the "create document" picker (SAF); once the user chooses a
    location, writes the decrypted copy there. No storage permission needed.
    on_result(success: bool, message: str)
    """
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("image/jpeg")
    intent.putExtra(Intent.EXTRA_TITLE, suggested_name)

    def _handler(request_code, result_code, data):
        au.unregister_activity_result(au.REQUEST_SAVE)
        if result_code != au.RESULT_OK or data is None:
            if on_result:
                on_result(False, "Save cancelled")
            return
        try:
            uri = data.getData()
            plain = key_manager.decrypt_bytes(open(enc_path, "rb").read())
            au.write_bytes_to_uri(uri, plain)
            del plain
            if on_result:
                on_result(True, "Photo saved to phone")
        except Exception as e:  # noqa
            if on_result:
                on_result(False, "Save failed: %s" % e)

    au.register_activity_result(au.REQUEST_SAVE, _handler)
    au.get_activity().startActivityForResult(intent, au.REQUEST_SAVE)
