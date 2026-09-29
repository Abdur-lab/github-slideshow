"""Where uploaded files live: local disk (the default) or an S3-compatible
bucket (AWS S3, Cloudflare R2, MinIO, ...), chosen with STORAGE_BACKEND.

Every upload in the app goes through save_upload / save_uploads and is
served by serve_upload, so routes and stored paths are the same for both
backends: a model keeps a relative path such as "leases/1a2b.pdf", which is
a file under UPLOAD_FOLDER on disk or an object key (after S3_PREFIX) in the
bucket. A server's own disk does not survive a redeploy on most hosting
platforms; a bucket does.

Files are private in both cases. serve_upload streams them through the app,
so the caller's authorization check always applies; nothing is exposed by a
public or pre-signed link."""
import mimetypes
import os
import secrets

from flask import Response, abort, current_app, send_from_directory
from werkzeug.utils import secure_filename


def _new_relpath(file_storage, subdir: str) -> str:
    ext = os.path.splitext(file_storage.filename)[1].lower()
    return f"{subdir}/{secure_filename(f'{secrets.token_hex(8)}{ext}')}"


def _using_s3() -> bool:
    return current_app.config.get("STORAGE_BACKEND", "local") == "s3"


def _s3_client():
    """A boto3 S3 client. Credentials come from the usual AWS sources
    (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, an instance role, ...)."""
    import boto3

    return boto3.client(
        "s3",
        region_name=current_app.config.get("S3_REGION") or None,
        endpoint_url=current_app.config.get("S3_ENDPOINT_URL") or None,
    )


def _s3_key(relpath: str) -> str:
    prefix = (current_app.config.get("S3_PREFIX") or "").strip("/")
    return f"{prefix}/{relpath}" if prefix else relpath


def save_upload(file_storage, subdir: str) -> str:
    """Saves an already-validated upload and returns its relative path (stored on the model)."""
    relpath = _new_relpath(file_storage, subdir)
    file_storage.stream.seek(0)
    if _using_s3():
        content_type = file_storage.mimetype or mimetypes.guess_type(relpath)[0] or "application/octet-stream"
        _s3_client().upload_fileobj(
            file_storage.stream,
            current_app.config["S3_BUCKET"],
            _s3_key(relpath),
            ExtraArgs={"ContentType": content_type},
        )
        return relpath
    abs_path = os.path.join(current_app.config["UPLOAD_FOLDER"], relpath)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    file_storage.save(abs_path)
    return relpath


def save_uploads(file_storages, subdir: str, max_count: int) -> list:
    """Saves up to max_count already-validated uploads, silently ignoring
    any beyond the cap (the form/route is responsible for validating each
    file before calling this)."""
    return [save_upload(fs, subdir) for fs in file_storages[:max_count]]


def serve_upload(relpath: str):
    """Streams a previously-saved upload. Callers must perform their own
    authorization check (e.g. assert_owner(), assert_tenant_self(), or a
    maintenance _can_view() check) before calling this — it does not check
    who is asking, only that the file exists."""
    if not _using_s3():
        return send_from_directory(current_app.config["UPLOAD_FOLDER"], relpath)

    client = _s3_client()
    try:
        obj = client.get_object(Bucket=current_app.config["S3_BUCKET"], Key=_s3_key(relpath))
    except client.exceptions.NoSuchKey:
        abort(404)
    body = obj["Body"]
    return Response(
        body.iter_chunks(64 * 1024),
        mimetype=obj.get("ContentType") or mimetypes.guess_type(relpath)[0] or "application/octet-stream",
        headers={"Content-Length": str(obj["ContentLength"])},
        direct_passthrough=True,
    )
