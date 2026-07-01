"""Web-push meldingen naar telefoons en browsers.

Gebruikers zetten meldingen aan in het dashboard; de browser maakt dan een
push-abonnement (endpoint + sleutels) aan dat hier wordt opgeslagen. Bij elke
nieuwe melding sturen we een web-push naar alle abonnementen van die
gebruiker, zodat de melding ook als notificatie op de telefoon verschijnt.

Vereist VAPID-sleutels in de environment (zie .env):
  VAPID_PRIVATE_KEY — privésleutel (base64url)
  VAPID_PUBLIC_KEY  — publieke sleutel (base64url), ook gebruikt door de browser
  VAPID_SUBJECT     — contactadres, bv. mailto:beheer@bedrijf.nl

Zonder sleutels blijven de in-app meldingen gewoon werken; alleen de push
wordt dan overgeslagen.
"""

import asyncio
import json
import os

import asyncpg
from fastapi import APIRouter, Body, Depends

from .auth import get_huidige_gebruiker

router = APIRouter(tags=["push"])

CREATE_PUSH_ABONNEMENTEN_TABLE = """
    CREATE TABLE IF NOT EXISTS push_abonnementen (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        gebruiker_id UUID NOT NULL,
        endpoint TEXT NOT NULL UNIQUE,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        aangemaakt_op TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
"""


def _raw_db_url() -> str:
    from .mutaties import _raw_db_url as _url
    return _url()


def _vapid_config() -> tuple:
    """(privésleutel, claims) of (None, None) als push niet geconfigureerd is."""
    priv = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    subject = os.environ.get("VAPID_SUBJECT", "").strip() or "mailto:beheer@example.com"
    if not priv:
        return None, None
    return priv, {"sub": subject}


def maak_push_payload(tekst: str, taak_id: str | None = None) -> str:
    """Bouw de JSON die de service worker in de browser ontvangt."""
    return json.dumps({
        "titel": "Benwa Intelligence",
        "tekst": tekst,
        "taak_id": taak_id,
        "url": "/planning",
    })


def _stuur_sync(abonnement: dict, payload: str, priv: str, claims: dict) -> bool:
    """Verstuur één web-push (blokkerend). True = abonnement is dood, opruimen."""
    from pywebpush import webpush, WebPushException
    try:
        webpush(
            subscription_info={
                "endpoint": abonnement["endpoint"],
                "keys": {"p256dh": abonnement["p256dh"], "auth": abonnement["auth"]},
            },
            data=payload,
            vapid_private_key=priv,
            vapid_claims=dict(claims),  # pywebpush muteert de claims
            ttl=3600,
        )
        return False
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code in (404, 410):
            return True  # abonnement bestaat niet meer (app verwijderd e.d.)
        print(f"⚠️ Push versturen mislukt ({code}): {e}", flush=True)
        return False
    except Exception as e:
        print(f"⚠️ Push versturen mislukt: {e}", flush=True)
        return False


async def stuur_push(conn: asyncpg.Connection, gebruiker_id, tekst: str,
                     taak_id: str | None = None) -> int:
    """Stuur een push naar alle abonnementen van een gebruiker.
    Faalt stil (meldingen in de app blijven leidend). Geeft aantal verstuurd terug."""
    priv, claims = _vapid_config()
    if priv is None:
        return 0
    try:
        rows = await conn.fetch(
            "SELECT id, endpoint, p256dh, auth FROM push_abonnementen WHERE gebruiker_id = $1",
            gebruiker_id,
        )
    except Exception:
        return 0  # tabel bestaat nog niet o.i.d. — nooit de melding zelf blokkeren

    payload = maak_push_payload(tekst, taak_id)
    verstuurd = 0
    for r in rows:
        dood = await asyncio.to_thread(_stuur_sync, dict(r), payload, priv, claims)
        if dood:
            await conn.execute("DELETE FROM push_abonnementen WHERE id = $1", r["id"])
        else:
            verstuurd += 1
    return verstuurd


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/push/publieke-sleutel")
async def publieke_sleutel():
    """De VAPID publieke sleutel die de browser nodig heeft om te abonneren."""
    return {"publieke_sleutel": os.environ.get("VAPID_PUBLIC_KEY", "")}


@router.post("/push/abonneer")
async def abonneer(endpoint: str = Body(...),
                   keys: dict = Body(...),
                   gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Sla een push-abonnement van de browser op voor de ingelogde gebruiker."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        await conn.execute(
            """INSERT INTO push_abonnementen (gebruiker_id, endpoint, p256dh, auth)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (endpoint) DO UPDATE
               SET gebruiker_id = $1, p256dh = $3, auth = $4""",
            gebruiker["id"], endpoint, keys.get("p256dh", ""), keys.get("auth", ""),
        )
    finally:
        await conn.close()
    return {"ok": True}


@router.post("/push/afmelden")
async def afmelden(endpoint: str = Body(..., embed=True),
                   gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Verwijder een push-abonnement (meldingen op dit apparaat uitzetten)."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        await conn.execute(
            "DELETE FROM push_abonnementen WHERE endpoint = $1 AND gebruiker_id = $2",
            endpoint, gebruiker["id"],
        )
    finally:
        await conn.close()
    return {"ok": True}
