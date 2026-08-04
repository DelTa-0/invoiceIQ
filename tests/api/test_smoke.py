"""End-to-end API smoke test (Phase 0 acceptance):

register -> login -> upload (eager pipeline) -> invoice visible with status.
"""

import io

from tests.helpers.pdf import make_invoice_pdf


def test_register_login_upload_smoke(client):
    r = client.post(
        "/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse-battery", "full_name": "Ada", "org_name": "ACME GmbH"},
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["org_id"]

    r = client.post("/v1/auth/login", json={"email": "owner@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "owner@example.com"
    assert r.json()["role"] == "owner"

    real_pdf = make_invoice_pdf()
    r = client.post(
        "/v1/invoices",
        headers=headers,
        files={"files": ("invoice-0001.pdf", io.BytesIO(real_pdf), "application/pdf")},
    )
    assert r.status_code == 202, r.text
    invoice_id = r.json()[0]["id"]

    r = client.get(f"/v1/orgs/{org_id}/invoices", headers=headers)
    assert r.status_code == 200, r.text
    assert any(i["id"] == invoice_id for i in r.json())
    target = next(i for i in r.json() if i["id"] == invoice_id)
    assert target["filename"] == "invoice-0001.pdf"
    assert target["status"] == "completed"

    # duplicate upload must be rejected
    r = client.post(
        "/v1/invoices",
        headers=headers,
        files={"files": ("invoice-0001.pdf", io.BytesIO(real_pdf), "application/pdf")},
    )
    assert r.status_code == 409, r.text


def test_auth_required(client):
    r = client.get("/v1/orgs/00000000-0000-0000-0000-000000000000/invoices")
    assert r.status_code == 401


def test_bad_login(client):
    r = client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert r.status_code == 401


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
