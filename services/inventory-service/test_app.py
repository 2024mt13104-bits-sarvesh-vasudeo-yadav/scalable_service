
import os
import tempfile

import app as service
from fastapi.testclient import TestClient


def test_health():
    assert TestClient(service.app).get("/health").status_code == 200


def test_atomic_stock_and_idempotent_reservation():
    old_db = service.DB
    temp_db_path = None

    try:
        # Close the temporary file immediately so SQLite can open it on Windows.
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db_path = f.name

        service.DB = temp_db_path
        c = TestClient(service.app)

        assert c.put(
            "/api/v1/inventory/TEST",
            json={"quantity": 2}
        ).status_code == 200

        body = {
            "reservation_id": "r1",
            "sku": "TEST",
            "quantity": 2
        }

        assert c.post(
            "/api/v1/inventory/reservations",
            json=body
        ).status_code == 200

        replay = c.post("/api/v1/inventory/reservations", json=body)
        assert replay.status_code == 200
        assert replay.json()["replayed"] is True

        assert c.get("/api/v1/inventory/TEST").json()["quantity"] == 0

        assert c.post(
            "/api/v1/inventory/reservations",
            json={
                "reservation_id": "r2",
                "sku": "TEST",
                "quantity": 1
            }
        ).status_code == 409

    finally:
        service.DB = old_db

        if temp_db_path and os.path.exists(temp_db_path):
            os.remove(temp_db_path)
