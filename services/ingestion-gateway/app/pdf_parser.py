"""PDF parser for Gantt-style Dutch construction planning tables.

Expected PDF structure:
- Columns = dates (week numbers 36-43+, days ma/di/wo/do/vr with day numbers)
- Header rows contain: street name per column, house number per column
- Data rows = numbered activity rows (1-25+), each with:
    - Row number
    - Activity description + responsible company
    - Cell values = house numbers being worked on that day
"""

import io
import re
from datetime import datetime, timedelta
from typing import Optional

import pdfplumber


# ---------------------------------------------------------------------------
# Known companies — used to split activity name from company
# ---------------------------------------------------------------------------
KNOWN_COMPANIES = [
    "Jos v.d. Steen",
    "Goed Werk",
    "Eleqtriq",
    "Mommers",
    "Derhaag",
    "Loomer",
    "Geerts",
    "Keller",
    "Paulo",
    "CHB",
    "LVA",
    "iedereen",
]

# Sort longest first so "Jos v.d. Steen" matches before a shorter substring
KNOWN_COMPANIES.sort(key=len, reverse=True)

# ---------------------------------------------------------------------------
# Ruimte codes — BKT renovatie (Badkamer / Keuken / Toilet)
# ---------------------------------------------------------------------------
RUIMTE_CODES: dict[str, str] = {
    "BKT": "Badkamer, Keuken & Toilet",
    "BK":  "Badkamer & Keuken",
    "BT":  "Badkamer & Toilet",
    "KT":  "Keuken & Toilet",
    "B":   "Badkamer",
    "K":   "Keuken",
    "T":   "Toilet",
}
# Sort longest first so "BKT" matches before "B"
_RUIMTE_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(RUIMTE_CODES.keys(), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Days of the week abbreviations used in the header
_DAY_ABBREVS = {"ma", "di", "wo", "do", "vr", "za", "zo"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_tables_from_pdf(pdf_bytes: bytes) -> list[list[list[Optional[str]]]]:
    """Extract all tables from all pages of the PDF using pdfplumber."""
    tables: list[list[list[Optional[str]]]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 5,
            })
            tables.extend(page_tables)
    return tables


def parse_gantt_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Main entry point: extract tables from the PDF and parse the Gantt planning.

    Returns a list of task dicts ready for DB insertion.
    """
    tables = extract_tables_from_pdf(pdf_bytes)
    if not tables:
        return []

    all_tasks: list[dict] = []
    for table in tables:
        tasks = _parse_single_table(table)
        all_tasks.extend(tasks)

    # Consolidate: group identical activity+company+location, merge date ranges
    return _consolidate_tasks(all_tasks)


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

def _parse_single_table(table: list[list[Optional[str]]]) -> list[dict]:
    """Parse a single extracted table into task entries."""
    if not table or len(table) < 3:
        return []

    rows = [[_clean_cell(c) for c in row] for row in table]
    num_cols = max(len(r) for r in rows)

    # Pad rows to uniform width
    for row in rows:
        while len(row) < num_cols:
            row.append("")

    # Step 1: Find header rows and build column mappings
    week_row_idx, day_name_row_idx, day_num_row_idx = _find_header_rows(rows)
    street_row_idx, house_row_idx = _find_location_header_rows(rows, day_num_row_idx)

    col_dates = _build_date_mapping(rows, week_row_idx, day_name_row_idx, day_num_row_idx)
    col_locations = _build_location_mapping(rows, street_row_idx, house_row_idx)

    # Step 2: Find the first data column (columns before it are row# and activity name)
    data_start_col = _find_data_start_col(col_dates)
    if data_start_col is None:
        return []

    # Step 3: Parse activity rows
    tasks: list[dict] = []
    activity_row_start = max(
        (i for i in [week_row_idx, day_name_row_idx, day_num_row_idx, street_row_idx, house_row_idx] if i is not None),
        default=-1,
    ) + 1

    for row_idx in range(activity_row_start, len(rows)):
        row = rows[row_idx]
        activity_name, company, ruimte = _parse_activity_cell(row, data_start_col)
        if not activity_name:
            continue

        # Scan data columns for non-empty cells
        for col_idx in range(data_start_col, num_cols):
            cell_value = row[col_idx] if col_idx < len(row) else ""
            if not cell_value:
                continue

            date = col_dates.get(col_idx)
            street = col_locations.get(col_idx, "")

            # Cell value = house number(s) being worked on that day
            house_numbers = _parse_house_numbers(cell_value)

            # Build display name: "Tegelwerk vloer (Badkamer) - Bizetstraat 16"
            ruimte_suffix = f" ({ruimte})" if ruimte else ""
            display_name = f"{activity_name}{ruimte_suffix}"

            if house_numbers:
                for hn in house_numbers:
                    loc = f"{street} {hn}".strip() if street else hn
                    tasks.append({
                        "naam": f"{display_name} - {loc}" if loc else display_name,
                        "beschrijving": ruimte or "",
                        "status": "gepland",
                        "startdatum": date or "",
                        "einddatum": date or "",
                        "toegewezen_aan": company,
                        "locatie": loc,
                        "ruimte": ruimte,
                    })
            else:
                loc = street or ""
                tasks.append({
                    "naam": f"{display_name} - {loc}" if loc else display_name,
                    "beschrijving": ruimte or "",
                    "status": "gepland",
                    "startdatum": date or "",
                    "einddatum": date or "",
                    "toegewezen_aan": company,
                    "locatie": loc,
                    "ruimte": ruimte,
                })

    return tasks


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

def _find_header_rows(rows: list[list[str]]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Find the row indices for:
    - week numbers (contains "36", "37", ... or "week 36", etc.)
    - day names (contains "ma", "di", "wo", "do", "vr")
    - day numbers (contains sequences of small numbers like 1,2,3,4,5)
    """
    week_row = None
    day_name_row = None
    day_num_row = None

    for idx, row in enumerate(rows[:15]):  # only scan first 15 rows
        cells = [c.lower() for c in row if c]

        # Week row: contains "week" or week numbers 36-53
        week_pattern_count = sum(
            1 for c in cells
            if re.search(r"\bweek\b", c) or re.match(r"^(3[6-9]|4\d|5[0-3])$", c.strip())
        )
        if week_pattern_count >= 2:
            week_row = idx
            continue

        # Day name row: contains ma/di/wo/do/vr
        day_count = sum(1 for c in cells if c.strip() in _DAY_ABBREVS)
        if day_count >= 3:
            day_name_row = idx
            continue

        # Day number row: mostly small numbers (1-31)
        num_count = sum(1 for c in cells if re.match(r"^\d{1,2}$", c.strip()))
        if num_count >= 5 and day_num_row is None:
            day_num_row = idx

    return week_row, day_name_row, day_num_row


def _find_location_header_rows(
    rows: list[list[str]], after_idx: Optional[int]
) -> tuple[Optional[int], Optional[int]]:
    """
    Find header rows containing street names and house numbers.
    Street rows contain text like "Bizetstraat", "Beethovenstraat", etc.
    House number rows contain repeating small numbers (house numbers).
    """
    start = (after_idx or 0) + 1 if after_idx is not None else 0
    street_row = None
    house_row = None

    street_pattern = re.compile(r"[A-Z][a-z]+(straat|laan|weg|plein|singel|hof|dreef|kade)", re.IGNORECASE)

    for idx in range(start, min(start + 10, len(rows))):
        row = rows[idx]
        cells = [c for c in row if c]

        street_count = sum(1 for c in cells if street_pattern.search(c))
        if street_count >= 1 and street_row is None:
            street_row = idx
            continue

        # House number row: contains many small numbers
        num_count = sum(1 for c in cells if re.match(r"^\d{1,4}$", c.strip()))
        if num_count >= 3 and house_row is None:
            house_row = idx

    return street_row, house_row


# ---------------------------------------------------------------------------
# Column → date mapping
# ---------------------------------------------------------------------------

def _build_date_mapping(
    rows: list[list[str]],
    week_row_idx: Optional[int],
    day_name_row_idx: Optional[int],
    day_num_row_idx: Optional[int],
) -> dict[int, str]:
    """
    Build a mapping of column index → ISO date string.

    Uses week numbers (36+ starting September 2025) and day-of-week or
    day-number to compute exact dates.
    """
    col_dates: dict[int, str] = {}

    if week_row_idx is None:
        return col_dates

    week_row = rows[week_row_idx]

    # Build column → week number mapping (week numbers span multiple columns)
    col_week: dict[int, int] = {}
    current_week: Optional[int] = None
    for col_idx, cell in enumerate(week_row):
        wn = _extract_week_number(cell)
        if wn is not None:
            current_week = wn
        if current_week is not None:
            col_week[col_idx] = current_week

    # Try day names first (ma=0, di=1, wo=2, do=3, vr=4)
    if day_name_row_idx is not None:
        day_row = rows[day_name_row_idx]
        day_offset_map = {"ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6}

        # Track day-within-week to handle the offset correctly
        for col_idx, cell in enumerate(day_row):
            day_abbr = cell.strip().lower()
            if day_abbr in day_offset_map and col_idx in col_week:
                week_num = col_week[col_idx]
                day_offset = day_offset_map[day_abbr]
                date = _week_number_to_monday(week_num) + timedelta(days=day_offset)
                col_dates[col_idx] = date.strftime("%Y-%m-%d")

    # If day names didn't cover it, try day numbers
    if not col_dates and day_num_row_idx is not None:
        day_num_row = rows[day_num_row_idx]
        for col_idx, cell in enumerate(day_num_row):
            m = re.match(r"^(\d{1,2})$", cell.strip())
            if m and col_idx in col_week:
                day_num = int(m.group(1))
                week_num = col_week[col_idx]
                date = _resolve_date_from_week_and_day(week_num, day_num)
                if date:
                    col_dates[col_idx] = date.strftime("%Y-%m-%d")

    return col_dates


def _extract_week_number(cell: str) -> Optional[int]:
    """Extract a week number from a cell like 'Week 36', '36', 'week 37', etc."""
    if not cell:
        return None
    m = re.match(r"(?:week\s*)?(\d{1,2})$", cell.strip(), re.IGNORECASE)
    if m:
        wn = int(m.group(1))
        if 1 <= wn <= 53:
            return wn
    return None


def _week_number_to_monday(week_num: int) -> datetime:
    """
    Convert an ISO week number to the Monday of that week.

    Weeks 36-53 → year 2025 (September 2025 onwards)
    Weeks 1-35  → year 2026
    """
    year = 2025 if week_num >= 36 else 2026
    # ISO week: %G = ISO year, %V = ISO week, %u = weekday (1=Monday)
    return datetime.strptime(f"{year}-W{week_num:02d}-1", "%G-W%V-%u")


def _resolve_date_from_week_and_day(week_num: int, day_num: int) -> Optional[datetime]:
    """
    Given a week number and a day-of-month number, figure out the actual date.

    We know the Monday of the week, and we know the day number. The month can
    be inferred from the week start.
    """
    monday = _week_number_to_monday(week_num)
    # Try each day of this week (Mon-Fri) and see which has the matching day number
    for offset in range(7):
        candidate = monday + timedelta(days=offset)
        if candidate.day == day_num:
            return candidate
    # If no exact match in the week (could happen at month boundaries), try nearby
    for offset in range(-2, 9):
        candidate = monday + timedelta(days=offset)
        if candidate.day == day_num:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Column → location mapping
# ---------------------------------------------------------------------------

def _build_location_mapping(
    rows: list[list[str]],
    street_row_idx: Optional[int],
    house_row_idx: Optional[int],
) -> dict[int, str]:
    """Build a mapping of column index → street name only.

    House numbers come from the cell values in activity rows, not from
    the header. The header house-number row is ignored here because the
    cell value in each activity row already tells us which house is being
    worked on.
    """
    col_locations: dict[int, str] = {}

    if street_row_idx is not None:
        street_row = rows[street_row_idx]
        current_street = ""
        for col_idx, cell in enumerate(street_row):
            if cell.strip():
                current_street = cell.strip()
            if current_street:
                col_locations[col_idx] = current_street

    return col_locations


# ---------------------------------------------------------------------------
# Activity row parsing
# ---------------------------------------------------------------------------

def _parse_activity_cell(row: list[str], data_start_col: int) -> tuple[str, str, str]:
    """
    Extract activity name, company and ruimte from the label columns of a row.

    Activity rows typically start with a row number (1-25+) followed by
    the activity description which ends with a company name.

    Returns (activity_name, company, ruimte_label).
    """
    # Combine all cells before data_start_col as the label
    label_parts = [row[i] for i in range(min(data_start_col, len(row))) if row[i]]
    if not label_parts:
        return ("", "", "")

    # REQUIRE a row number (1-99) as first part — real activities are always numbered
    first = label_parts[0].strip()
    if not re.match(r"^\d{1,2}$", first):
        return ("", "", "")  # Not a numbered activity row, skip
    label_parts = label_parts[1:]

    if not label_parts:
        return ("", "", "")

    full_label = " ".join(label_parts).strip()
    if not full_label or len(full_label) < 3:
        return ("", "", "")

    # Skip rows that look like headers, not activities
    if _is_header_text(full_label):
        return ("", "", "")

    # Extract company name first
    activity, company = _split_activity_and_company(full_label)

    # Then extract ruimte code from the activity name
    activity, ruimte = _extract_ruimte(activity.strip())

    return (activity.strip(), company.strip(), ruimte)


def _extract_ruimte(text: str) -> tuple[str, str]:
    """
    Extract room code from activity text and return (cleaned_text, ruimte_label).

    Example: "Tegelwerk vloer B" → ("Tegelwerk vloer", "Badkamer")
             "Stucwerk wanden BKT" → ("Stucwerk wanden", "Badkamer, Keuken & Toilet")
             "Droogdag"            → ("Droogdag", "")
    """
    m = _RUIMTE_PATTERN.search(text)
    if not m:
        return (text, "")
    code = m.group(1).upper()
    ruimte_label = RUIMTE_CODES.get(code, "")
    # Remove the code from the text
    cleaned = text[:m.start()].strip().rstrip("-–—/ ") + text[m.end():].strip()
    cleaned = cleaned.strip().rstrip("-–—/ ")
    return (cleaned, ruimte_label)


def _split_activity_and_company(text: str) -> tuple[str, str]:
    """Split 'Afdekken / afplakken CHB' into ('Afdekken / afplakken', 'CHB')."""
    for company in KNOWN_COMPANIES:
        # Check if text ends with the company name (case-insensitive)
        pattern = re.compile(re.escape(company) + r"\s*$", re.IGNORECASE)
        m = pattern.search(text)
        if m:
            activity = text[:m.start()].strip().rstrip("-–—/ ")
            return (activity, company)

    # Fallback: last word might be a company
    # Only if it looks like an abbreviation (all caps, 2-4 chars)
    words = text.rsplit(None, 1)
    if len(words) == 2:
        last = words[1]
        if last.isupper() and 2 <= len(last) <= 5 and last.isalpha():
            return (words[0].rstrip("-–—/ "), last)

    return (text, "")


def _is_header_text(text: str) -> bool:
    """Check if text looks like a header/label rather than an activity."""
    lower = text.lower()
    header_patterns = [
        "week", "straat", "huisnr", "datum", "activiteit", "omschrijving",
        "verantwoordelijk", "aannemer", "planning", "nr", "nummer",
    ]
    return lower in header_patterns or (len(text) <= 3 and not text[0].isdigit())


# ---------------------------------------------------------------------------
# House number parsing
# ---------------------------------------------------------------------------

def _parse_house_numbers(cell: str) -> list[str]:
    """
    Parse house numbers from a cell value.

    Cells might contain: "16", "16+18", "16, 18, 20", "14-20", "16\n18", etc.
    """
    cell = cell.strip()
    if not cell:
        return []

    # If the cell is just a single number
    if re.match(r"^\d{1,4}[a-zA-Z]?$", cell):
        return [cell]

    # Split by common separators: +, comma, newline, space, /
    parts = re.split(r"[+,/\n\s]+", cell)
    numbers = []
    for p in parts:
        p = p.strip()
        # Handle ranges like "14-20" (even numbers only, typical for Dutch streets)
        range_match = re.match(r"^(\d{1,4})\s*[-–]\s*(\d{1,4})$", p)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if end > start and (end - start) <= 30:
                step = 2 if (start % 2 == end % 2) else 1
                numbers.extend(str(n) for n in range(start, end + 1, step))
            else:
                numbers.append(p)
        elif re.match(r"^\d{1,4}[a-zA-Z]?$", p):
            numbers.append(p)

    return numbers


# ---------------------------------------------------------------------------
# Task consolidation
# ---------------------------------------------------------------------------

def _consolidate_tasks(tasks: list[dict]) -> list[dict]:
    """
    Merge tasks with the same activity + company + location into date ranges
    instead of one task per day.
    """
    # Group by (activity_base_name, company, location)
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for t in tasks:
        key = (t["naam"], t["toegewezen_aan"], t.get("locatie", ""))
        groups.setdefault(key, []).append(t)

    consolidated: list[dict] = []
    for (naam, company, locatie), group in groups.items():
        dates = sorted(
            t["startdatum"] for t in group if t.get("startdatum")
        )
        start = dates[0] if dates else ""
        end = dates[-1] if dates else ""

        ruimte = group[0].get("ruimte", "") if group else ""

        # Build beschrijving: ruimte + locatie
        beschrijving_parts = []
        if ruimte:
            beschrijving_parts.append(f"Ruimte: {ruimte}")
        if locatie:
            beschrijving_parts.append(f"Locatie: {locatie}")
        beschrijving = " | ".join(beschrijving_parts)

        consolidated.append({
            "naam": naam,
            "beschrijving": beschrijving,
            "status": "gepland",
            "startdatum": start,
            "einddatum": end,
            "toegewezen_aan": company,
        })

    return consolidated


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _clean_cell(cell: Optional[str]) -> str:
    """Clean a cell value from pdfplumber."""
    if cell is None:
        return ""
    return str(cell).strip().replace("\n", " ")


def _find_data_start_col(col_dates: dict[int, str]) -> Optional[int]:
    """Find the first column index that has a date mapping — that's where data starts."""
    if not col_dates:
        return None
    return min(col_dates.keys())
