"""Tests voor web-push meldingen."""

import sys
import os
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "ingestion-gateway"))
sys.path.insert(0, SERVICES_DIR)

from app.push import maak_push_payload, _vapid_config


class TestPushPayload:
    def test_payload_bevat_tekst_en_taak(self):
        data = json.loads(maak_push_payload("Tegels verplaatst", "abc-123"))
        assert data["tekst"] == "Tegels verplaatst"
        assert data["taak_id"] == "abc-123"
        assert data["url"] == "/planning"
        assert data["titel"]

    def test_payload_zonder_taak(self):
        data = json.loads(maak_push_payload("Algemene melding"))
        assert data["taak_id"] is None


class TestVapidConfig:
    def test_zonder_sleutel_geen_push(self, monkeypatch):
        monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
        priv, claims = _vapid_config()
        assert priv is None and claims is None

    def test_met_sleutel(self, monkeypatch):
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "geheim")
        monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@test.nl")
        priv, claims = _vapid_config()
        assert priv == "geheim"
        assert claims == {"sub": "mailto:test@test.nl"}
