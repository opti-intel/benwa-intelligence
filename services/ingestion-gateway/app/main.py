"""Ingestion Gateway - FastAPI service for raw data ingestion."""

import asyncio
import sys
import os
from contextlib import asynccontextmanager
from datetime import date as date_type
from typing import Optional
from uuid import UUID, uuid4

import asyncpg
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import (
    hash_wachtwoord, verifieer_wachtwoord, maak_token,
    get_huidige_gebruiker, vereist_admin, valideer_wachtwoord,
)

# Add shared library to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.schemas import IngestionRecord, KafkaEvent
from shared.kafka_utils import get_kafka_producer, publish_event
from shared.db import engine

from .parser import normalize_payload
from .pdf_parser import parse_gantt_pdf
from .tasks import router as tasks_router
from .nl_parser import parse_bericht

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
_records: dict[UUID, IngestionRecord] = {}
_kafka_producer = None

CREATE_TASKS_TABLE = """
    CREATE TABLE IF NOT EXISTS tasks (
        id UUID PRIMARY KEY,
        naam VARCHAR(255) NOT NULL,
        beschrijving TEXT DEFAULT '',
        status VARCHAR(20) NOT NULL DEFAULT 'gepland',
        startdatum DATE,
        einddatum DATE,
        toegewezen_aan VARCHAR(255) DEFAULT '',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""

CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS gebruikers (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        naam VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        wachtwoord_hash VARCHAR(255) NOT NULL,
        rol VARCHAR(20) NOT NULL DEFAULT 'medewerker',
        bedrijf VARCHAR(255) DEFAULT '',
        actief BOOLEAN DEFAULT TRUE,
        aangemaakt_op TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""

CREATE_AUDIT_TABLE = """
    CREATE TABLE IF NOT EXISTS audit_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        gebruiker_naam VARCHAR(255) NOT NULL DEFAULT 'onbekend',
        gebruiker_email VARCHAR(255) NOT NULL DEFAULT '',
        actie VARCHAR(100) NOT NULL,
        details TEXT DEFAULT '',
        ip_adres VARCHAR(64) DEFAULT '',
        tijdstip TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""

CREATE_BERICHTEN_TABLE = """
    CREATE TABLE IF NOT EXISTS berichten (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        van_id UUID NOT NULL,
        naar_id UUID NOT NULL,
        tekst TEXT NOT NULL,
        gelezen BOOLEAN DEFAULT FALSE,
        tijdstip TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""

CREATE_AI_BERICHTEN_TABLE = """
    CREATE TABLE IF NOT EXISTS ai_berichten (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        gebruiker_id UUID NOT NULL,
        rol VARCHAR(10) NOT NULL,
        tekst TEXT NOT NULL,
        tijdstip TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""

CREATE_GROEPBERICHTEN_TABLE = """
    CREATE TABLE IF NOT EXISTS groepberichten (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        groep_naam VARCHAR(255) NOT NULL,
        van_id UUID NOT NULL,
        tekst TEXT NOT NULL,
        tijdstip TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""

CREATE_AANGEPASTE_GROEPEN_TABLE = """
    CREATE TABLE IF NOT EXISTS aangepaste_groepen (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        naam VARCHAR(255) NOT NULL UNIQUE,
        aangemaakt_door UUID REFERENCES gebruikers(id) ON DELETE SET NULL,
        aangemaakt_op TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""

CREATE_AANGEPASTE_GROEP_LEDEN_TABLE = """
    CREATE TABLE IF NOT EXISTS aangepaste_groep_leden (
        groep_id UUID REFERENCES aangepaste_groepen(id) ON DELETE CASCADE,
        gebruiker_id UUID REFERENCES gebruikers(id) ON DELETE CASCADE,
        PRIMARY KEY (groep_id, gebruiker_id)
    )
"""


async def _log_audit(actie: str, details: str = "", gebruiker_naam: str = "systeem",
                     gebruiker_email: str = "", ip_adres: str = ""):
    """Schrijf een audit-regel naar de database (fire-and-forget)."""
    try:
        raw_url = _get_raw_db_url()
        conn = await asyncpg.connect(raw_url)
        await conn.execute(
            """INSERT INTO audit_log (gebruiker_naam, gebruiker_email, actie, details, ip_adres)
               VALUES ($1, $2, $3, $4, $5)""",
            gebruiker_naam, gebruiker_email, actie, details, ip_adres
        )
        await conn.close()
    except Exception as e:
        print(f"⚠️ Audit log mislukt: {e}", flush=True)


def _get_raw_db_url() -> str:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://benwa:changeme@postgres:5432/benwa_intelligence"
    )
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _parse_date(val: Optional[str]) -> Optional[date_type]:
    """Convert 'YYYY-MM-DD' string to date object, or None."""
    if not val:
        return None
    try:
        return date_type.fromisoformat(val)
    except Exception:
        return None


async def ensure_tables():
    """Create all tables if they don't exist. Retries up to 10x."""
    raw_url = _get_raw_db_url()
    for attempt in range(10):
        try:
            conn = await asyncpg.connect(raw_url)
            await conn.execute(CREATE_TASKS_TABLE)
            await conn.execute(CREATE_USERS_TABLE)
            await conn.execute(CREATE_AUDIT_TABLE)
            await conn.execute(CREATE_BERICHTEN_TABLE)
            await conn.execute(CREATE_AI_BERICHTEN_TABLE)
            await conn.execute(CREATE_GROEPBERICHTEN_TABLE)
            await conn.execute(CREATE_AANGEPASTE_GROEPEN_TABLE)
            await conn.execute(CREATE_AANGEPASTE_GROEP_LEDEN_TABLE)
            # Create default admin account if no users exist yet
            count = await conn.fetchval("SELECT COUNT(*) FROM gebruikers")
            if count == 0:
                admin_hash = hash_wachtwoord("admin123")
                await conn.execute(
                    """INSERT INTO gebruikers (naam, email, wachtwoord_hash, rol, bedrijf)
                       VALUES ($1, $2, $3, $4, $5)""",
                    "Beheerder", "admin@optiintel.nl", admin_hash, "admin", "Opti Corporation"
                )
                print("✅ Standaard admin aangemaakt: admin@optiintel.nl / admin123", flush=True)
            await conn.close()
            print("✅ Tabellen klaar", flush=True)
            return
        except Exception as e:
            print(f"⏳ DB not ready (attempt {attempt + 1}/10): {e}", flush=True)
            await asyncio.sleep(2)
    print("❌ Could not create tables after 10 attempts", flush=True)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _kafka_producer
    await ensure_tables()
    try:
        _kafka_producer = await get_kafka_producer()
    except Exception:
        _kafka_producer = None
    yield
    if _kafka_producer is not None:
        await _kafka_producer.stop()


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Ingestion Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    source_type: str
    source_uri: Optional[str] = None
    raw_payload: dict


class NieuweGebruiker(BaseModel):
    naam: str
    email: str
    wachtwoord: str
    rol: str = "medewerker"
    bedrijf: str = ""


class WachtwoordWijzig(BaseModel):
    nieuw_wachtwoord: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/ingest", response_model=IngestionRecord, status_code=201)
async def ingest(request: IngestRequest):
    normalized = normalize_payload(request.source_type, request.raw_payload)
    record = IngestionRecord(
        source_type=request.source_type,
        source_uri=request.source_uri,
        raw_payload=request.raw_payload,
        normalized_payload=normalized,
        status="ingested",
    )
    _records[record.id] = record
    if _kafka_producer is not None:
        event = KafkaEvent(
            event_type="raw_ingestion",
            payload=record.model_dump(mode="json"),
            source_service="ingestion-gateway",
        )
        try:
            await publish_event(_kafka_producer, "raw-ingestion", event)
        except Exception:
            record.status = "kafka_publish_failed"
    return record


@app.get("/ingest/{record_id}", response_model=IngestionRecord)
async def get_record(record_id: UUID):
    record = _records.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@app.get("/ingest", response_model=list[IngestionRecord])
async def list_records(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    all_records = sorted(_records.values(), key=lambda r: r.created_at, reverse=True)
    return all_records[offset : offset + limit]


app.include_router(tasks_router)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/login")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    ip = request.client.host if request.client else "onbekend"
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    row = await conn.fetchrow(
        "SELECT id, naam, wachtwoord_hash, rol, bedrijf, actief FROM gebruikers WHERE email = $1",
        form.username.lower().strip()
    )
    await conn.close()

    if not row or not row["actief"]:
        await _log_audit("login_mislukt", f"Onbekend e-mailadres: {form.username}", ip_adres=ip)
        raise HTTPException(status_code=401, detail="Onbekend e-mailadres of account inactief")
    if not verifieer_wachtwoord(form.password, row["wachtwoord_hash"]):
        await _log_audit("login_mislukt", f"Onjuist wachtwoord voor: {form.username}",
                         gebruiker_naam=row["naam"], gebruiker_email=form.username, ip_adres=ip)
        raise HTTPException(status_code=401, detail="Onjuist wachtwoord")

    token = maak_token({
        "sub": str(row["id"]),
        "naam": row["naam"],
        "rol": row["rol"],
        "bedrijf": row["bedrijf"],
    })
    await _log_audit("login_geslaagd", f"Ingelogd als {row['rol']}",
                     gebruiker_naam=row["naam"], gebruiker_email=form.username, ip_adres=ip)
    return {
        "access_token": token,
        "token_type": "bearer",
        "id": str(row["id"]),
        "naam": row["naam"],
        "rol": row["rol"],
        "bedrijf": row["bedrijf"],
    }


@app.get("/auth/mij")
async def mijn_profiel(gebruiker: dict = Depends(get_huidige_gebruiker)):
    return gebruiker


@app.get("/auth/gebruikers")
async def lijst_gebruikers(gebruiker: dict = Depends(vereist_admin)):
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    rows = await conn.fetch(
        "SELECT id, naam, email, rol, bedrijf, actief, aangemaakt_op FROM gebruikers ORDER BY aangemaakt_op DESC"
    )
    await conn.close()
    return [dict(r) for r in rows]


@app.post("/auth/gebruikers", status_code=201)
async def maak_gebruiker(data: NieuweGebruiker, _admin: dict = Depends(vereist_admin)):
    # Wachtwoordbeleid
    fouten = valideer_wachtwoord(data.wachtwoord)
    if fouten:
        raise HTTPException(status_code=422, detail=f"Wachtwoord voldoet niet: {', '.join(fouten)}")
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    bestaand = await conn.fetchval("SELECT id FROM gebruikers WHERE email = $1", data.email.lower().strip())
    if bestaand:
        await conn.close()
        raise HTTPException(status_code=409, detail="E-mailadres al in gebruik")
    wachtwoord_hash = hash_wachtwoord(data.wachtwoord)
    row = await conn.fetchrow(
        """INSERT INTO gebruikers (naam, email, wachtwoord_hash, rol, bedrijf)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING id, naam, email, rol, bedrijf, actief""",
        data.naam, data.email.lower().strip(), wachtwoord_hash,
        data.rol, data.bedrijf
    )
    await conn.close()
    await _log_audit("gebruiker_aangemaakt", f"Nieuw account: {data.email} ({data.rol})",
                     gebruiker_naam=_admin["naam"], gebruiker_email=_admin.get("email", ""))
    return dict(row)


@app.patch("/auth/gebruikers/{gebruiker_id}")
async def update_gebruiker(
    gebruiker_id: str,
    data: dict,
    _admin: dict = Depends(vereist_admin)
):
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    allowed = {"naam", "rol", "bedrijf", "actief"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        await conn.close()
        raise HTTPException(status_code=400, detail="Geen geldige velden")
    sets = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    vals = list(updates.values())
    await conn.execute(
        f"UPDATE gebruikers SET {sets} WHERE id = $1",
        gebruiker_id, *vals
    )
    await conn.close()
    detail = ", ".join(f"{k}={v}" for k, v in updates.items())
    await _log_audit("gebruiker_bijgewerkt", f"ID {gebruiker_id}: {detail}",
                     gebruiker_naam=_admin["naam"])
    return {"ok": True}


@app.delete("/auth/gebruikers/{gebruiker_id}")
async def verwijder_gebruiker(gebruiker_id: str, _admin: dict = Depends(vereist_admin)):
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    naam_row = await conn.fetchval("SELECT naam FROM gebruikers WHERE id = $1", gebruiker_id)
    await conn.execute("DELETE FROM gebruikers WHERE id = $1", gebruiker_id)
    await conn.close()
    await _log_audit("gebruiker_verwijderd", f"Account verwijderd: {naam_row or gebruiker_id}",
                     gebruiker_naam=_admin["naam"])
    return {"ok": True}


@app.post("/auth/gebruikers/{gebruiker_id}/wachtwoord")
async def reset_wachtwoord(
    gebruiker_id: str,
    data: WachtwoordWijzig,
    _admin: dict = Depends(vereist_admin)
):
    fouten = valideer_wachtwoord(data.nieuw_wachtwoord)
    if fouten:
        raise HTTPException(status_code=422, detail=f"Wachtwoord voldoet niet: {', '.join(fouten)}")
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    naam_row = await conn.fetchval("SELECT naam FROM gebruikers WHERE id = $1", gebruiker_id)
    nieuw_hash = hash_wachtwoord(data.nieuw_wachtwoord)
    await conn.execute(
        "UPDATE gebruikers SET wachtwoord_hash = $1 WHERE id = $2",
        nieuw_hash, gebruiker_id
    )
    await conn.close()
    await _log_audit("wachtwoord_reset", f"Wachtwoord gewijzigd voor: {naam_row or gebruiker_id}",
                     gebruiker_naam=_admin["naam"])
    return {"ok": True}


@app.post("/auth/mij/wachtwoord")
async def wijzig_eigen_wachtwoord(
    data: WachtwoordWijzig,
    gebruiker: dict = Depends(get_huidige_gebruiker)
):
    """Medewerker wijzigt eigen wachtwoord."""
    fouten = valideer_wachtwoord(data.nieuw_wachtwoord)
    if fouten:
        raise HTTPException(status_code=422, detail=f"Wachtwoord voldoet niet: {', '.join(fouten)}")
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    nieuw_hash = hash_wachtwoord(data.nieuw_wachtwoord)
    await conn.execute(
        "UPDATE gebruikers SET wachtwoord_hash = $1 WHERE id = $2",
        nieuw_hash, gebruiker["id"]
    )
    await conn.close()
    await _log_audit("eigen_wachtwoord_gewijzigd", "Eigen wachtwoord aangepast",
                     gebruiker_naam=gebruiker["naam"])
    return {"ok": True}


@app.get("/auth/audit-log")
async def haal_audit_log(
    _admin: dict = Depends(vereist_admin),
    limit: int = Query(200, ge=1, le=1000)
):
    raw_url = _get_raw_db_url()
    conn = await asyncpg.connect(raw_url)
    rows = await conn.fetch(
        "SELECT id, gebruiker_naam, gebruiker_email, actie, details, ip_adres, tijdstip "
        "FROM audit_log ORDER BY tijdstip DESC LIMIT $1",
        limit
    )
    await conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# PDF Ingest
# ---------------------------------------------------------------------------
@app.post("/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...), gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Accept a PDF upload, parse Gantt planning, and save tasks to DB."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Alleen PDF bestanden worden geaccepteerd")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Leeg bestand")

    # Parse PDF
    try:
        parsed_tasks = parse_gantt_pdf(pdf_bytes)
    except Exception as e:
        print(f"❌ PDF parse error: {e}", flush=True)
        raise HTTPException(status_code=422, detail=f"Kon PDF niet verwerken: {e}")

    print(f"📋 PDF parsed: {len(parsed_tasks)} taken gevonden", flush=True)

    if not parsed_tasks:
        return {"totaal_gevonden": 0, "taken_aangemaakt": 0, "taken": []}

    raw_url = _get_raw_db_url()
    print(f"🔌 Connecting to DB: {raw_url[:40]}...", flush=True)

    try:
        conn = await asyncpg.connect(raw_url)
        print("✅ DB connected", flush=True)

        # Ensure table exists
        await conn.execute(CREATE_TASKS_TABLE)

        created_tasks: list[dict] = []
        for t in parsed_tasks:
            task_id = uuid4()  # UUID object, not string
            naam = t["naam"]
            beschrijving = t.get("beschrijving", "")
            status = t.get("status", "gepland")
            startdatum = _parse_date(t.get("startdatum"))
            einddatum = _parse_date(t.get("einddatum"))
            toegewezen_aan = t.get("toegewezen_aan", "")

            await conn.execute(
                """
                INSERT INTO tasks (id, naam, beschrijving, status, startdatum, einddatum, toegewezen_aan)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO NOTHING
                """,
                task_id, naam, beschrijving, status, startdatum, einddatum, toegewezen_aan,
            )
            created_tasks.append({
                "id": str(task_id),
                "naam": naam,
                "beschrijving": beschrijving,
                "status": status,
                "startdatum": str(startdatum) if startdatum else None,
                "einddatum": str(einddatum) if einddatum else None,
                "toegewezen_aan": toegewezen_aan,
            })

        await conn.close()
        print(f"✅ {len(created_tasks)} taken opgeslagen in DB", flush=True)
        await _log_audit(
            "pdf_geupload",
            f"'{file.filename}' — {len(created_tasks)} taken aangemaakt",
            gebruiker_naam=gebruiker["naam"],
        )
        return {
            "totaal_gevonden": len(parsed_tasks),
            "taken_aangemaakt": len(created_tasks),
            "taken": created_tasks,
        }

    except Exception as e:
        print(f"❌ DB error in ingest_pdf: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Database fout: {e}")


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

class NieuwBericht(BaseModel):
    naar_id: str
    tekst: str


@app.get("/chat/gebruikers")
async def chat_gebruikers(gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Geeft een lijst van alle andere gebruikers terug (veilig: geen email/wachtwoord)."""
    conn = await asyncpg.connect(_get_raw_db_url())
    rows = await conn.fetch(
        """SELECT id, naam, rol, bedrijf FROM gebruikers
           WHERE actief = TRUE AND id != $1
           ORDER BY rol, naam""",
        gebruiker["id"]
    )
    await conn.close()
    return [{"id": str(r["id"]), "naam": r["naam"], "rol": r["rol"], "bedrijf": r["bedrijf"]} for r in rows]


@app.get("/chat/berichten/{andere_id}")
async def haal_berichten(andere_id: str, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Haalt de berichtengeschiedenis op tussen de huidige gebruiker en een andere gebruiker."""
    conn = await asyncpg.connect(_get_raw_db_url())
    rows = await conn.fetch(
        """SELECT id, van_id, naar_id, tekst, gelezen, tijdstip
           FROM berichten
           WHERE (van_id = $1 AND naar_id = $2)
              OR (van_id = $2 AND naar_id = $1)
           ORDER BY tijdstip ASC
           LIMIT 200""",
        gebruiker["id"], andere_id
    )
    # Markeer inkomende ongelezen berichten als gelezen
    await conn.execute(
        """UPDATE berichten SET gelezen = TRUE
           WHERE naar_id = $1 AND van_id = $2 AND gelezen = FALSE""",
        gebruiker["id"], andere_id
    )
    await conn.close()
    return [
        {
            "id": str(r["id"]),
            "van_id": str(r["van_id"]),
            "naar_id": str(r["naar_id"]),
            "tekst": r["tekst"],
            "gelezen": r["gelezen"],
            "tijdstip": r["tijdstip"].isoformat(),
        }
        for r in rows
    ]


async def _verwerk_bericht_ai(tekst: str, afzender_naam: str) -> dict | None:
    """Verwerk een chatbericht via de AI parser. Maak een taak aan als er een wordt herkend.
    Geeft de taak terug als dict, of None als er niets gevonden werd."""
    try:
        resultaat = parse_bericht(tekst)
        if not resultaat.get("heeft_taak"):
            return None
        taak = resultaat["taak"]
        task_id = uuid4()
        startdatum = _parse_date(taak.get("startdatum"))
        einddatum = _parse_date(taak.get("einddatum"))
        toegewezen = taak.get("toegewezen_aan") or afzender_naam
        conn = await asyncpg.connect(_get_raw_db_url())
        await conn.execute(
            """INSERT INTO tasks (id, naam, beschrijving, status, startdatum, einddatum, toegewezen_aan)
               VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING""",
            task_id, taak["naam"], taak.get("beschrijving", ""),
            "gepland", startdatum, einddatum, toegewezen,
        )
        await conn.close()
        print(f"✅ AI taak via chat aangemaakt: {taak['naam']} (door {afzender_naam})", flush=True)
        return {"id": str(task_id), "naam": taak["naam"], "antwoord": resultaat.get("antwoord")}
    except Exception as e:
        print(f"⚠️ AI chat parser fout: {e}", flush=True)
        return None


@app.post("/chat/berichten", status_code=201)
async def stuur_bericht(data: NieuwBericht, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Stuurt een bericht naar een andere gebruiker."""
    if not data.tekst.strip():
        raise HTTPException(status_code=400, detail="Bericht mag niet leeg zijn")
    conn = await asyncpg.connect(_get_raw_db_url())
    row = await conn.fetchrow(
        """INSERT INTO berichten (van_id, naar_id, tekst)
           VALUES ($1, $2, $3)
           RETURNING id, van_id, naar_id, tekst, gelezen, tijdstip""",
        gebruiker["id"], data.naar_id, data.tekst.strip()
    )
    await conn.close()

    # AI controleert het bericht op taken
    ai_taak = await _verwerk_bericht_ai(data.tekst.strip(), gebruiker["naam"])

    return {
        "id": str(row["id"]),
        "van_id": str(row["van_id"]),
        "naar_id": str(row["naar_id"]),
        "tekst": row["tekst"],
        "gelezen": row["gelezen"],
        "tijdstip": row["tijdstip"].isoformat(),
        "ai_taak": ai_taak,
    }


@app.get("/chat/ongelezen")
async def ongelezen_berichten(gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Geeft het aantal ongelezen berichten per gesprek terug."""
    conn = await asyncpg.connect(_get_raw_db_url())
    rows = await conn.fetch(
        """SELECT van_id, COUNT(*) as aantal
           FROM berichten
           WHERE naar_id = $1 AND gelezen = FALSE
           GROUP BY van_id""",
        gebruiker["id"]
    )
    await conn.close()
    return {str(r["van_id"]): r["aantal"] for r in rows}


# ---------------------------------------------------------------------------
# AI Assistent chat
# ---------------------------------------------------------------------------

class AiVraag(BaseModel):
    tekst: str


async def _genereer_ai_antwoord(vraag: str, gebruiker_naam: str) -> str:
    """Genereert een contextbewust antwoord op basis van de taken in de database."""
    v = vraag.lower()
    conn = await asyncpg.connect(_get_raw_db_url())
    try:
        if any(w in v for w in ["hoeveel", "aantal", "totaal"]):
            totaal = await conn.fetchval("SELECT COUNT(*) FROM tasks")
            gepland = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'gepland'")
            bezig = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'bezig'")
            klaar = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'klaar'")
            return (
                f"📊 **Projectoverzicht**\n\n"
                f"• Totaal taken: {totaal}\n"
                f"• Gepland: {gepland}\n"
                f"• Bezig: {bezig}\n"
                f"• Klaar: {klaar}\n\n"
                f"Voortgang: {round((klaar / totaal * 100) if totaal else 0)}% voltooid."
            )

        elif any(w in v for w in ["taken", "taak", "overzicht", "lijst", "status"]):
            rows = await conn.fetch(
                """SELECT naam, status, toegewezen_aan, einddatum
                   FROM tasks ORDER BY einddatum ASC NULLS LAST LIMIT 8"""
            )
            if not rows:
                return "Er zijn nog geen taken in het systeem."
            regels = "\n".join(
                f"• {r['naam']} [{r['status']}]"
                + (f" → {r['toegewezen_aan']}" if r['toegewezen_aan'] else "")
                for r in rows
            )
            return f"📋 **Recente taken:**\n\n{regels}"

        elif any(w in v for w in ["bezig", "lopend", "actief"]):
            rows = await conn.fetch(
                "SELECT naam, toegewezen_aan FROM tasks WHERE status = 'bezig' LIMIT 6"
            )
            if not rows:
                return "Er zijn momenteel geen taken in uitvoering."
            regels = "\n".join(f"• {r['naam']}" + (f" ({r['toegewezen_aan']})" if r['toegewezen_aan'] else "") for r in rows)
            return f"🔨 **Taken in uitvoering:**\n\n{regels}"

        elif any(w in v for w in ["vandaag", "deadline", "urgent", "spoed"]):
            from datetime import date as _date
            vandaag = str(_date.today())
            rows = await conn.fetch(
                "SELECT naam, status, einddatum FROM tasks WHERE einddatum <= $1 AND status != 'klaar' ORDER BY einddatum ASC LIMIT 6",
                vandaag
            )
            if not rows:
                return "✅ Geen urgente taken voor vandaag of verlopen deadlines!"
            regels = "\n".join(f"• {r['naam']} (deadline: {r['einddatum']})" for r in rows)
            return f"⚠️ **Urgente taken:**\n\n{regels}"

        elif any(w in v for w in ["help", "wat kun", "wat kan", "waarvoor"]):
            return (
                f"👋 Hallo {gebruiker_naam}! Ik ben de **Opti Intel AI-assistent**.\n\n"
                "Ik kan je helpen met:\n"
                "• **Projectstatus** — vraag naar 'hoeveel taken'\n"
                "• **Takenlijst** — vraag naar 'overzicht taken'\n"
                "• **Lopende taken** — vraag wat er 'bezig' is\n"
                "• **Urgente taken** — vraag naar 'deadlines vandaag'\n\n"
                "Stel gewoon een vraag in gewoon Nederlands!"
            )

        else:
            return (
                f"Dag {gebruiker_naam}! Ik begrijp je vraag niet helemaal. 🤔\n\n"
                "Probeer iets als:\n"
                "• 'Hoeveel taken zijn er?'\n"
                "• 'Geef een overzicht van de taken'\n"
                "• 'Welke taken zijn bezig?'\n"
                "• 'Zijn er urgente deadlines vandaag?'"
            )
    finally:
        await conn.close()


@app.get("/chat/ai/berichten")
async def haal_ai_berichten(gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Haalt de AI-gespreksgeschiedenis op voor de ingelogde gebruiker."""
    conn = await asyncpg.connect(_get_raw_db_url())
    rows = await conn.fetch(
        """SELECT id, gebruiker_id, rol, tekst, tijdstip
           FROM ai_berichten WHERE gebruiker_id = $1
           ORDER BY tijdstip ASC LIMIT 100""",
        gebruiker["id"]
    )
    await conn.close()
    return [
        {
            "id": str(r["id"]),
            "gebruiker_id": str(r["gebruiker_id"]),
            "rol": r["rol"],
            "tekst": r["tekst"],
            "tijdstip": r["tijdstip"].isoformat(),
        }
        for r in rows
    ]


@app.post("/chat/ai", status_code=201)
async def stuur_ai_bericht(data: AiVraag, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Verwerkt een bericht aan de AI en geeft een antwoord terug."""
    if not data.tekst.strip():
        raise HTTPException(status_code=400, detail="Bericht mag niet leeg zijn")

    conn = await asyncpg.connect(_get_raw_db_url())
    # Sla gebruikersvraag op
    await conn.execute(
        "INSERT INTO ai_berichten (gebruiker_id, rol, tekst) VALUES ($1, $2, $3)",
        gebruiker["id"], "user", data.tekst.strip()
    )
    # Genereer antwoord
    antwoord = await _genereer_ai_antwoord(data.tekst, gebruiker["naam"])
    # Sla AI-antwoord op
    row = await conn.fetchrow(
        "INSERT INTO ai_berichten (gebruiker_id, rol, tekst) VALUES ($1, $2, $3) RETURNING id, tijdstip",
        gebruiker["id"], "ai", antwoord
    )
    await conn.close()
    return {
        "vraag": data.tekst.strip(),
        "antwoord": antwoord,
        "tijdstip": row["tijdstip"].isoformat(),
    }


# ---------------------------------------------------------------------------
# Groepschat endpoints
# ---------------------------------------------------------------------------

class NieuwGroepBericht(BaseModel):
    tekst: str


class NieuweAangepaste_Groep(BaseModel):
    naam: str
    leden: list[str]  # user IDs als strings


@app.get("/chat/groepen")
async def haal_groepen(gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Geeft alle bedrijfsgroepen + aangepaste groepen terug waarvan de gebruiker lid is."""
    conn = await asyncpg.connect(_get_raw_db_url())
    eigen_bedrijf = await conn.fetchval(
        "SELECT bedrijf FROM gebruikers WHERE id = $1", gebruiker["id"]
    )
    # Automatische bedrijfsgroepen
    rows = await conn.fetch(
        """SELECT bedrijf, COUNT(*) as leden
           FROM gebruikers WHERE actief = TRUE AND bedrijf != '' AND bedrijf IS NOT NULL
           GROUP BY bedrijf ORDER BY bedrijf"""
    )
    # Aangepaste groepen waarbij gebruiker lid is
    custom_rows = await conn.fetch(
        """SELECT ag.id, ag.naam, COUNT(agl2.gebruiker_id) as leden
           FROM aangepaste_groepen ag
           JOIN aangepaste_groep_leden agl ON agl.groep_id = ag.id AND agl.gebruiker_id = $1
           JOIN aangepaste_groep_leden agl2 ON agl2.groep_id = ag.id
           GROUP BY ag.id, ag.naam
           ORDER BY ag.naam""",
        gebruiker["id"]
    )
    await conn.close()

    groepen = []
    for r in rows:
        if gebruiker["rol"] in ("admin", "aannemer") or r["bedrijf"] == eigen_bedrijf:
            groepen.append({
                "id": r["bedrijf"],
                "naam": r["bedrijf"],
                "leden": r["leden"],
                "is_eigen_bedrijf": r["bedrijf"] == eigen_bedrijf,
                "type": "bedrijf",
            })
    for r in custom_rows:
        groepen.append({
            "id": r["naam"],   # naam als sleutel voor groepberichten-tabel
            "naam": r["naam"],
            "leden": r["leden"],
            "is_eigen_bedrijf": False,
            "type": "custom",
        })
    return groepen


@app.post("/chat/groepen/aanmaken", status_code=201)
async def maak_groep_aan(data: NieuweAangepaste_Groep, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Maakt een nieuwe aangepaste groep aan met geselecteerde leden."""
    naam = data.naam.strip()
    if not naam:
        raise HTTPException(status_code=400, detail="Groepsnaam mag niet leeg zijn")
    conn = await asyncpg.connect(_get_raw_db_url())
    # Check dubbele naam
    bestaand = await conn.fetchval("SELECT id FROM aangepaste_groepen WHERE naam = $1", naam)
    if bestaand:
        await conn.close()
        raise HTTPException(status_code=409, detail="Groepsnaam is al in gebruik")
    # Groep aanmaken
    groep_id = await conn.fetchval(
        "INSERT INTO aangepaste_groepen (naam, aangemaakt_door) VALUES ($1, $2) RETURNING id",
        naam, gebruiker["id"]
    )
    # Maakder + gekozen leden toevoegen
    alle_ids = list({gebruiker["id"]} | {UUID(lid) for lid in data.leden if lid})
    for lid_id in alle_ids:
        await conn.execute(
            """INSERT INTO aangepaste_groep_leden (groep_id, gebruiker_id)
               VALUES ($1, $2) ON CONFLICT DO NOTHING""",
            groep_id, lid_id
        )
    await conn.close()
    return {
        "id": naam,
        "naam": naam,
        "leden": len(alle_ids),
        "is_eigen_bedrijf": False,
        "type": "custom",
    }


@app.get("/chat/groepen/{groep_naam}/berichten")
async def haal_groepberichten(groep_naam: str, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Haalt berichten op van een bedrijfsgroep."""
    conn = await asyncpg.connect(_get_raw_db_url())
    rows = await conn.fetch(
        """SELECT gb.id, gb.van_id, gb.tekst, gb.tijdstip, g.naam as van_naam, g.bedrijf as van_bedrijf
           FROM groepberichten gb
           LEFT JOIN gebruikers g ON g.id = gb.van_id
           WHERE gb.groep_naam = $1
           ORDER BY gb.tijdstip ASC LIMIT 200""",
        groep_naam
    )
    await conn.close()
    return [
        {
            "id": str(r["id"]),
            "van_id": str(r["van_id"]),
            "van_naam": r["van_naam"] or "Onbekend",
            "tekst": r["tekst"],
            "tijdstip": r["tijdstip"].isoformat(),
        }
        for r in rows
    ]


@app.post("/chat/groepen/{groep_naam}/berichten", status_code=201)
async def stuur_groepbericht(groep_naam: str, data: NieuwGroepBericht, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Stuurt een bericht naar een bedrijfsgroep."""
    if not data.tekst.strip():
        raise HTTPException(status_code=400, detail="Bericht mag niet leeg zijn")
    conn = await asyncpg.connect(_get_raw_db_url())
    row = await conn.fetchrow(
        """INSERT INTO groepberichten (groep_naam, van_id, tekst)
           VALUES ($1, $2, $3)
           RETURNING id, van_id, tekst, tijdstip""",
        groep_naam, gebruiker["id"], data.tekst.strip()
    )
    await conn.close()

    # AI controleert het bericht op taken
    ai_taak = await _verwerk_bericht_ai(data.tekst.strip(), gebruiker["naam"])

    return {
        "id": str(row["id"]),
        "van_id": str(row["van_id"]),
        "van_naam": gebruiker["naam"],
        "tekst": row["tekst"],
        "tijdstip": row["tijdstip"].isoformat(),
        "ai_taak": ai_taak,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ingestion-gateway"}
