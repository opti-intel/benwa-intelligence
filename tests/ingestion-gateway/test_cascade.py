"""Tests voor de cascade-logica (automatisch doorschuiven van afhankelijke taken)."""

import sys
import os
from datetime import date

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "ingestion-gateway"))
sys.path.insert(0, SERVICES_DIR)

from app.cascade import (
    volgende_werkdag,
    plus_werkdagen,
    werkdagen_duur,
    bereken_cascade,
    maakt_cyclus,
)
from app.claude_parser import VOORSTEL_SCHEMA

# Referentiedata (2026): ma 6 juli t/m vr 10 juli, za 11, zo 12, ma 13 juli.
MA = date(2026, 7, 6)
DI = date(2026, 7, 7)
WO = date(2026, 7, 8)
DO = date(2026, 7, 9)
VR = date(2026, 7, 10)
ZA = date(2026, 7, 11)
ZO = date(2026, 7, 12)
MA2 = date(2026, 7, 13)
DI2 = date(2026, 7, 14)
WO2 = date(2026, 7, 15)
VR2 = date(2026, 7, 17)


class TestWerkdagRekenen:
    def test_weekend_schuift_naar_maandag(self):
        assert volgende_werkdag(ZA) == MA2
        assert volgende_werkdag(ZO) == MA2
        assert volgende_werkdag(WO) == WO

    def test_plus_werkdagen_over_weekend(self):
        assert plus_werkdagen(VR, 1) == MA2
        assert plus_werkdagen(MA, 4) == VR
        assert plus_werkdagen(DO, 2) == MA2

    def test_plus_nul_werkdagen(self):
        assert plus_werkdagen(WO, 0) == WO
        assert plus_werkdagen(ZA, 0) == MA2  # weekend normaliseert vooruit

    def test_werkdagen_duur(self):
        assert werkdagen_duur(MA, VR) == 5
        assert werkdagen_duur(VR, MA2) == 2  # weekend telt niet mee
        assert werkdagen_duur(WO, WO) == 1


def _taak(naam, start, eind, wie=""):
    return {"naam": naam, "startdatum": start, "einddatum": eind, "toegewezen_aan": wie}


class TestBerekenCascade:
    def test_volger_schuift_op_na_uitloop(self):
        # Tegelen liep uit t/m vrijdag; voegen stond op do/vr gepland.
        taken = {
            "teg": _taak("Tegelen", MA, VR, "Ahmed"),
            "voeg": _taak("Voegen", DO, VR, "Bram"),
        }
        verschoven = bereken_cascade(taken, [("teg", "voeg")], "teg")
        assert len(verschoven) == 1
        v = verschoven[0]
        assert v["taak_id"] == "voeg"
        assert v["nieuwe_start"] == MA2  # werkdag na vrijdag = maandag
        assert v["nieuwe_eind"] == DI2   # duur van 2 werkdagen blijft behouden

    def test_ketting_schuift_door(self):
        # Tegelen -> voegen -> sanitair: alles schuift door.
        taken = {
            "teg": _taak("Tegelen", MA, VR),
            "voeg": _taak("Voegen", DO, VR),
            "san": _taak("Sanitair", MA2, WO2),
        }
        relaties = [("teg", "voeg"), ("voeg", "san")]
        verschoven = bereken_cascade(taken, relaties, "teg")
        assert [v["taak_id"] for v in verschoven] == ["voeg", "san"]
        # Voegen: ma2 t/m di2; sanitair moet dus op wo2 starten, duur 3 werkdagen.
        assert verschoven[1]["nieuwe_start"] == WO2
        assert verschoven[1]["nieuwe_eind"] == VR2

    def test_genoeg_ruimte_geen_verschuiving(self):
        taken = {
            "teg": _taak("Tegelen", MA, WO),
            "voeg": _taak("Voegen", VR, VR),
        }
        assert bereken_cascade(taken, [("teg", "voeg")], "teg") == []

    def test_meerdere_voorgangers_laatste_telt(self):
        # Sanitair hangt af van tegelen ÉN elektra; de laatste einddatum bepaalt.
        taken = {
            "teg": _taak("Tegelen", MA, DI),
            "elek": _taak("Elektra", MA, VR),
            "san": _taak("Sanitair", WO, DO),
        }
        relaties = [("teg", "san"), ("elek", "san")]
        verschoven = bereken_cascade(taken, relaties, "teg")
        assert len(verschoven) == 1
        assert verschoven[0]["nieuwe_start"] == MA2  # na elektra (vr), niet na tegelen

    def test_cyclus_loopt_niet_vast(self):
        taken = {
            "a": _taak("A", MA, VR),
            "b": _taak("B", DO, VR),
        }
        relaties = [("a", "b"), ("b", "a")]
        verschoven = bereken_cascade(taken, relaties, "a")
        assert isinstance(verschoven, list)  # belangrijkste: geen oneindige lus

    def test_taak_zonder_datums_wordt_overgeslagen(self):
        taken = {
            "teg": _taak("Tegelen", MA, VR),
            "voeg": _taak("Voegen", None, None),
        }
        assert bereken_cascade(taken, [("teg", "voeg")], "teg") == []

    def test_onbekende_relaties_geen_effect(self):
        taken = {"teg": _taak("Tegelen", MA, VR)}
        assert bereken_cascade(taken, [], "teg") == []


class TestCyclusDetectie:
    def test_directe_cyclus(self):
        # b volgt al op a; a laten volgen op b zou een kringetje maken.
        assert maakt_cyclus([("a", "b")], "b", "a") is True

    def test_indirecte_cyclus(self):
        # a → b → c bestaat; c als voorganger van a maakt een kringetje.
        assert maakt_cyclus([("a", "b"), ("b", "c")], "c", "a") is True

    def test_geen_cyclus(self):
        assert maakt_cyclus([("a", "b")], "a", "c") is False
        assert maakt_cyclus([], "a", "b") is False


class TestVoorstelSchema:
    def test_komt_na_in_schema(self):
        """De AI-parser moet het veld komt_na kennen én verplicht invullen."""
        assert "komt_na" in VOORSTEL_SCHEMA["properties"]
        assert "komt_na" in VOORSTEL_SCHEMA["required"]
        assert VOORSTEL_SCHEMA["properties"]["komt_na"]["type"] == "array"
