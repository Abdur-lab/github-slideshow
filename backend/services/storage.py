"""Local-disk file storage helper. In production this is the natural place
to swap in an S3-backed implementation without touching any route (Chapter
1 / Appendix A note that S3 support is designed for but not implemented)."""
import os
import secrets

from flask import current_app, send_from_directory
from werkzeug.utils import secure_filename


def save_upload(file_storage, subdir: str) -> str:
    """Saves an already-validated upload under UPLOAD_FOLDER/<subdir>/ and
    returns the path relative to UPLOAD_FOLDER (stored on the model)."""
    ext = os.path.splitext(file_storage.filename)[1].lower()
    target_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], subdir)
    os.makedirs(target_dir, exist_ok=True)
    filename = secure_filename(f"{secrets.token_hex(8)}{ext}")
    abs_path = os.path.join(target_dir, filename)
    file_storage.stream.seek(0)
    file_storage.save(abs_path)
    return os.path.join(subdir, filename)


def save_uploads(file_storages, subdir: str, max_count: int) -> list:
    """Saves up to max_count already-validated uploads, silently ignoring
    any beyond the cap (the form/route is responsible for validating each
    file before calling this)."""
    paths = []
    for fs in file_storages[:max_count]:
        paths.append(save_upload(fs, subdir))
    return paths


def serve_upload(relpath: str):
    """Streams a previously-saved upload. Callers must perform their own
    authorization check (e.g. assert_owner(), assert_tenant_self(), or a
    maintenance _can_view() check) before calling this — it does not check
    who is asking, only that the path exists under UPLOAD_FOLDER."""
    directory = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(directory, relpath)
