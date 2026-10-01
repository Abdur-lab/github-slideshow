"""Uploads go to local disk by default, or to an S3-compatible bucket with STORAGE_BACKEND=s3."""
import io
import os
from datetime import date, timedelta

import pytest

from backend import create_app
from backend.config import TestConfig
from backend.models import Lease
from backend.services import storage
from tests.conftest import login

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class FakeS3:
    """Just enough of a boto3 S3 client for the calls storage.py makes."""

    class exceptions:
        class NoSuchKey(Exception):
            pass

    class _Body:
        def __init__(self, data):
            self.data = data

        def iter_chunks(self, size):
            for i in range(0, len(self.data), size):
                yield self.data[i:i + size]

    def __init__(self):
        self.objects = {}

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        self.objects[(bucket, key)] = (fileobj.read(), (ExtraArgs or {}).get("ContentType"))

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise self.exceptions.NoSuchKey(Key)
        data, content_type = self.objects[(Bucket, Key)]
        return {"Body": self._Body(data), "ContentType": content_type, "ContentLength": len(data)}


@pytest.fixture()
def s3(app, monkeypatch, tmp_path):
    fake = FakeS3()
    monkeypatch.setattr(storage, "_s3_client", lambda: fake)
    app.config.update(STORAGE_BACKEND="s3", S3_BUCKET="rentalpro-test", S3_PREFIX="uploads", UPLOAD_FOLDER=str(tmp_path))
    return fake


def _upload_lease(client, tenant, unit):
    return client.post(
        f"/tenants/{tenant.id}/upload-lease",
        data={
            "unit_id": unit.id, "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
            "monthly_rent": "1000", "lease_document": (io.BytesIO(PDF), "lease.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_lease_documents_are_stored_in_the_bucket_and_served_back(client, s3, tmp_path, manager, unit, tenant):
    login(client, manager.email)
    _upload_lease(client, tenant, unit)
    lease = Lease.query.filter_by(tenant_id=tenant.id).one()

    assert ("rentalpro-test", f"uploads/{lease.document_path}") in s3.objects
    assert not any(files for _, _, files in os.walk(tmp_path))  # nothing written to local disk

    resp = client.get(f"/tenants/{tenant.id}/lease-document/{lease.id}")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data == PDF


def test_photos_round_trip_through_the_bucket(client, s3, owner, property_):
    login(client, owner.email)
    client.post(
        f"/properties/{property_.id}/edit",
        data={"name": property_.name, "address": property_.address, "city": property_.city,
              "country": property_.country, "late_fee_type": "NONE", "photos": (io.BytesIO(PNG), "front.png")},
        content_type="multipart/form-data",
    )
    path = property_.photo_paths[0]
    assert s3.objects[("rentalpro-test", f"uploads/{path}")] == (PNG, "image/png")
    resp = client.get(f"/properties/{property_.id}/photos/{path.split('/')[-1]}")
    assert resp.status_code == 200 and resp.data == PNG


def test_a_missing_object_is_a_404(app, s3):
    with app.test_request_context():
        with pytest.raises(Exception) as err:
            storage.serve_upload("leases/gone.pdf")
    assert getattr(err.value, "code", None) == 404


def test_local_disk_is_still_the_default(client, tmp_path, app, manager, unit, tenant):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    login(client, manager.email)
    _upload_lease(client, tenant, unit)
    lease = Lease.query.filter_by(tenant_id=tenant.id).one()
    assert (tmp_path / lease.document_path).read_bytes() == PDF


def test_s3_mode_requires_a_bucket():
    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        create_app(type("NoBucket", (TestConfig,), {"STORAGE_BACKEND": "s3", "S3_BUCKET": None}))
