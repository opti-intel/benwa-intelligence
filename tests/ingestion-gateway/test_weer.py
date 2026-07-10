"""Tests voor de weerbewaking (buitenwerk herkennen + verschuiven bij slecht weer)."""

import sys
import os
from datetime import date

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "ingestion-gateway"))
sys.path.insert(0, SERVICES_DIR)

from app.weer import is_buitenwerk, onwerkbare_dagen, bereken_verschuiving

# Referentie: wo 8 juli 2026 t/m ma 13 juli 2026 (za 11 / zo 12 = weekend)
WO = date(2026, 7, 8)
DO = date(2026, 7, 9)
VR = date(2026, 7, 10)
MA2 = date(2026, 7, 13)
DI2 = date(2026, 7, 14)


def _dag(datum, temp=15.0, regen=0.0, wind=20.0):
    return {"datum": datum, "min_temp": temp, "neerslag_mm": regen, "windstoten_kmu": wind}


class TestBuitenwerk:
    def test_herkent_buitenwerk(self):
        assert is_buitenwerk("Dakpannen leggen blok B") is True
        assert is_buitenwerk("Metselen gevel") is True
        assert is_buitenwerk("Fundering storten") is True

    def test_binnenwerk_niet(self):
        assert is_buitenwerk("Tegelen badkamer") is False
        assert is_buitenwerk("Elektra aansluiten meterkast") is False


class TestOnwerkbareDagen:
    def test_vorst_en_storm(self):
        slecht = onwerkbare_dagen([
            _dag(WO, temp=-2.0),
            _dag(DO),
            _dag(VR, wind=75.0),
        ])
        assert WO in slecht and "vorst" in slecht[WO]
        assert VR in slecht and "storm" in slecht[VR]
        assert DO not in slecht

    def test_zware_regen(self):
        slecht = onwerkbare_dagen([_dag(WO, regen=12.0)])
        assert "regen" in slecht[WO]

    def test_goed_weer(self):
        assert onwerkbare_dagen([_dag(WO), _dag(DO)]) == {}


class TestVerschuiving:
    def test_taak_in_slecht_weer_schuift(self):
        # Taak do t/m vr, storm op vrijdag -> nieuwe start maandag, duur 2 werkdagen.
        start, eind, reden = bereken_verschuiving(DO, VR, {VR: "storm (75 km/u)"})
        assert start == MA2
        assert eind == DI2
        assert "storm" in reden

    def test_taak_buiten_slecht_weer_blijft(self):
        start, eind, reden = bereken_verschuiving(MA2, DI2, {WO: "vorst (-2 °C)"})
        assert start is None and eind is None and reden is None

    def test_nieuwe_start_na_laatste_slechte_dag(self):
        # Slecht weer wo én do; taak wo t/m do -> start op vrijdag.
        start, _, _ = bereken_verschuiving(WO, DO, {WO: "vorst", DO: "vorst"})
        assert start == VR
