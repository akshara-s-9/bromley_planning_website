"""Decide whether a permitted application is a genuine new-build dwelling.

A bare "dwelling" keyword search is mostly noise: over a year of Bromley
permissions, 44 descriptions mention "dwelling" but only ~13 are new houses --
the rest are extensions "to existing dwelling", outbuildings and certificates.

Every record keeps its `reason`, so a misclassification can be diagnosed
instead of silently vanishing.
"""

from __future__ import annotations

import re

from . import config

# The user's keyword. PlanIt's own search stems, so "dwellings" is covered.
KEYWORD_RE = re.compile(r"\bdwelling(?:s|house|houses)?\b", re.I)

# Something is being built, and what is being built is somewhere to live.
NEW_BUILD_RE = re.compile(
    r"\b(erection|erect|construction|construct|redevelopment|demolition)\b"
    r".{0,120}?"
    r"\b(dwelling|dwellinghouse|dwellinghouses|dwellings|house|houses|bungalow|bungalows|home|homes)\b",
    re.I | re.S,
)

UK_POSTCODE_RE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.I)


def reference_suffix(uid: str) -> str:
    """Bromley encodes application type in the reference: 26/01095/FPA -> FPA."""
    return (uid or "").rsplit("/", 1)[-1].strip().upper()


def extract_postcode(record: dict) -> str | None:
    """PlanIt's postcode field is occasionally null; recover it from the address."""
    postcode = (record.get("postcode") or "").strip()
    if postcode:
        return postcode.upper()

    match = UK_POSTCODE_RE.search(record.get("address") or "")
    return match.group(0).upper() if match else None


def classify(record: dict) -> tuple[bool, str]:
    """Return (is_new_build, reason)."""
    description = record.get("description") or ""
    suffix = reference_suffix(record.get("uid", ""))

    if not description.strip():
        return False, "no description"

    if not KEYWORD_RE.search(description):
        return False, "description does not mention 'dwelling'"

    if suffix in config.DROP_SUFFIXES:
        return False, f"excluded application type '{suffix}'"

    match = NEW_BUILD_RE.search(description)
    if not match:
        return False, "mentions 'dwelling' but no erection/construction of a new home"

    if suffix and suffix not in config.KEEP_SUFFIXES:
        return False, f"unrecognised application type '{suffix}'"

    return True, f"new-build phrase '{' '.join(match.group(0).split())[:70]}' in {suffix}"
