import pytest

pytestmark = pytest.mark.django_db


def test_healthz_ok(api_client):
    resp = api_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.data["status"] == "ok"
