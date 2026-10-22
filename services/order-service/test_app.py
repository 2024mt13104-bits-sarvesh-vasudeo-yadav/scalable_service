import os, tempfile
from fastapi.testclient import TestClient
import app as service

def test_health():
    client=TestClient(service.app)
    assert client.get("/health").status_code == 200
