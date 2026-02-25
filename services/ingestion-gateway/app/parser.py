"""Stub parsers for normalizing raw payloads by source type."""


def parse_bim(payload: dict) -> dict:
    """Parse and normalize a BIM (Building Information Model) payload."""
    return {
        "type": "bim",
        "elements": payload.get("elements", []),
        "metadata": payload.get("metadata", {}),
        "normalized": True,
    }


def parse_sensor_data(payload: dict) -> dict:
    """Parse and normalize IoT / sensor data payload."""
    return {
        "type": "sensor",
        "readings": payload.get("readings", []),
        "device_id": payload.get("device_id"),
        "normalized": True,
    }


def parse_document(payload: dict) -> dict:
    """Parse and normalize a document payload (PDF text, specs, etc.)."""
    return {
        "type": "document",
        "content": payload.get("content", ""),
        "doc_type": payload.get("doc_type", "unknown"),
        "normalized": True,
    }


_PARSERS = {
    "bim": parse_bim,
    "sensor": parse_sensor_data,
    "document": parse_document,
}


def normalize_payload(source_type: str, payload: dict) -> dict:
    """Route the payload to the correct parser based on source_type."""
    parser = _PARSERS.get(source_type)
    if parser is None:
        return {"type": source_type, "raw": payload, "normalized": False}
    return parser(payload)
