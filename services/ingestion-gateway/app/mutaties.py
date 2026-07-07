"""Endpoints voor voorgestelde planningsmutaties en meldingen.

Een chatbericht wordt door Claude geïnterpreteerd en als 'pending' voorstel
opgeslagen (zie main.py). Hier kan ALLEEN DE ZENDER van het bericht zijn eigen
voorstel bevestigen of afwijzen. Pas bij bevestiging wordt de planning (tabel
'tasks') aangepast en krijgen alle direct of indirect betrokken gebruikers een
melding.

'Betrokken' = direct (de toegewezen persoon + de zender) plus indirect
(iedereen met een taak waarvan de periode overlapt met de gewijzigde taak).
"""

import json
import os
from datetime import date
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from fastapi import Body

from .auth import get_huidige_gebruiker, vereist_admin
from .cascade import verwerk_voorstel_relaties

router = APIRouter(tags=["mutaties"])


def _raw_db_url() -> str:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://benwa:changeme@postgres:5432/benwa_intelligence",
    )
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _parse_date(val):
    """'YYYY-MM-DD' string -> date object, of None."""
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Toepassen van een voorstel op de planning
# ---------------------------------------------------------------------------

async def pas_mutatie_toe(conn: asyncpg.Connection, voorstel: dict, afzender_naam: str) -> str:
    """Pas een goedgekeurd voorstel toe op de tabel 'tasks'.

    Geeft het id van de aangemaakte/gewijzigde taak terug. Werpt ValueError als
    het voorstel niet toepasbaar is (bv. ontbrekende naam of doel-taak).
    """
    actie = voorstel.get("actie")

    if actie == "taak_aanmaken":
        naam = voorstel.get("naam")
        if not naam:
            raise ValueError("Voorstel mist een taaknaam")
        task_id = uuid4()
        await conn.execute(
            """INSERT INTO tasks (id, naam, beschrijving, status, startdatum, einddatum, toegewezen_aan)
               VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING""",
            task_id,
            naam,
            voorstel.get("beschrijving") or "",
            voorstel.get("status") or "gepland",
            _parse_date(voorstel.get("startdatum")),
            _parse_date(voorstel.get("einddatum")),
            voorstel.get("toegewezen_aan") or afzender_naam,
        )
        return str(task_id)

    if actie == "taak_wijzigen":
        doel = voorstel.get("doel_taak_id")
        if not doel:
            raise ValueError("Wijzigingsvoorstel mist doel_taak_id")
        velden: dict = {}
        for k in ("naam", "beschrijving", "status", "toegewezen_aan"):
            if voorstel.get(k) is not None:
                velden[k] = voorstel[k]
        for k in ("startdatum", "einddatum"):
            if voorstel.get(k) is not None:
                velden[k] = _parse_date(voorstel[k])
        if not velden:
            raise ValueError("Wijzigingsvoorstel bevat geen aan te passen velden")
        sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(velden))
        resultaat = await conn.execute(
            f"UPDATE tasks SET {sets}, updated_at = NOW() WHERE id = $1",
            doel, *velden.values(),
        )
        if int(resultaat.split()[-1]) == 0:
            raise ValueError("Doel-taak niet gevonden")
        return str(doel)

    raise ValueError(f"Onbekende actie: {actie}")


# ---------------------------------------------------------------------------
# Bepalen wie betrokken is + meldingen aanmaken
# ---------------------------------------------------------------------------

async def _betrokken_gebruiker_ids(conn: asyncpg.Connection, task_id: str, afzender_id) -> tuple[set, dict]:
    """Geeft (set van gebruiker-ids om te melden, de taak-rij) terug.

    Direct: de aan de taak toegewezen persoon. Indirect: iedereen met een taak
    waarvan de periode overlapt met die van de gewijzigde taak. De zender
    (= degene die net bevestigde) wordt NIET zelf gemeld.
    """
    taak = await conn.fetchrow(
        "SELECT naam, startdatum, einddatum, toegewezen_aan FROM tasks WHERE id = $1",
        task_id,
    )
    namen: set = set()
    if taak and taak["toegewezen_aan"]:
        namen.add(taak["toegewezen_aan"])

    # Indirect: datumoverlap met andere taken (alleen als beide datums bekend zijn).
    if taak and taak["startdatum"] and taak["einddatum"]:
        overlap = await conn.fetch(
            """SELECT DISTINCT toegewezen_aan FROM tasks
               WHERE id != $1
                 AND toegewezen_aan IS NOT NULL AND toegewezen_aan != ''
                 AND startdatum IS NOT NULL AND einddatum IS NOT NULL
                 AND startdatum <= $3 AND einddatum >= $2""",
            task_id, taak["startdatum"], taak["einddatum"],
        )
        for r in overlap:
            namen.add(r["toegewezen_aan"])

    ids: set = set()
    if namen:
        rows = await conn.fetch(
            "SELECT id, naam FROM gebruikers WHERE naam = ANY($1::text[]) AND actief = TRUE",
            list(namen),
        )
        ids = {str(r["id"]) for r in rows}

    # De zender bevestigde zelf, dus die hoeft geen melding.
    if afzender_id is not None:
        ids.discard(str(afzender_id))
    return ids, taak


def _melding_tekst(actie: str, taak: dict, afzender_naam: str) -> str:
    naam = taak["naam"] if taak else "taak"
    periode = ""
    if taak and taak["startdatum"] and taak["einddatum"]:
        periode = f" ({taak['startdatum']} t/m {taak['einddatum']})"
    if actie == "taak_aanmaken":
        return f"🆕 Nieuwe taak gepland: {naam}{periode} — toegevoegd door {afzender_naam}"
    return f"🔄 Planning gewijzigd: {naam}{periode} — door {afzender_naam}"


async def _maak_meldingen(conn, gebruiker_ids: set, tekst: str, task_id: str, voorstel_id: str):
    from .push import stuur_push
    for uid in gebruiker_ids:
        await conn.execute(
            """INSERT INTO meldingen (gebruiker_id, tekst, taak_id, voorstel_id)
               VALUES ($1, $2, $3, $4)""",
            uid, tekst, task_id, voorstel_id,
        )
        await stuur_push(conn, uid, tekst, task_id)


# ---------------------------------------------------------------------------
# Voorstellen-endpoints
# ---------------------------------------------------------------------------

@router.get("/mutaties")
async def lijst_mutaties(gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Geeft de openstaande (pending) voorstellen van de ingelogde zender terug."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        rows = await conn.fetch(
            """SELECT id, bron, afzender, ruwe_tekst, voorstel, aangemaakt_op
               FROM voorgestelde_mutaties
               WHERE afzender_id = $1 AND status = 'pending'
               ORDER BY aangemaakt_op DESC""",
            gebruiker["id"],
        )
    finally:
        await conn.close()
    return [
        {
            "id": str(r["id"]),
            "bron": r["bron"],
            "afzender": r["afzender"],
            "ruwe_tekst": r["ruwe_tekst"],
            "voorstel": json.loads(r["voorstel"]),
            "aangemaakt_op": r["aangemaakt_op"].isoformat(),
        }
        for r in rows
    ]


async def _haal_pending_voorstel(conn, voorstel_id: str, gebruiker: dict) -> dict:
    """Haal een voorstel op en controleer dat de huidige gebruiker de zender is
    en dat het nog pending is. Werpt HTTPException bij een probleem."""
    row = await conn.fetchrow(
        "SELECT afzender_id, afzender, voorstel, status FROM voorgestelde_mutaties WHERE id = $1",
        voorstel_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Voorstel niet gevonden")
    if str(row["afzender_id"]) != str(gebruiker["id"]):
        raise HTTPException(status_code=403, detail="Alleen de zender mag dit voorstel behandelen")
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Voorstel is al {row['status']}")
    return row


@router.post("/mutaties/{voorstel_id}/bevestig")
async def bevestig_mutatie(voorstel_id: str, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Bevestig een voorstel: pas het toe op de planning en meld de betrokkenen.
    Alleen de zender van het oorspronkelijke bericht mag dit."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        row = await _haal_pending_voorstel(conn, voorstel_id, gebruiker)
        voorstel = json.loads(row["voorstel"])

        try:
            task_id = await pas_mutatie_toe(conn, voorstel, row["afzender"])
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Kon voorstel niet toepassen: {e}")

        await conn.execute(
            """UPDATE voorgestelde_mutaties
               SET status = 'bevestigd', behandeld_door = $2, behandeld_op = NOW()
               WHERE id = $1""",
            voorstel_id, gebruiker["naam"],
        )

        ids, taak = await _betrokken_gebruiker_ids(conn, task_id, row["afzender_id"])
        tekst = _melding_tekst(voorstel.get("actie"), taak, row["afzender"])
        await _maak_meldingen(conn, ids, tekst, task_id, voorstel_id)

        # Leg door de AI herkende volgorde-relaties vast, voer de cascade uit
        # en meld iedereen wiens taak automatisch verschuift.
        verschoven, cascade_meldingen = await verwerk_voorstel_relaties(
            conn, voorstel, task_id, row["afzender_id"], voorstel_id
        )
    finally:
        await conn.close()

    totaal_meldingen = len(ids) + cascade_meldingen
    print(
        f"✅ Voorstel {voorstel_id} bevestigd door {gebruiker['naam']}; "
        f"{totaal_meldingen} melding(en) verstuurd, "
        f"{len(verschoven)} taak/taken automatisch verschoven",
        flush=True,
    )
    return {
        "ok": True,
        "status": "bevestigd",
        "taak_id": task_id,
        "meldingen_verstuurd": totaal_meldingen,
        "automatisch_verschoven": [
            {
                "taak_id": v["taak_id"],
                "naam": v["naam"],
                "toegewezen_aan": v["toegewezen_aan"],
                "nieuwe_start": v["nieuwe_start"].isoformat(),
                "nieuwe_eind": v["nieuwe_eind"].isoformat(),
            }
            for v in verschoven
        ],
    }


@router.post("/mutaties/{voorstel_id}/afwijs")
async def wijs_mutatie_af(voorstel_id: str, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Wijs een voorstel af. Alleen de zender mag dit; de planning blijft ongewijzigd."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        await _haal_pending_voorstel(conn, voorstel_id, gebruiker)
        await conn.execute(
            """UPDATE voorgestelde_mutaties
               SET status = 'afgewezen', behandeld_door = $2, behandeld_op = NOW()
               WHERE id = $1""",
            voorstel_id, gebruiker["naam"],
        )
    finally:
        await conn.close()
    return {"ok": True, "status": "afgewezen"}


# ---------------------------------------------------------------------------
# Planning leegmaken (alleen admin)
# ---------------------------------------------------------------------------

@router.post("/planning/leegmaken")
async def planning_leegmaken(bevestiging: str = Body(..., embed=True),
                             gebruiker: dict = Depends(vereist_admin)):
    """Wist ALLE taken, volgorde-relaties, openstaande voorstellen en
    meldingen. Definitief — bedoeld om testdata op te ruimen.
    Vereist het bevestigingswoord 'LEEGMAKEN' om ongelukken te voorkomen."""
    if bevestiging != "LEEGMAKEN":
        raise HTTPException(
            status_code=422,
            detail="Typ LEEGMAKEN als bevestiging om de planning te wissen.",
        )

    conn = await asyncpg.connect(_raw_db_url())
    try:
        aantal_taken = await conn.fetchval("SELECT COUNT(*) FROM tasks") or 0
        await conn.execute("DELETE FROM meldingen")
        await conn.execute("DELETE FROM voorgestelde_mutaties WHERE status = 'pending'")
        await conn.execute("DELETE FROM taak_afhankelijkheden")
        await conn.execute("DELETE FROM tasks")
        await conn.execute(
            """INSERT INTO audit_log (gebruiker_naam, actie, details)
               VALUES ($1, 'planning_leeggemaakt', $2)""",
            gebruiker["naam"], f"{aantal_taken} taken gewist (incl. relaties, voorstellen en meldingen)",
        )
    finally:
        await conn.close()

    print(f"🗑️ Planning leeggemaakt door {gebruiker['naam']}: {aantal_taken} taken", flush=True)
    return {"ok": True, "taken_gewist": aantal_taken}


# ---------------------------------------------------------------------------
# Meldingen-endpoints
# ---------------------------------------------------------------------------

@router.get("/meldingen")
async def lijst_meldingen(gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Geeft de meldingen van de ingelogde gebruiker terug (nieuwste eerst)."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        rows = await conn.fetch(
            """SELECT id, tekst, taak_id, voorstel_id, gelezen, tijdstip
               FROM meldingen WHERE gebruiker_id = $1
               ORDER BY tijdstip DESC LIMIT 100""",
            gebruiker["id"],
        )
    finally:
        await conn.close()
    return [
        {
            "id": str(r["id"]),
            "tekst": r["tekst"],
            "taak_id": str(r["taak_id"]) if r["taak_id"] else None,
            "voorstel_id": str(r["voorstel_id"]) if r["voorstel_id"] else None,
            "gelezen": r["gelezen"],
            "tijdstip": r["tijdstip"].isoformat(),
        }
        for r in rows
    ]


@router.get("/meldingen/ongelezen")
async def aantal_ongelezen_meldingen(gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Geeft het aantal ongelezen meldingen terug (voor een badge in de UI)."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        aantal = await conn.fetchval(
            "SELECT COUNT(*) FROM meldingen WHERE gebruiker_id = $1 AND gelezen = FALSE",
            gebruiker["id"],
        )
    finally:
        await conn.close()
    return {"ongelezen": aantal or 0}


@router.post("/meldingen/{melding_id}/gelezen")
async def markeer_melding_gelezen(melding_id: str, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Markeert één melding van de ingelogde gebruiker als gelezen."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        resultaat = await conn.execute(
            "UPDATE meldingen SET gelezen = TRUE WHERE id = $1 AND gebruiker_id = $2",
            melding_id, gebruiker["id"],
        )
    finally:
        await conn.close()
    if int(resultaat.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="Melding niet gevonden")
    return {"ok": True}
