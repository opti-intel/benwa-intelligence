"""
Rule-based Dutch NLP parser for construction chat messages.

Extracts: what (task), who (person), when (date/time), where (location), task_type.
No external APIs or ML models needed — pure pattern matching on Dutch text.

Supports multi-turn conversations: when info is missing (date, person), returns
a partial result with follow-up questions. The frontend sends the partial context
back with the next message so we can merge.
"""

import re
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

DAGEN = {
    "maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3,
    "vrijdag": 4, "zaterdag": 5, "zondag": 6,
}

MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _next_weekday(day_index: int, today: date | None = None) -> date:
    """Return the next occurrence of the given weekday (0=Monday)."""
    today = today or date.today()
    days_ahead = day_index - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def parse_datum(text: str) -> str | None:
    """Try to extract a date from Dutch text. Returns YYYY-MM-DD or None."""
    lower = text.lower()
    today = date.today()

    if re.search(r"\bmorgen\b", lower):
        return (today + timedelta(days=1)).isoformat()

    if re.search(r"\bovermorgen\b", lower):
        return (today + timedelta(days=2)).isoformat()

    if re.search(r"\bvandaag\b", lower):
        return today.isoformat()

    m = re.search(r"volgende\s+week\s+(\w+)", lower)
    if m:
        dag = DAGEN.get(m.group(1))
        if dag is not None:
            nxt = _next_weekday(dag, today)
            if nxt <= today + timedelta(days=7):
                nxt += timedelta(days=7)
            return nxt.isoformat()

    m = re.search(r"deze\s+week\s+(\w+)", lower)
    if m:
        dag = DAGEN.get(m.group(1))
        if dag is not None:
            return _next_weekday(dag, today).isoformat()

    for dag_naam, dag_idx in DAGEN.items():
        if re.search(rf"\b{dag_naam}\b", lower):
            return _next_weekday(dag_idx, today).isoformat()

    m = re.search(r"(\d{1,2})\s+(" + "|".join(MAANDEN.keys()) + r")(?:\s+(\d{4}))?", lower)
    if m:
        day = int(m.group(1))
        month = MAANDEN[m.group(2)]
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass

    m = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", lower)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            return date(year, b, a).isoformat()
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------

def parse_tijd(text: str) -> str | None:
    """Extract a time like '9u', '14:30', '9 uur', 'om 10h'. Returns HH:MM or None."""
    lower = text.lower()

    m = re.search(r"\b(\d{1,2})\s*[uh](?:\s*(\d{2}))?\b", lower)
    if m:
        h = int(m.group(1))
        mins = int(m.group(2)) if m.group(2) else 0
        if 0 <= h <= 23 and 0 <= mins <= 59:
            return f"{h:02d}:{mins:02d}"

    m = re.search(r"\b(\d{1,2}):(\d{2})\b", lower)
    if m:
        h, mins = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mins <= 59:
            return f"{h:02d}:{mins:02d}"

    m = re.search(r"\bom\s+(\d{1,2})\s+uur\b", lower)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    return None


# ---------------------------------------------------------------------------
# Task type detection (construction domain)
# ---------------------------------------------------------------------------

TAAK_TYPES: dict[str, list[str]] = {
    "sanitair": ["sanitair", "wc", "toilet", "badkamer", "douche", "wastafel", "kraan"],
    "elektriciteit": ["elektr", "bedrading", "bekabeling", "groepenkast", "stopcontact", "verlichting", "lamp"],
    "loodgieterij": ["loodgieter", "waterleiding", "riolering", "afvoer", "leiding"],
    "metselwerk": ["metsel", "muren", "bakstenen", "voegen"],
    "dakwerken": ["dak", "dakpan", "dakspant", "dakbedekking", "goot", "schoorsteen"],
    "schilderwerk": ["schilder", "verf", "verven", "lakken", "primer"],
    "stucwerk": ["stuc", "pleister", "bepleisteren"],
    "vloerwerk": ["vloer", "tegels", "laminaat", "parket", "chape"],
    "funderings": ["fundering", "graven", "beton storten", "heipalen"],
    "timmerwerk": ["timmer", "hout", "kozijn", "deur", "raam", "trap"],
    "isolatie": ["isolat", "isoleren", "piepschuim", "glaswol", "PUR"],
    "HVAC": ["verwarming", "airco", "ventilatie", "cv-ketel", "radiator"],
    "grondwerk": ["grondwerk", "graafwerk", "graven", "egaliseren", "ophogen"],
    "afwerking": ["afwerk", "kitwerk", "plinten", "afdichten"],
    "levering": ["lever", "bestel", "materiaal", "transport", "ophalen", "aanvoer"],
    "inspectie": ["inspectie", "keuring", "controle", "oplevering"],
}


def detect_taak_type(text: str) -> str:
    lower = text.lower()
    for taak_type, keywords in TAAK_TYPES.items():
        for kw in keywords:
            if kw in lower:
                return taak_type
    return ""


# ---------------------------------------------------------------------------
# Location extraction
# ---------------------------------------------------------------------------

LOCATIE_PATTERNS = [
    r"(?:in|op|bij|aan)\s+(blok\s+\w+)",
    r"(?:in|op|bij)\s+(?:de|het)\s+((?:\d+e\s+)?verdieping)",
    r"(?:in|op|bij)\s+(?:de|het)\s+([\w\s]{2,25}?)(?:\s+(?:van|op|om|voor|moet|gaat|kan|wordt|is|het|de|\.|,|$))",
    r"\b((?:verdieping|vleugel|zone|sectie|gebouw|hal|kamer|ruimte)\s+\w+)",
    r"\b(keuken|badkamer|garage|kelder|zolder|woonkamer|slaapkamer|berging|tuin|terras|balkon|oprit)\b",
]


def extract_locatie(text: str) -> str:
    for pattern in LOCATIE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().rstrip(".,;")
            if len(loc) > 40:
                continue
            return loc[0].upper() + loc[1:] if loc else ""
    return ""


# ---------------------------------------------------------------------------
# Person / "who" extraction
# ---------------------------------------------------------------------------

PERSOON_PATTERNS = [
    (r"\b(ik)\s+(?:kom|ga|doe|begin|start|plaats|installeer|leg|maak|breng)", True),
    (r"^([A-Z][a-z]+(?:\s+(?:de|van|den|der|el|al))?(?:\s+[A-Z][a-z]+)?)\s+(?:komt|gaat|doet|begint|plaatst|installeert|legt|maakt|brengt|moet)", False),
    (r"\bdoor\s+([A-Z][a-z]+(?:\s+(?:de|van|den|der|el|al))?(?:\s+[A-Z][a-z]+)?)\b", False),
    (r"\bvoor\s+([A-Z][a-z]+(?:\s+(?:de|van|den|der|el|al))?(?:\s+[A-Z][a-z]+)?)\b", False),
    (r"\b(?:de|een)\s+(loodgieter|elektricien|metselaar|schilder|dakdekker|timmerman|monteur|aannemer|voorman|kraanmachinist|stukadoor)\b", True),
]

ROLE_DISPLAY = {
    "loodgieter": "De loodgieter", "elektricien": "De elektricien",
    "metselaar": "De metselaar", "schilder": "De schilder",
    "dakdekker": "De dakdekker", "timmerman": "De timmerman",
    "monteur": "De monteur", "aannemer": "De aannemer",
    "voorman": "De voorman", "kraanmachinist": "De kraanmachinist",
    "stukadoor": "De stukadoor",
}


def extract_persoon(text: str) -> str:
    for pattern, case_insensitive in PERSOON_PATTERNS:
        flags = re.IGNORECASE if case_insensitive else 0
        m = re.search(pattern, text, flags)
        if m:
            person = m.group(1).strip()
            display = ROLE_DISPLAY.get(person.lower())
            if display:
                return display
            return person
    return ""


# ---------------------------------------------------------------------------
# Activity / "what" extraction
# ---------------------------------------------------------------------------

ACTIVITEIT_VERBS = [
    "plaatsen", "installeren", "leggen", "storten", "metsen", "metselen",
    "schilderen", "verven", "stucen", "stuken", "bepleisteren",
    "graven", "boren", "zagen", "monteren", "aansluiten",
    "repareren", "herstellen", "vervangen", "demonteren",
    "isoleren", "bekabelen", "bedraden", "betegelen",
    "timmeren", "lassen", "solderen", "lijmen", "kitten",
    "leveren", "bestellen", "ophalen", "transporteren",
    "inspecteren", "keuren", "controleren", "opleveren",
    "afwerken", "schoonmaken", "opruimen",
    "plaatst", "installeert", "legt", "stort", "metselt",
    "schildert", "verft", "stuct", "bepleistert",
    "graaft", "boort", "zaagt", "monteert", "aansluit",
    "repareert", "herstelt", "vervangt", "demonteert",
    "isoleert", "bekabelt", "betegelt",
    "timmert", "last", "soldeert", "lijmt", "kit",
    "levert", "bestelt", "haalt op", "transporteert",
    "inspecteert", "keurt", "controleert", "oplevert",
    "afwerkt", "schoonmaakt", "opruimt",
    "doen", "maken", "komen", "beginnen", "starten",
]


def extract_activiteit(text: str) -> str:
    """Extract the core activity description by stripping person/date/time/filler.

    Dutch word order puts the verb at the end: "de badkamer tegels leggen".
    So instead of looking after the verb, we strip everything that ISN'T the task.
    """
    result = text

    # 1. Strip person prefix: "ik kom", "Jan de Vries komt", "Pieter Bakker gaat",
    #    "de loodgieter moet"
    result = re.sub(
        r"^(?:ik\s+(?:kom|ga|moet|wil|zal)\s*"
        r"|[A-Z][a-z]+(?:\s+(?:de|van|den|der|el|al))?(?:\s+[A-Z][a-z]+)?\s+(?:komt|gaat|moet|wil|zal)\s*"
        r"|de\s+\w+\s+(?:komt|gaat|moet|wil|zal)\s*)",
        "", result, flags=re.IGNORECASE
    ).strip()

    # 2. Strip date expressions (weekdays, "morgen", "volgende week X", "26 februari", etc.)
    result = re.sub(r"\b(?:volgende|deze)\s+week\s+\w+", "", result, flags=re.IGNORECASE)
    for dag in DAGEN:
        result = re.sub(rf"\b(?:op\s+)?{dag}\b", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\b(?:morgen|overmorgen|vandaag)\b", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\b\d{1,2}\s+(?:" + "|".join(MAANDEN.keys()) + r")(?:\s+\d{4})?\b", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\b\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?\b", "", result)

    # 3. Strip time expressions: "om 9u", "om 14u30", "om 9:30", "om 10 uur"
    result = re.sub(r"\bom\s+\d{1,2}\s*[uh](?:\s*\d{2})?\b", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\bom\s+\d{1,2}:\d{2}\b", "", result)
    result = re.sub(r"\bom\s+\d{1,2}\s+uur\b", "", result, flags=re.IGNORECASE)

    # 4. Strip orphaned prepositions left after date/time removal
    result = re.sub(r"\s+(?:op|om|in|voor|na|vanaf|tot)\s*$", "", result, flags=re.IGNORECASE)
    result = re.sub(r"^[\s,]*(?:op|om)\s+", "", result, flags=re.IGNORECASE)

    # 5. Strip remaining filler words at the start
    result = re.sub(r"^[\s,]*\b(?:even|nog|eens|dan|er|naar|toe|om\s+te)\b", "", result, flags=re.IGNORECASE)

    # 6. Clean up whitespace, punctuation
    result = re.sub(r"\s+", " ", result).strip().strip(".,;!?")

    # 7. Strip leading articles if they're orphaned: "de ", "het ", "een "
    result = re.sub(r"^(?:de|het|een)\s+(?=\S)", "", result, flags=re.IGNORECASE).strip()

    if len(result) > 3:
        return result[0].upper() + result[1:]

    # Fallback: return original stripped of obvious noise
    return text.strip()


# ---------------------------------------------------------------------------
# Duration estimation per task type (in days)
# ---------------------------------------------------------------------------

DUUR_SCHATTING: dict[str, int] = {
    "sanitair": 2, "elektriciteit": 3, "loodgieterij": 2,
    "metselwerk": 5, "dakwerken": 5, "schilderwerk": 3,
    "stucwerk": 3, "vloerwerk": 3, "funderings": 7,
    "timmerwerk": 4, "isolatie": 2, "HVAC": 3,
    "grondwerk": 4, "afwerking": 2, "levering": 1, "inspectie": 1,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_greeting_or_question(lower: str) -> bool:
    greetings = ["hallo", "hey", "hoi", "goedemorgen", "goedemiddag", "goedenavond",
                 "dag", "hi", "yo", "bedankt", "dankjewel", "dankje", "thanks"]
    if any(lower.startswith(g) for g in greetings) and len(lower) < 30:
        return True
    if lower.endswith("?"):
        return True
    if lower.startswith(("wat ", "wie ", "waar ", "wanneer ", "hoe ", "welke ", "hoeveel ", "kun ", "kan ")):
        return True
    return False


def _generate_greeting_response(lower: str) -> str:
    if lower.endswith("?"):
        if "wanneer" in lower or "planning" in lower:
            return "Ga naar het Planning-tabblad voor een overzicht van alle geplande taken. Of vertel me wat je wilt inplannen!"
        if "hoeveel" in lower or "taken" in lower:
            return "Bekijk het Taken-tabblad voor een overzicht. Je kunt me ook vragen om nieuwe taken aan te maken!"
        return "Goede vraag! Ik ben gespecialiseerd in het aanmaken van taken. Vertel me wat er moet gebeuren op de werf en ik maak er een taak van."
    if any(w in lower for w in ["bedankt", "dankje", "dankjewel", "thanks"]):
        return "Graag gedaan! Laat me weten als je nog iets wilt inplannen."
    return "Hoi! Vertel me wat er moet gebeuren op de bouwplaats en ik maak er meteen een taak van. Bijvoorbeeld: \"Donderdag om 9u sanitair plaatsen in blok A\"."


TAAK_TYPE_LABELS: dict[str, str] = {
    "sanitair": "Sanitair", "elektriciteit": "Elektriciteit",
    "loodgieterij": "Loodgieterij", "metselwerk": "Metselwerk",
    "dakwerken": "Dakwerken", "schilderwerk": "Schilderwerk",
    "stucwerk": "Stucwerk", "vloerwerk": "Vloerwerk",
    "funderings": "Funderingswerk", "timmerwerk": "Timmerwerk",
    "isolatie": "Isolatie", "HVAC": "HVAC",
    "grondwerk": "Grondwerk", "afwerking": "Afwerking",
    "levering": "Levering", "inspectie": "Inspectie",
}


def _build_task_name(activiteit: str, taak_type: str, locatie: str) -> str:
    """Build a short, descriptive task name.

    The activiteit already contains the full description (e.g. "Badkamer tegels leggen")
    since extract_activiteit strips person/date/time. We only fall back to task_type
    if the activiteit is too short/generic.
    """
    # If activiteit is rich enough, use it directly
    if len(activiteit) > 8:
        name = activiteit
    elif taak_type:
        # Very short activiteit — prefix with type label
        label = TAAK_TYPE_LABELS.get(taak_type, taak_type.capitalize())
        name = f"{label}: {activiteit}" if activiteit else label
    else:
        name = activiteit or "Taak"

    # Append location only if not already part of the name
    if locatie and locatie.lower() not in name.lower() and len(name) < 45:
        name = f"{name} — {locatie}"

    # Cap at reasonable length
    if len(name) > 60:
        name = name[:57] + "..."

    return name


def _format_date_nl(iso: str) -> str:
    """Format YYYY-MM-DD to a readable Dutch string."""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    dag_namen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    maand_namen = ["", "januari", "februari", "maart", "april", "mei", "juni",
                   "juli", "augustus", "september", "oktober", "november", "december"]
    return f"{dag_namen[d.weekday()]} {d.day} {maand_namen[d.month]}"


def _build_confirmation(taak: dict, tijd: str | None, persoon: str) -> str:
    """Build a WhatsApp-style Dutch confirmation message.

    Format: ✅ Taak aangemaakt: Tegels leggen in de badkamer op zaterdag 1 maart om 9:00 — uitgevoerd door Jan.
    """
    parts = [f"✅ Taak aangemaakt: **{taak['naam']}**"]

    if taak.get("locatie"):
        parts.append(f"in {taak['locatie']}")

    date_parts = []
    if taak.get("startdatum"):
        date_parts.append(f"op {_format_date_nl(taak['startdatum'])}")
    if tijd:
        date_parts.append(f"om {tijd}")
    if date_parts:
        parts.append(" ".join(date_parts))

    if persoon and persoon.lower() != "ik":
        parts.append(f"uitgevoerd door {persoon}")
    elif persoon and persoon.lower() == "ik":
        parts.append("uitgevoerd door jou")

    return " ".join(parts) + "."


# ---------------------------------------------------------------------------
# Extract all fields from a single message (without context logic)
# ---------------------------------------------------------------------------

def _extract_fields(text: str) -> dict:
    """Extract all parseable fields from a message. Returns a flat dict."""
    return {
        "datum": parse_datum(text),
        "tijd": parse_tijd(text),
        "persoon": extract_persoon(text),
        "locatie": extract_locatie(text),
        "taak_type": detect_taak_type(text),
        "activiteit": extract_activiteit(text),
    }


def _has_action(text: str, fields: dict) -> bool:
    """Check if the message contains an actionable task description."""
    lower = text.lower()
    return bool(fields["taak_type"]) or any(v in lower for v in ACTIVITEIT_VERBS[:30])


# ---------------------------------------------------------------------------
# Multi-turn context merging
# ---------------------------------------------------------------------------

def _merge_into_context(context: dict, new_fields: dict) -> dict:
    """Merge newly extracted fields into existing partial context.
    New values override empty/missing ones, but don't overwrite existing data."""
    merged = dict(context)
    for key in ("datum", "tijd", "persoon", "locatie", "taak_type", "activiteit"):
        new_val = new_fields.get(key)
        if new_val:
            # For persoon: a new name from a follow-up replaces the old one,
            # because we explicitly asked "who"
            # For other fields: only fill in blanks
            if key == "persoon" or not merged.get(key):
                merged[key] = new_val
    return merged


def _context_missing_fields(fields: dict) -> list[str]:
    """Return list of missing required fields, in the order we should ask.

    All 5 are required: activiteit, locatie, datum, tijd, persoon.
    We ask for them one by one in this order.
    """
    missing = []
    # activiteit is usually present from the first message; check anyway
    if not fields.get("activiteit") or len(fields.get("activiteit", "")) < 3:
        missing.append("activiteit")
    if not fields.get("locatie"):
        missing.append("locatie")
    if not fields.get("datum"):
        missing.append("datum")
    if not fields.get("tijd"):
        missing.append("tijd")
    if not fields.get("persoon"):
        missing.append("persoon")
    return missing


def _build_followup_question(missing: list[str], fields: dict) -> str:
    """Build a friendly Dutch follow-up question for the FIRST missing field.

    We ask one field at a time in conversational tone.
    """
    activiteit = fields.get("activiteit", "de taak")
    # First missing field determines the question
    first = missing[0] if missing else None

    if first == "activiteit":
        return "Wat moet er precies gebeuren? Beschrijf de taak (bijv. tegels leggen, muren metselen)."

    if first == "locatie":
        return f"Op welke locatie wordt **{activiteit.lower()}** uitgevoerd? (bijv. badkamer, blok A, 2e verdieping)"

    if first == "datum":
        return f"Op welke datum moet dit gebeuren? (bijv. zaterdag, 28 februari, volgende week maandag)"

    if first == "tijd":
        return f"Hoe laat begin je? (bijv. 9u, 14:30, om 10 uur)"

    if first == "persoon":
        return f"En wie voert dit uit? (naam of functie, bijv. Jan de Vries of de loodgieter)"

    return "Kun je meer details geven?"


# ---------------------------------------------------------------------------
# Main parse function — multi-turn aware
# ---------------------------------------------------------------------------

def parse_bericht(text: str, context: dict | None = None) -> dict:
    """
    Parse a Dutch construction chat message, optionally merging with prior context
    from an incomplete previous message.

    Returns a dict with:
      heeft_taak: bool          — True if a complete task was created
      taak: dict | None         — The full task data (only when heeft_taak=True)
      antwoord: str             — Dutch response text
      onvolledig: dict | None   — Partial context to send back next turn (when info is missing)
    """
    lower = text.lower().strip()

    # --- If we have context, this is a follow-up message ---
    if context:
        # "sla over" / "skip" → force-create with whatever we have
        skip_words = ("sla over", "overslaan", "skip", "laat maar", "maakt niet uit", "geen idee", "weet niet")
        if any(lower.startswith(w) or lower == w for w in skip_words):
            # Fill reasonable defaults for anything still missing
            if not context.get("datum"):
                context["datum"] = date.today().isoformat()
            if not context.get("tijd"):
                context["tijd"] = "08:00"
            if not context.get("persoon"):
                context["persoon"] = ""
            if not context.get("locatie"):
                context["locatie"] = ""
            return _build_complete_result(context)

        new_fields = _extract_fields(text)

        # Check if the follow-up is a greeting/question instead of an answer
        # (user changed topic). If so, drop context and handle fresh.
        if _is_greeting_or_question(lower) and not any(new_fields.get(k) for k in ("datum", "tijd", "persoon", "locatie")):
            return {
                "heeft_taak": False,
                "taak": None,
                "antwoord": _generate_greeting_response(lower),
                "onvolledig": None,
            }

        # For short answers that don't parse as structured fields,
        # try to fill the first missing field with the raw text.
        merged = _merge_into_context(context, new_fields)
        current_missing = _context_missing_fields(merged)

        # If the answer didn't fill the expected field, use raw text as value
        if current_missing and current_missing == _context_missing_fields(context):
            first_missing = current_missing[0]
            raw = text.strip().rstrip(".,;!?")
            if first_missing == "locatie" and raw and not merged.get("locatie"):
                merged["locatie"] = raw[0].upper() + raw[1:] if len(raw) > 1 else raw.upper()
            elif first_missing == "persoon" and raw and not merged.get("persoon"):
                merged["persoon"] = raw[0].upper() + raw[1:] if len(raw) > 1 else raw.upper()

        # Check what's still missing
        missing = _context_missing_fields(merged)

        if missing:
            return {
                "heeft_taak": False,
                "taak": None,
                "antwoord": _build_followup_question(missing, merged),
                "onvolledig": merged,
            }

        # All 5 fields present — create the task!
        return _build_complete_result(merged)

    # --- Fresh message (no context) ---

    # Greetings / questions
    if _is_greeting_or_question(lower):
        return {
            "heeft_taak": False,
            "taak": None,
            "antwoord": _generate_greeting_response(lower),
            "onvolledig": None,
        }

    fields = _extract_fields(text)

    # Need at least an activity indicator
    if not _has_action(text, fields):
        return {
            "heeft_taak": False,
            "taak": None,
            "antwoord": "Ik begrijp je bericht, maar kon er geen concrete taak uit halen. "
                        "Probeer iets als: \"Ik kom donderdag om 9u het sanitair plaatsen in blok A\".",
            "onvolledig": None,
        }

    # Check what's missing — ask one by one
    missing = _context_missing_fields(fields)

    if missing:
        return {
            "heeft_taak": False,
            "taak": None,
            "antwoord": _build_followup_question(missing, fields),
            "onvolledig": fields,
        }

    # All 5 fields present — build task immediately
    return _build_complete_result(fields)


def _build_complete_result(fields: dict) -> dict:
    """Build a complete task result from merged fields."""
    datum = fields.get("datum")
    tijd = fields.get("tijd")
    persoon = fields.get("persoon", "")
    locatie = fields.get("locatie", "")
    taak_type = fields.get("taak_type", "")
    activiteit = fields.get("activiteit", "Taak")

    naam = _build_task_name(activiteit, taak_type, locatie)

    einddatum = None
    if datum:
        duur_dagen = DUUR_SCHATTING.get(taak_type, 1)
        eind = date.fromisoformat(datum) + timedelta(days=duur_dagen)
        einddatum = eind.isoformat()

    beschrijving_parts = [activiteit]
    if locatie:
        beschrijving_parts.append(f"Locatie: {locatie}")
    if tijd:
        beschrijving_parts.append(f"Tijd: {tijd}")
    beschrijving = " — ".join(beschrijving_parts)

    taak = {
        "naam": naam,
        "beschrijving": beschrijving,
        "startdatum": datum,
        "einddatum": einddatum,
        "toegewezen_aan": persoon if persoon.lower() != "ik" else "",
        "locatie": locatie,
        "taak_type": taak_type,
    }

    antwoord = _build_confirmation(taak, tijd, persoon)

    return {
        "heeft_taak": True,
        "taak": taak,
        "antwoord": antwoord,
        "onvolledig": None,
    }
