"""Text writers turn ListingFacts into a messy, human-looking title + description.

TemplateWriter: offline phrase bank (English + Gulf Arabic). Instant and free.
GeminiWriter:   LLM rewrite in batches, used to replace template text over time.
"""

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from generator.facts import ListingFacts


@dataclass(frozen=True)
class ListingText:
    title: str
    description: str
    writer: str


class TextWriter(ABC):
    name: str

    @abstractmethod
    async def write(self, batch: list[ListingFacts]) -> dict[str, ListingText]:
        """Return texts keyed by external_id. Missing keys mean "not written"."""


def facts_fingerprint(f: ListingFacts) -> str:
    """Changes whenever the facts a text was written from change (invalidates caches)."""
    payload = {
        "category": f.category, "label": f.item_label, "condition": f.condition,
        "listing_type": f.listing_type, "period": f.price_period, "attrs": f.attributes,
        "location": f.location, "language": f.language, "styles": f.styles, "omit": f.omit,
    }  # fmt: skip
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ text validation

ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")
# A written price would compete with the structured price field, so reject it.
PRICE_IN_TEXT = re.compile(
    r"(?i)(?:qar|qr|usd|\$|ريال|دولار)\s?\d[\d,.]*|\d[\d,.]*\s?(?:qar|qr|usd|\$|k\b|ريال|دولار)"
)


def language_ok(text: str, language: str) -> bool:
    ar, lat = len(ARABIC.findall(text)), len(LATIN.findall(text))
    letters = ar + lat or 1
    if language == "en":
        return ar / letters < 0.05
    if language == "ar":
        # Arabic listings keep Latin model names ("HP Spectre x360"), so require a share.
        return ar / letters > 0.3
    return ar > 0 and lat > 0  # mixed


def validate_text(f: ListingFacts, title: str, description: str) -> str | None:
    """Return a reason the text is unusable, or None if it is fine."""
    if not 5 <= len(title) <= 140:
        return "title length"
    if not 15 <= len(description) <= 1500:
        return "description length"
    if not language_ok(f"{title} {description}", f.language):
        return "language"
    if PRICE_IN_TEXT.search(f"{title} {description}"):
        return "mentions a price"
    return None
