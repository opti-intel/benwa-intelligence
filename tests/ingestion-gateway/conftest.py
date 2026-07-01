"""Zorgt dat 'app' in deze testmap naar de ingestion-gateway-service wijst."""
import os
import sys

_SVC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "services", "ingestion-gateway"))
if _SVC_DIR not in sys.path:
    sys.path.insert(0, _SVC_DIR)

# Verwijder 'app'-modules van een eerder geladen service uit de cache.
for _m in [k for k in list(sys.modules) if k == "app" or k.startswith("app.")]:
    del sys.modules[_m]
