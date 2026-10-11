"""ListingSource: anything that yields normalized listings for ingestion.

The synthetic dataset is the first implementation; a future permitted real source
implements the same interface.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from app.models.listing import NormalizedListing

# Attribute keys worth repeating in search_text, in display order.
SEARCH_ATTRIBUTE_KEYS = (
    "storage_gb",
    "ram_gb",
    "color",
    "year",
    "mileage_km",
    "cpu",
    "gpu",
    "screen_in",
    "transmission",
    "fuel",
    "trim",
    "property_type",
    "bedrooms",
    "bathrooms",
    "area_sqm",
    "furnished",
    "neighborhood",
    "material",
    "item_type",
)


class ListingSource(ABC):
    name: str

    @abstractmethod
    def iter_listings(self) -> Iterator[NormalizedListing]: ...


def build_search_text(listing: NormalizedListing) -> str:
    """Title + description + key structured facts: the text that gets embedded."""
    facts: list[str] = [listing.category]
    for value in (listing.brand, listing.model):
        if value:
            facts.append(value)
    if listing.condition:
        facts.append(f"condition: {listing.condition.value.replace('_', ' ')}")
    if listing.listing_type.value == "rent":
        facts.append(f"for rent per {listing.price_period.value}")
    attrs = listing.attributes
    for key in SEARCH_ATTRIBUTE_KEYS:
        if attrs.get(key) not in (None, ""):
            facts.append(f"{key.replace('_', ' ')}: {attrs[key]}")
    facts.append(f"location: {listing.location}")
    return f"{listing.title}\n{listing.description}\n{' | '.join(facts)}"


class SyntheticListingSource(ListingSource):
    """Reads the generator's JSONL dataset (data/listings.jsonl)."""

    name = "synthetic"

    def __init__(self, path: Path) -> None:
        self.path = path

    def iter_listings(self) -> Iterator[NormalizedListing]:
        with self.path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                record.pop("meta", None)  # generator ground truth, not stored in the DB
                try:
                    yield NormalizedListing.model_validate(record)
                except ValueError as exc:
                    raise ValueError(f"{self.path.name}:{line_no}: {exc}") from exc
