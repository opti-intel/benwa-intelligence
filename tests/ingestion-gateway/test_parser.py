"""Tests for ingestion-gateway parsers."""

import sys
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "ingestion-gateway"))
sys.path.insert(0, SERVICES_DIR)

from app.parser import parse_bim, parse_sensor_data, parse_document, normalize_payload


# ---------------------------------------------------------------------------
# parse_bim
# ---------------------------------------------------------------------------

class TestParseBim:
    """Tests for the BIM payload parser."""

    def test_extracts_elements_and_metadata(self):
        payload = {
            "elements": [{"type": "slab", "id": "s1"}],
            "metadata": {"format": "IFC4"},
        }
        result = parse_bim(payload)

        assert result["type"] == "bim"
        assert result["normalized"] is True
        assert result["elements"] == [{"type": "slab", "id": "s1"}]
        assert result["metadata"] == {"format": "IFC4"}

    def test_missing_elements_defaults_to_empty(self):
        result = parse_bim({})

        assert result["elements"] == []
        assert result["metadata"] == {}
        assert result["normalized"] is True

    def test_preserves_all_elements(self):
        elements = [{"id": f"e{i}"} for i in range(10)]
        result = parse_bim({"elements": elements})

        assert len(result["elements"]) == 10


# ---------------------------------------------------------------------------
# parse_sensor_data
# ---------------------------------------------------------------------------

class TestParseSensorData:
    """Tests for the sensor data parser."""

    def test_extracts_readings_and_device_id(self):
        payload = {
            "readings": [{"temp": 25.0}, {"temp": 26.1}],
            "device_id": "thermo-7",
        }
        result = parse_sensor_data(payload)

        assert result["type"] == "sensor"
        assert result["normalized"] is True
        assert len(result["readings"]) == 2
        assert result["device_id"] == "thermo-7"

    def test_missing_readings_defaults_to_empty(self):
        result = parse_sensor_data({"device_id": "d1"})

        assert result["readings"] == []
        assert result["device_id"] == "d1"

    def test_missing_device_id_returns_none(self):
        result = parse_sensor_data({"readings": [1, 2, 3]})

        assert result["device_id"] is None


# ---------------------------------------------------------------------------
# parse_document
# ---------------------------------------------------------------------------

class TestParseDocument:
    """Tests for the document parser."""

    def test_extracts_content_and_doc_type(self):
        payload = {"content": "Section 1: Scope of work...", "doc_type": "spec"}
        result = parse_document(payload)

        assert result["type"] == "document"
        assert result["normalized"] is True
        assert result["content"] == "Section 1: Scope of work..."
        assert result["doc_type"] == "spec"

    def test_missing_content_defaults_to_empty_string(self):
        result = parse_document({})

        assert result["content"] == ""
        assert result["doc_type"] == "unknown"

    def test_preserves_full_content(self):
        long_text = "word " * 1000
        result = parse_document({"content": long_text})

        assert result["content"] == long_text


# ---------------------------------------------------------------------------
# normalize_payload
# ---------------------------------------------------------------------------

class TestNormalizePayload:
    """Tests for the normalize_payload routing function."""

    def test_routes_bim(self):
        result = normalize_payload("bim", {"elements": [1]})

        assert result["type"] == "bim"
        assert result["normalized"] is True

    def test_routes_sensor(self):
        result = normalize_payload("sensor", {"readings": [1]})

        assert result["type"] == "sensor"
        assert result["normalized"] is True

    def test_routes_document(self):
        result = normalize_payload("document", {"content": "hello"})

        assert result["type"] == "document"
        assert result["normalized"] is True

    def test_unknown_source_type_returns_raw(self):
        payload = {"custom_data": 42}
        result = normalize_payload("lidar", payload)

        assert result["type"] == "lidar"
        assert result["normalized"] is False
        assert result["raw"] == payload

    def test_another_unknown_type(self):
        result = normalize_payload("drone_imagery", {"images": []})

        assert result["normalized"] is False
        assert result["type"] == "drone_imagery"
