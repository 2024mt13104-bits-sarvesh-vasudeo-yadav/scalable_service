
import os
import tempfile

import app as service
from fastapi.testclient import TestClient


def test_payment_idempotency():
    old_db = service.DB
    temp_db_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db_path = f.name

        service.DB = temp_db_path
        c = TestClient(service.app)

        body = {
            "order_id": "o1",
            "amount": 5,
            "simulate_failure": False,
            "idempotency_key": "p1"
        }

        first_response = c.post("/api/v1/payments", json=body)
        assert first_response.status_code == 200
        first = first_response.json()

        second_response = c.post("/api/v1/payments", json=body)
        assert second_response.status_code == 200
        second = second_response.json()

        assert first["payment_id"] == second["payment_id"]
        assert second["replayed"] is True

    finally:
        service.DB = old_db

        if temp_db_path and os.path.exists(temp_db_path):
            os.remove(temp_db_path)
