"""Claude-gebaseerde interpretatie van bouwchat-berichten.

Vervangt de regel-gebaseerde nl_parser voor de taakdetectie: een chatbericht
wordt door Claude (Anthropic API) gelezen en omgezet naar een VOORGESTELDE
planningsmutatie. Deze module past zelf niets in de planning aan — ze geeft
enkel een gestructureerd voorstel terug. Het opslaan als 'pending' en het
later toepassen gebeurt elders (main.py / mutaties.py).
"""

import json
import os
from datetime import date

# Welk Claude-model de berichten interpreteert.
MODEL = "claude-sonnet-4-6"

# Gestructureerd JSON-schema dat Claude MOET volgen. Dit garandeert dat we
# altijd een parseerbaar voorstel terugkrijgen met vaste velden.
VOORSTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "actie": {
            "type": "string",
            "enum": ["taak_aanmaken", "taak_wijzigen", "geen"],
            "description": (
                "taak_aanmaken als het bericht een nieuwe taak beschrijft; "
                "taak_wijzigen als het een bestaande taak aanpast "
                "(datum, status of toewijzing); geen als er geen "
                "planningsactie in het bericht zit."
            ),
        },
        "doel_taak_id": {
            "type": ["string", "null"],
            "description": (
                "Bij taak_wijzigen: de id van de bestaande taak uit de "
                "meegegeven lijst die wordt aangepast. Anders null."
            ),
        },
        "naam": {
            "type": ["string", "null"],
            "description": "Korte naam van de taak (bv. 'Gevel metselen blok B').",
        },
        "beschrijving": {
            "type": ["string", "null"],
            "description": "Eventuele extra details uit het bericht. Anders null.",
        },
        "status": {
            "type": ["string", "null"],
            "description": "Status van de taak indien vermeld ('gepland', 'bezig' of 'klaar'), anders null.",
        },
        "startdatum": {
            "type": ["string", "null"],
            "description": "Startdatum als YYYY-MM-DD, of null als niet vermeld.",
        },
        "einddatum": {
            "type": ["string", "null"],
            "description": "Einddatum/deadline als YYYY-MM-DD, of null als niet vermeld.",
        },
        "toegewezen_aan": {
            "type": ["string", "null"],
            "description": "Naam van de persoon aan wie de taak toegewezen is, of null.",
        },
        "adres": {
            "type": ["string", "null"],
            "description": (
                "Adres of locatie van de bouwplaats als die in het bericht "
                "staat (bv. 'Maurice Ravelstraat 5, Tilburg' of 'blok B "
                "Ravels'). Wordt gebruikt om het weer op die plek te bewaken. "
                "Null als er geen locatie genoemd wordt."
            ),
        },
        "komt_na": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Ids van bestaande taken (uit de meegegeven lijst) die klaar "
                "moeten zijn vóórdat deze taak kan beginnen. Vul dit ALTIJD in "
                "wanneer het bericht een volgorde noemt of impliceert: "
                "'na het tegelen', 'zodra X klaar is', 'eerst A dan B', "
                "'als de vloer droog is', 'de voeger komt na de tegelzetter'. "
                "Verwijst het bericht naar een vakman of bedrijf ('na de "
                "elektricien'), zoek dan de taak van die persoon in de lijst. "
                "Lege lijst als er geen volgorde genoemd wordt."
            ),
        },
        "vertrouwen": {
            "type": "number",
            "description": "Hoe zeker je bent (0.0 tot 1.0) dat dit een correcte interpretatie is.",
        },
        "samenvatting": {
            "type": "string",
            "description": (
                "Eén zin in het Nederlands die aan de uitvoerder uitlegt wat het "
                "voorstel inhoudt, zodat die het kan bevestigen of afwijzen."
            ),
        },
    },
    "required": [
        "actie",
        "doel_taak_id",
        "naam",
        "beschrijving",
        "status",
        "startdatum",
        "einddatum",
        "toegewezen_aan",
        "adres",
        "komt_na",
        "vertrouwen",
        "samenvatting",
    ],
    "additionalProperties": False,
}


def _systeem_prompt(vandaag: str) -> str:
    return (
        "Je bent een planningsassistent voor een bouwbedrijf. Je leest korte "
        "chatberichten van bouwarbeiders en zet ze om naar een voorgestelde "
        "planningsmutatie.\n\n"
        f"De datum van vandaag is {vandaag}. Reken relatieve datums "
        "('morgen', 'volgende week dinsdag', 'overmorgen') om naar een "
        "concrete YYYY-MM-DD datum op basis van die datum.\n\n"
        "Regels:\n"
        "- Beschrijft het bericht een nieuwe taak (wie/wat/waar/wanneer)? Kies "
        "actie 'taak_aanmaken'.\n"
        "- Past het bericht een bestaande taak aan (uit de meegegeven lijst)? "
        "Kies 'taak_wijzigen' en zet doel_taak_id op de juiste id.\n"
        "- Is het gewoon een mededeling, vraag of smalltalk zonder "
        "planningsactie? Kies 'geen' en laat de taakvelden null.\n"
        "- VOLGORDE: noemt of impliceert het bericht dat werk na ander werk "
        "komt ('na het tegelen', 'zodra de elektricien klaar is', 'eerst A "
        "dan B', 'als de vloer droog is')? Zet dan ALTIJD de ids van die "
        "voorgaande taken in komt_na — zowel bij taak_aanmaken als "
        "taak_wijzigen. Deze koppeling zorgt dat de planning automatisch "
        "meeschuift bij uitloop, dus sla haar nooit over. Benoem de volgorde "
        "ook kort in de samenvatting.\n"
        "- Verzin geen gegevens die niet in het bericht staan; laat onbekende "
        "velden op null.\n"
        "- Wees voorzichtig met 'vertrouwen': zet het laag als het bericht vaag is."
    )


def _gebruiker_prompt(tekst: str, afzender: str, bestaande_taken: list[dict]) -> str:
    taken_context = "Er zijn nog geen bestaande taken bekend."
    if bestaande_taken:
        regels = "\n".join(
            f"- id={t['id']} | {t['naam']} [{t.get('status', '')}]"
            + (f" | {t['startdatum']} t/m {t.get('einddatum') or t['startdatum']}" if t.get("startdatum") else "")
            + (f" → {t['toegewezen_aan']}" if t.get("toegewezen_aan") else "")
            for t in bestaande_taken
        )
        taken_context = "Bestaande taken (voor eventuele wijzigingen):\n" + regels

    return (
        f"Afzender: {afzender}\n"
        f"Bericht: \"{tekst}\"\n\n"
        f"{taken_context}\n\n"
        "Geef het voorstel terug volgens het schema."
    )


async def interpreteer_bericht(
    tekst: str,
    afzender: str,
    bestaande_taken: list[dict] | None = None,
) -> dict | None:
    """Laat Claude een chatbericht interpreteren.

    Geeft een gestructureerd voorstel-dict terug (volgens VOORSTEL_SCHEMA), of
    None wanneer er geen API-key is, een fout optreedt, of het bericht geen
    planningsactie bevat (actie == 'geen').
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ Geen ANTHROPIC_API_KEY ingesteld; berichtinterpretatie overgeslagen.", flush=True)
        return None

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)
        vandaag = date.today().isoformat()
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_systeem_prompt(vandaag),
            messages=[
                {
                    "role": "user",
                    "content": _gebruiker_prompt(tekst, afzender, bestaande_taken or []),
                }
            ],
            output_config={"format": {"type": "json_schema", "schema": VOORSTEL_SCHEMA}},
        )
    except Exception as e:
        print(f"⚠️ Claude-interpretatie mislukt: {e}", flush=True)
        return None

    # Het schema garandeert dat het eerste tekstblok geldige JSON is.
    tekst_blok = next((b.text for b in response.content if b.type == "text"), None)
    if not tekst_blok:
        return None
    try:
        voorstel = json.loads(tekst_blok)
    except json.JSONDecodeError as e:
        print(f"⚠️ Kon Claude-antwoord niet als JSON lezen: {e}", flush=True)
        return None

    if voorstel.get("actie") == "geen":
        return None
    return voorstel
