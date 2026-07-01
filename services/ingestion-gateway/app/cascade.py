"""Automatisch doorschuiven (cascade) van afhankelijke taken.

Volgorde-relaties staan in de tabel 'taak_afhankelijkheden':
(voorganger_id, volger_id) betekent: de volger kan pas beginnen als de
voorganger klaar is.

Als een taak wordt verzet, controleren we alle volgers. Elke volger die nu
te vroeg start, schuift op naar de eerstvolgende werkdag na de (nieuwe)
einddatum van zijn voorganger, met behoud van zijn duur in werkdagen.
Dat kettingt recursief door naar de volgers van de volgers, enzovoort.
Weekends (zaterdag/zondag) tellen niet als werkdagen.

Taken worden alleen naar ACHTEREN geschoven, nooit automatisch naar voren:
als een taak eerder klaar is, blijft de rest gewoon staan (eerder beginnen
vergt meestal een menselijke beslissing over materiaal en mensen).
"""

from datetime import date, timedelta

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException

from .auth import get_huidige_gebruiker

router = APIRouter(tags=["afhankelijkheden"])


# ---------------------------------------------------------------------------
# Werkdag-rekenen (puur, geen database)
# ---------------------------------------------------------------------------

def volgende_werkdag(d: date) -> date:
    """Schuif door naar maandag als d in het weekend valt."""
    while d.weekday() >= 5:  # 5 = zaterdag, 6 = zondag
        d += timedelta(days=1)
    return d


def plus_werkdagen(d: date, n: int) -> date:
    """Tel n werkdagen op bij d (d zelf telt als werkdag 0)."""
    d = volgende_werkdag(d)
    while n > 0:
        d = volgende_werkdag(d + timedelta(days=1))
        n -= 1
    return d


def werkdagen_duur(start: date, eind: date) -> int:
    """Aantal werkdagen van start t/m eind (minimaal 1)."""
    if eind < start:
        return 1
    dagen = 0
    d = start
    while d <= eind:
        if d.weekday() < 5:
            dagen += 1
        d += timedelta(days=1)
    return max(dagen, 1)


# ---------------------------------------------------------------------------
# Cascade-berekening (puur, geen database — makkelijk te testen)
# ---------------------------------------------------------------------------

def bereken_cascade(taken: dict, relaties: list, start_id: str) -> list:
    """Bereken welke taken moeten opschuiven na een wijziging aan start_id.

    taken:    {taak_id: {"naam", "startdatum", "einddatum", "toegewezen_aan"}}
              (datums als date-objecten of None)
    relaties: lijst van (voorganger_id, volger_id) tuples
    start_id: de taak die net gewijzigd is

    Geeft een lijst verschuivingen terug, in volgorde van toepassen:
    [{"taak_id", "naam", "toegewezen_aan", "oude_start", "oude_eind",
      "nieuwe_start", "nieuwe_eind"}]
    De datums in `taken` worden bijgewerkt tijdens het rekenen zodat
    kettingen kloppen.
    """
    volgers_van: dict = {}
    voorgangers_van: dict = {}
    for voor, volg in relaties:
        volgers_van.setdefault(voor, []).append(volg)
        voorgangers_van.setdefault(volg, []).append(voor)

    verschoven = []
    wachtrij = [start_id]
    bezocht = set()

    while wachtrij:
        huidig = wachtrij.pop(0)
        if huidig in bezocht:
            continue  # cyclus-bescherming
        bezocht.add(huidig)

        for volger_id in volgers_van.get(huidig, []):
            volger = taken.get(volger_id)
            if not volger or not volger.get("startdatum"):
                continue  # zonder datums valt er niets te schuiven

            # Vroegst toegestane start: de werkdag na de laatste einddatum
            # van ALLE voorgangers van deze volger.
            eind_data = [
                taken[v]["einddatum"]
                for v in voorgangers_van.get(volger_id, [])
                if taken.get(v) and taken[v].get("einddatum")
            ]
            if not eind_data:
                continue
            min_start = volgende_werkdag(max(eind_data) + timedelta(days=1))

            if volger["startdatum"] >= min_start:
                continue  # genoeg ruimte, niets te doen

            oude_start = volger["startdatum"]
            oude_eind = volger.get("einddatum") or oude_start
            duur = werkdagen_duur(oude_start, oude_eind)
            nieuwe_start = min_start
            nieuwe_eind = plus_werkdagen(nieuwe_start, duur - 1)

            volger["startdatum"] = nieuwe_start
            volger["einddatum"] = nieuwe_eind
            verschoven.append({
                "taak_id": volger_id,
                "naam": volger.get("naam") or "taak",
                "toegewezen_aan": volger.get("toegewezen_aan") or "",
                "oude_start": oude_start,
                "oude_eind": oude_eind,
                "nieuwe_start": nieuwe_start,
                "nieuwe_eind": nieuwe_eind,
            })
            wachtrij.append(volger_id)

    return verschoven


# ---------------------------------------------------------------------------
# Database-laag
# ---------------------------------------------------------------------------

async def _laad_taken_en_relaties(conn: asyncpg.Connection) -> tuple:
    rows = await conn.fetch(
        "SELECT id, naam, startdatum, einddatum, toegewezen_aan FROM tasks"
    )
    taken = {
        str(r["id"]): {
            "naam": r["naam"],
            "startdatum": r["startdatum"],
            "einddatum": r["einddatum"],
            "toegewezen_aan": r["toegewezen_aan"],
        }
        for r in rows
    }
    rel_rows = await conn.fetch(
        "SELECT voorganger_id, volger_id FROM taak_afhankelijkheden"
    )
    relaties = [(str(r["voorganger_id"]), str(r["volger_id"])) for r in rel_rows]
    return taken, relaties


async def cascade_verschuif(conn: asyncpg.Connection, start_task_id: str) -> list:
    """Voer de cascade uit in de database. Geeft de verschuivingen terug."""
    taken, relaties = await _laad_taken_en_relaties(conn)
    if start_task_id not in taken:
        return []
    verschoven = bereken_cascade(taken, relaties, start_task_id)
    for v in verschoven:
        await conn.execute(
            """UPDATE tasks SET startdatum = $2, einddatum = $3, updated_at = NOW()
               WHERE id = $1""",
            v["taak_id"], v["nieuwe_start"], v["nieuwe_eind"],
        )
    return verschoven


async def meld_verschoven_taken(conn: asyncpg.Connection, verschoven: list,
                                afzender_id, bron_taak_naam: str,
                                voorstel_id: str | None = None) -> int:
    """Maak een melding voor elke gebruiker wiens taak automatisch is verschoven.
    Geeft het aantal aangemaakte meldingen terug."""
    aantal = 0
    for v in verschoven:
        if not v["toegewezen_aan"]:
            continue
        rows = await conn.fetch(
            "SELECT id FROM gebruikers WHERE naam = $1 AND actief = TRUE",
            v["toegewezen_aan"],
        )
        tekst = (
            f"⛓️ Automatisch verschoven omdat '{bron_taak_naam}' is gewijzigd: "
            f"{v['naam']} staat nu op {v['nieuwe_start']} t/m {v['nieuwe_eind']} "
            f"(was {v['oude_start']} t/m {v['oude_eind']})"
        )
        from .push import stuur_push
        for r in rows:
            if afzender_id is not None and str(r["id"]) == str(afzender_id):
                continue
            await conn.execute(
                """INSERT INTO meldingen (gebruiker_id, tekst, taak_id, voorstel_id)
                   VALUES ($1, $2, $3, $4)""",
                r["id"], tekst, v["taak_id"], voorstel_id,
            )
            await stuur_push(conn, r["id"], tekst, v["taak_id"])
            aantal += 1
    return aantal


def maakt_cyclus(relaties: list, voorganger_id: str, volger_id: str) -> bool:
    """True als de relatie voorganger→volger een kringetje zou maken
    (d.w.z. de voorganger is via bestaande relaties al bereikbaar vanaf de volger)."""
    volgers_van: dict = {}
    for voor, volg in relaties:
        volgers_van.setdefault(voor, []).append(volg)
    wachtrij, gezien = [volger_id], set()
    while wachtrij:
        n = wachtrij.pop(0)
        if n == voorganger_id:
            return True
        if n in gezien:
            continue
        gezien.add(n)
        wachtrij.extend(volgers_van.get(n, []))
    return False


async def verwerk_voorstel_relaties(conn: asyncpg.Connection, voorstel: dict,
                                    task_id: str, afzender_id,
                                    voorstel_id: str | None = None) -> tuple:
    """Centrale afhandeling na het toepassen van een voorstel:

    1. Leg ALTIJD de door de AI herkende volgorde-relaties (komt_na) vast.
    2. Voer de cascade uit (vanaf de voorgangers én vanaf de taak zelf).
    3. Meld iedereen wiens taak automatisch is verschoven.

    Geeft (verschoven_taken, aantal_meldingen) terug.
    """
    taken, relaties = await _laad_taken_en_relaties(conn)

    voorgangers = [
        v for v in (voorstel.get("komt_na") or [])
        if v and v != task_id and v in taken
    ]
    for vid in voorgangers:
        if maakt_cyclus(relaties, vid, task_id):
            print(f"⚠️ Volgorde {vid} → {task_id} overgeslagen (zou kringetje maken)", flush=True)
            continue
        await conn.execute(
            """INSERT INTO taak_afhankelijkheden (voorganger_id, volger_id)
               VALUES ($1, $2) ON CONFLICT DO NOTHING""",
            vid, task_id,
        )
        relaties.append((vid, task_id))

    # Cascade vanaf elke voorganger (schuift de taak zelf op als die te vroeg
    # staat) en vanaf de taak zelf (schuift háár volgers op bij datumwijziging).
    verschoven: dict = {}
    if voorgangers or voorstel.get("startdatum") or voorstel.get("einddatum"):
        for start in voorgangers + [task_id]:
            for v in await cascade_verschuif(conn, start):
                verschoven[v["taak_id"]] = v

    verschoven_lijst = list(verschoven.values())
    bron_naam = (taken.get(task_id) or {}).get("naam") or voorstel.get("naam") or "taak"
    aantal = await meld_verschoven_taken(conn, verschoven_lijst, afzender_id, bron_naam, voorstel_id)
    return verschoven_lijst, aantal


# ---------------------------------------------------------------------------
# Endpoints voor volgorde-relaties
# ---------------------------------------------------------------------------

def _raw_db_url() -> str:
    from .mutaties import _raw_db_url as _url
    return _url()


@router.get("/taken/{taak_id}/afhankelijkheden")
async def lijst_afhankelijkheden(taak_id: str, gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Voorgangers (taken die eerst klaar moeten) en volgers van een taak."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        voorgangers = await conn.fetch(
            """SELECT t.id, t.naam, t.startdatum, t.einddatum FROM taak_afhankelijkheden a
               JOIN tasks t ON t.id = a.voorganger_id WHERE a.volger_id = $1""",
            taak_id,
        )
        volgers = await conn.fetch(
            """SELECT t.id, t.naam, t.startdatum, t.einddatum FROM taak_afhankelijkheden a
               JOIN tasks t ON t.id = a.volger_id WHERE a.voorganger_id = $1""",
            taak_id,
        )
    finally:
        await conn.close()

    def _fmt(rows):
        return [
            {
                "id": str(r["id"]),
                "naam": r["naam"],
                "startdatum": r["startdatum"].isoformat() if r["startdatum"] else None,
                "einddatum": r["einddatum"].isoformat() if r["einddatum"] else None,
            }
            for r in rows
        ]

    return {"voorgangers": _fmt(voorgangers), "volgers": _fmt(volgers)}


@router.post("/taken/{taak_id}/afhankelijkheden")
async def voeg_afhankelijkheid_toe(taak_id: str,
                                   voorganger_id: str = Body(..., embed=True),
                                   gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Leg vast dat taak {taak_id} pas kan beginnen als {voorganger_id} klaar is.
    Schuift de volger direct op als die nu te vroeg gepland staat."""
    if taak_id == voorganger_id:
        raise HTTPException(status_code=422, detail="Een taak kan niet van zichzelf afhangen")

    conn = await asyncpg.connect(_raw_db_url())
    try:
        taken, relaties = await _laad_taken_en_relaties(conn)
        if taak_id not in taken or voorganger_id not in taken:
            raise HTTPException(status_code=404, detail="Taak niet gevonden")

        # Cyclus-check: is taak_id (via bestaande relaties) al een
        # voorganger van voorganger_id? Dan zou dit een kringetje maken.
        volgers_van: dict = {}
        for voor, volg in relaties:
            volgers_van.setdefault(voor, []).append(volg)
        wachtrij, gezien = [taak_id], set()
        while wachtrij:
            n = wachtrij.pop(0)
            if n == voorganger_id:
                raise HTTPException(
                    status_code=422,
                    detail="Deze volgorde zou een kringetje maken (A na B na A)",
                )
            if n in gezien:
                continue
            gezien.add(n)
            wachtrij.extend(volgers_van.get(n, []))

        await conn.execute(
            """INSERT INTO taak_afhankelijkheden (voorganger_id, volger_id)
               VALUES ($1, $2) ON CONFLICT DO NOTHING""",
            voorganger_id, taak_id,
        )

        # Direct conflicten oplossen + betrokkenen melden.
        verschoven = await cascade_verschuif(conn, voorganger_id)
        bron_naam = taken[voorganger_id]["naam"]
        await meld_verschoven_taken(conn, verschoven, gebruiker["id"], bron_naam)
    finally:
        await conn.close()

    return {
        "ok": True,
        "automatisch_verschoven": [
            {
                "taak_id": v["taak_id"],
                "naam": v["naam"],
                "nieuwe_start": v["nieuwe_start"].isoformat(),
                "nieuwe_eind": v["nieuwe_eind"].isoformat(),
            }
            for v in verschoven
        ],
    }


@router.delete("/taken/{taak_id}/afhankelijkheden/{voorganger_id}")
async def verwijder_afhankelijkheid(taak_id: str, voorganger_id: str,
                                    gebruiker: dict = Depends(get_huidige_gebruiker)):
    """Verwijder een volgorde-relatie. Bestaande datums blijven staan."""
    conn = await asyncpg.connect(_raw_db_url())
    try:
        resultaat = await conn.execute(
            "DELETE FROM taak_afhankelijkheden WHERE voorganger_id = $1 AND volger_id = $2",
            voorganger_id, taak_id,
        )
    finally:
        await conn.close()
    if int(resultaat.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="Afhankelijkheid niet gevonden")
    return {"ok": True}
