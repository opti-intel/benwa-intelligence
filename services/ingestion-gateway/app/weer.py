"""Weer-integratie: automatische verschuifvoorstellen bij slecht weer.

Elke paar uur haalt het systeem de weersverwachting op (Open-Meteo, gratis,
geen sleutel nodig). Voor taken die als buitenwerk herkend worden en binnen
de komende dagen gepland staan, wordt gecontroleerd of het weer werkbaar is:

  - vorst        : minimumtemperatuur onder 0 °C
  - zware regen  : 8 mm neerslag of meer op een dag
  - storm        : windstoten vanaf 60 km/u

Is een geplande dag onwerkbaar, dan maakt het systeem een VOORSTEL aan om de
taak te verschuiven naar de eerste werkbare werkdag — precies zoals een
chatvoorstel, maar met bron 'weer'. Een beheerder bevestigt met één klik,
waarna de bestaande cascade alle afhankelijke taken automatisch meeschuift.

Locatie van de bouwplaats komt uit de environment variables WEER_LAT en
WEER_LON (standaard: regio Ravels/Tilburg).
"""

import asyncio
import json
import os
from datetime import date, timedelta

import asyncpg
import httpx
from fastapi import APIRouter, Depends

from .auth import vereist_admin
from .cascade import volgende_werkdag, plus_werkdagen, werkdagen_duur

router = APIRouter(tags=["weer"])

# Hoeveel dagen vooruit we kijken.
VOORUITBLIK_DAGEN = 7

# Grenswaarden voor "onwerkbaar buitenweer".
MAX_NEERSLAG_MM = 8.0
MAX_WINDSTOTEN_KMU = 60.0
MIN_TEMPERATUUR_C = 0.0

# Trefwoorden waarmee we buitenwerk herkennen in taaknaam/omschrijving.
BUITENWERK_WOORDEN = [
    "dak", "metsel", "gevel", "straat", "bestrat", "fundering", "graaf",
    "grond", "beton", "storten", "steiger", "kraan", "riool", "tuin",
    "schutting", "terras", "oprit", "buiten", "ruwbouw", "hijs", "sloop",
    "kozijn", "raam plaatsen", "voeg", "stukadoor buiten", "asfalt",
]


def is_buitenwerk(naam: str, beschrijving: str = "") -> bool:
    tekst = f"{naam} {beschrijving}".lower()
    return any(w in tekst for w in BUITENWERK_WOORDEN)


def onwerkbare_dagen(verwachting: list) -> dict:
    """Bepaal per datum of het weer onwerkbaar is en waarom.

    verwachting: lijst van dicts met keys datum (date), min_temp, neerslag_mm,
    windstoten_kmu. Geeft {date: reden} terug voor onwerkbare dagen.
    """
    slecht = {}
    for d in verwachting:
        redenen = []
        if d["min_temp"] is not None and d["min_temp"] < MIN_TEMPERATUUR_C:
            redenen.append(f"vorst ({d['min_temp']:.0f} °C)")
        if d["neerslag_mm"] is not None and d["neerslag_mm"] >= MAX_NEERSLAG_MM:
            redenen.append(f"zware regen ({d['neerslag_mm']:.0f} mm)")
        if d["windstoten_kmu"] is not None and d["windstoten_kmu"] >= MAX_WINDSTOTEN_KMU:
            redenen.append(f"storm (windstoten {d['windstoten_kmu']:.0f} km/u)")
        if redenen:
            slecht[d["datum"]] = " en ".join(redenen)
    return slecht


def bereken_verschuiving(startdatum: date, einddatum: date, slechte_dagen: dict) -> tuple:
    """Bepaal of een taak verschoven moet worden en waarheen.

    Geeft (nieuwe_start, nieuwe_eind, reden) terug, of (None, None, None)
    als de geplande periode werkbaar is. De nieuwe start is de eerste
    werkdag ná de laatste onwerkbare dag, met behoud van duur in werkdagen.
    """
    eind = einddatum or startdatum
    geraakt = [d for d in slechte_dagen if startdatum <= d <= eind]
    if not geraakt:
        return None, None, None

    laatste_slechte = max(d for d in slechte_dagen)
    nieuwe_start = volgende_werkdag(laatste_slechte + timedelta(days=1))
    duur = werkdagen_duur(startdatum, eind)
    nieuwe_eind = plus_werkdagen(nieuwe_start, duur - 1)
    eerste = min(geraakt)
    reden = f"{eerste.strftime('%d-%m')}: {slechte_dagen[eerste]}"
    return nieuwe_start, nieuwe_eind, reden


def rond_locatie(lat: float, lon: float) -> tuple:
    """Rond coördinaten af op ~1 km zodat adressen in dezelfde buurt één
    weersverwachting delen (scheelt onnodige API-aanroepen)."""
    return (round(lat, 2), round(lon, 2))


def standaard_locatie() -> tuple:
    return (
        float(os.environ.get("WEER_LAT", "51.37")),
        float(os.environ.get("WEER_LON", "4.99")),
    )


# ---------------------------------------------------------------------------
# Geocoding: bouwplaatsadres -> coördinaten (OpenStreetMap/Nominatim, gratis)
# met cache in de database zodat elk adres maar één keer wordt opgezocht.
# ---------------------------------------------------------------------------

async def geocodeer(conn: asyncpg.Connection, adres: str) -> tuple | None:
    adres = (adres or "").strip()
    if not adres:
        return None

    rij = await conn.fetchrow(
        "SELECT lat, lon, gevonden FROM adres_locaties WHERE adres = $1", adres.lower()
    )
    if rij is not None:
        return (rij["lat"], rij["lon"]) if rij["gevonden"] else None

    lat = lon = None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": adres, "format": "json", "limit": 1, "countrycodes": "nl,be"},
                headers={"User-Agent": "Opti-Intel weerbewaking (info@benwa-intelligence.com)"},
            )
            r.raise_for_status()
            resultaten = r.json()
            if resultaten:
                lat, lon = float(resultaten[0]["lat"]), float(resultaten[0]["lon"])
    except Exception as e:
        print(f"⚠️ Geocoding mislukt voor '{adres}': {e}", flush=True)
        return None  # niet cachen; volgende keer opnieuw proberen

    await conn.execute(
        """INSERT INTO adres_locaties (adres, lat, lon, gevonden)
           VALUES ($1, $2, $3, $4) ON CONFLICT (adres) DO NOTHING""",
        adres.lower(), lat, lon, lat is not None,
    )
    return (lat, lon) if lat is not None else None


# ---------------------------------------------------------------------------
# Weersverwachting ophalen (Open-Meteo, gratis)
# ---------------------------------------------------------------------------

async def haal_verwachting(lat: float, lon: float) -> list:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_min,precipitation_sum,wind_gusts_10m_max"
        f"&forecast_days={VOORUITBLIK_DAGEN}&timezone=Europe%2FAmsterdam"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
        d = r.json()["daily"]
    return [
        {
            "datum": date.fromisoformat(d["time"][i]),
            "min_temp": d["temperature_2m_min"][i],
            "neerslag_mm": d["precipitation_sum"][i],
            "windstoten_kmu": d["wind_gusts_10m_max"][i],
        }
        for i in range(len(d["time"]))
    ]


# ---------------------------------------------------------------------------
# De controle zelf
# ---------------------------------------------------------------------------

def _raw_db_url() -> str:
    from .mutaties import _raw_db_url as _url
    return _url()


async def controleer_weer_en_stel_voor() -> list:
    """Voer één weercontrole uit, per bouwplaatslocatie.

    Taken met een adres krijgen de verwachting van hun eigen bouwplaats;
    taken zonder (vindbaar) adres vallen terug op de standaardlocatie.
    Geeft de aangemaakte voorstellen terug.
    """
    conn = await asyncpg.connect(_raw_db_url())
    aangemaakt = []
    try:
        taken = await conn.fetch(
            """SELECT id, naam, beschrijving, adres, startdatum, einddatum, toegewezen_aan
               FROM tasks
               WHERE status = 'gepland' AND startdatum IS NOT NULL
                 AND startdatum <= $1""",
            date.today() + timedelta(days=VOORUITBLIK_DAGEN),
        )

        # Bepaal per taak de locatie (adres -> coördinaten, met cache) en
        # groepeer op afgeronde locatie zodat we per buurt één keer het weer ophalen.
        buiten_taken = [t for t in taken if is_buitenwerk(t["naam"], t["beschrijving"] or "")]
        taak_locatie: dict = {}
        for t in buiten_taken:
            coords = await geocodeer(conn, t["adres"] or "")
            taak_locatie[t["id"]] = rond_locatie(*coords) if coords else rond_locatie(*standaard_locatie())

        slecht_per_locatie: dict = {}
        for locatie in set(taak_locatie.values()):
            try:
                verwachting = await haal_verwachting(*locatie)
                slecht_per_locatie[locatie] = onwerkbare_dagen(verwachting)
            except Exception as e:
                print(f"⚠️ Weer ophalen mislukt voor {locatie}: {e}", flush=True)
                slecht_per_locatie[locatie] = {}

        for t in buiten_taken:
            slechte_dagen = slecht_per_locatie.get(taak_locatie[t["id"]], {})
            if not slechte_dagen:
                continue
            nieuwe_start, nieuwe_eind, reden = bereken_verschuiving(
                t["startdatum"], t["einddatum"], slechte_dagen
            )
            if nieuwe_start is None:
                continue
            if t["adres"]:
                reden = f"{t['adres']} — {reden}"

            # Niet dubbel voorstellen: sla over als er al een openstaand
            # weer-voorstel voor deze taak is.
            bestaand = await conn.fetchval(
                """SELECT COUNT(*) FROM voorgestelde_mutaties
                   WHERE bron = 'weer' AND status = 'pending'
                     AND (voorstel->>'doel_taak_id') = $1""",
                str(t["id"]),
            )
            if bestaand:
                continue

            samenvatting = (
                f"Onwerkbaar weer verwacht ({reden}). Voorstel: '{t['naam']}' "
                f"verschuiven naar {nieuwe_start.strftime('%d-%m')} t/m {nieuwe_eind.strftime('%d-%m')}."
            )
            voorstel = {
                "actie": "taak_wijzigen",
                "doel_taak_id": str(t["id"]),
                "naam": t["naam"],
                "beschrijving": None,
                "status": None,
                "startdatum": nieuwe_start.isoformat(),
                "einddatum": nieuwe_eind.isoformat(),
                "toegewezen_aan": None,
                "komt_na": [],
                "vertrouwen": 0.9,
                "samenvatting": samenvatting,
            }
            voorstel_id = await conn.fetchval(
                """INSERT INTO voorgestelde_mutaties
                       (bron, afzender_id, afzender, ruwe_tekst, voorstel)
                   VALUES ('weer', NULL, 'Opti-Intel weerbewaking', $1, $2::jsonb)
                   RETURNING id""",
                f"Weersverwachting: {reden}",
                json.dumps(voorstel),
            )

            # Meld de toegewezen vakman (in-app + push).
            if t["toegewezen_aan"]:
                from .push import stuur_push
                rows = await conn.fetch(
                    "SELECT id FROM gebruikers WHERE naam = $1 AND actief = TRUE",
                    t["toegewezen_aan"],
                )
                tekst = f"🌧 Weerwaarschuwing: {samenvatting}"
                for r in rows:
                    await conn.execute(
                        """INSERT INTO meldingen (gebruiker_id, tekst, taak_id, voorstel_id)
                           VALUES ($1, $2, $3, $4)""",
                        r["id"], tekst, t["id"], voorstel_id,
                    )
                    await stuur_push(conn, r["id"], tekst, str(t["id"]))

            aangemaakt.append({"taak": t["naam"], "samenvatting": samenvatting})
            print(f"🌧 Weer-voorstel aangemaakt: {samenvatting}", flush=True)
    finally:
        await conn.close()
    return aangemaakt


async def weerbewaking_loop():
    """Achtergrondtaak: elke 6 uur een weercontrole (eerste na 1 minuut)."""
    await asyncio.sleep(60)
    while True:
        try:
            await controleer_weer_en_stel_voor()
        except Exception as e:
            print(f"⚠️ Weercontrole mislukt: {e}", flush=True)
        await asyncio.sleep(6 * 3600)


# ---------------------------------------------------------------------------
# Endpoint: handmatig een controle draaien (handig voor demo's en testen)
# ---------------------------------------------------------------------------

@router.post("/weer/controleer")
async def controleer_nu(gebruiker: dict = Depends(vereist_admin)):
    """Draai de weercontrole direct (alleen admin)."""
    try:
        voorstellen = await controleer_weer_en_stel_voor()
    except Exception as e:
        return {"ok": False, "fout": f"Weersverwachting ophalen mislukt: {e}"}
    return {"ok": True, "voorstellen_aangemaakt": len(voorstellen), "details": voorstellen}
