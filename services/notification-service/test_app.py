
import os
import tempfile

import app as service
from fastapi.testclient import TestClient


def test_notification_deduplicates_event():
    old_db = service.DB
    temp_db_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db_path = f.name

        service.DB = temp_db_path
        c = TestClient(service.app)

        body = {
            "event_key": "e1",
            "order_id": "o1",
            "message": "confirmed"
        }

        first_response = c.post("/api/v1/notifications", json=body)
        assert first_response.status_code == 200
        first = first_response.json()

        second_response = c.post("/api/v1/notifications", json=body)
        assert second_response.status_code == 200
        second = second_response.json()

        assert first["notification_id"] == second["notification_id"]

    finally:
        service.DB = old_db

        if temp_db_path and os.path.exists(temp_db_path):
            os.remove(temp_db_path)
