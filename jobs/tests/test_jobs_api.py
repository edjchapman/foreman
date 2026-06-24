import pytest

from jobs.models import Job
from jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


def test_submit_creates_pending_job(api_client):
    resp = api_client.post(
        "/api/v1/jobs/",
        {"job_type": "property_csv_import", "payload": {"source": "s3://b/x.csv"}},
        format="json",
    )
    assert resp.status_code == 202
    assert resp.data["status"] == Job.Status.PENDING
    assert "Location" in resp.headers
    assert Job.objects.count() == 1


def test_submit_rejects_empty_payload(api_client):
    resp = api_client.post(
        "/api/v1/jobs/",
        {"job_type": "property_csv_import", "payload": {}},
        format="json",
    )
    assert resp.status_code == 400
    assert Job.objects.count() == 0


def test_idempotency_key_dedupes(api_client):
    body = {"job_type": "property_csv_import", "payload": {"source": "x.csv"}}
    r1 = api_client.post("/api/v1/jobs/", body, format="json", HTTP_IDEMPOTENCY_KEY="abc-123")
    r2 = api_client.post("/api/v1/jobs/", body, format="json", HTTP_IDEMPOTENCY_KEY="abc-123")
    assert r1.status_code == 202
    assert r2.status_code == 200  # second call returns the existing job, no duplicate
    assert r1.data["id"] == r2.data["id"]
    assert Job.objects.count() == 1


def test_retrieve_job(api_client):
    job = JobFactory()
    resp = api_client.get(f"/api/v1/jobs/{job.id}/")
    assert resp.status_code == 200
    assert resp.data["id"] == str(job.id)
    assert resp.data["status"] == Job.Status.PENDING


def test_list_jobs_paginated(api_client):
    JobFactory.create_batch(3)
    resp = api_client.get("/api/v1/jobs/")
    assert resp.status_code == 200
    assert resp.data["count"] == 3
