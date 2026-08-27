"""Configuration constants for the Bromley new-dwelling approvals site."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "bromley.db"
STATIC_DIR = PROJECT_ROOT / "static"

# --- PlanIt feed -------------------------------------------------------------
# PlanIt scrapes Bromley's Arcus public register and exposes it as JSON.
# Bromley's own portal (planningaccess.bromley.gov.uk) has no public API.
PLANIT_URL = "https://www.planit.org.uk/api/applics/json"
AUTHORITY = "Bromley"

# Fields we ask PlanIt for. Keeping this tight keeps us under the 1000kB
# per-request cap so pagination stays predictable.
PLANIT_SELECT = ",".join(
    [
        "uid",
        "app_type",
        "app_size",
        "postcode",
        "address",
        "description",
        "decided_date",
        "start_date",
        "location_x",
        "location_y",
        "url",
        "link",
    ]
)

PAGE_SIZE = 500          # PlanIt caps any single request at 5000 results
PAGE_DELAY_SECONDS = 1.5  # PlanIt rate limits; back off between pages
MAX_RETRIES = 3

DEFAULT_REFRESH_DAYS = 30  # routine top-up window when --from/--to omitted

# --- Classification ----------------------------------------------------------
# Bromley encodes the application type in the reference suffix (26/01095/FPA).
# This is more reliable than PlanIt's app_type, which lumps householder
# applications in with full applications under "Full".
KEEP_SUFFIXES = {
    "FPA",    # full planning permission
    "OUT",    # outline
    "NOT",    # prior approval / notification
    "S73A",   # variation of condition
}

DROP_SUFFIXES = {
    "HPA",    # householder (extensions etc.)
    "TCA",    # trees in conservation area
    "TPO",    # tree preservation order
    "ADV",    # advertising
    "CON",    # discharge of conditions
    "CON1",
    "CON2",
    "CON3",
    "LDC",    # lawful development certificate - a confirmation, not a permission
    "AMD",    # non-material amendment
    "DEM",    # demolition notification only
    "DEMCON",
}

# --- Outbound links ----------------------------------------------------------
# PlanIt records a Salesforce record URL for each application, but those record
# IDs do not resolve for the public -- they render "Invalid Page" (verified
# against 25/05448/FPA, decided June 2026). The register is only reachable by
# searching for the application reference, so we send people there and give
# them the reference to paste. The URL is stored but not presented as a link.
BROMLEY_REGISTER_SEARCH_URL = "https://planningaccess.bromley.gov.uk/pr/s/"
