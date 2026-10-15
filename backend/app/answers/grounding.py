"""Grounding for generated answers (Stage 7): what the LLM may say, enforced in code.

Rules (acceptance: no response ever contains a price or link that did not come from the DB):
1. Citations: only listings the model was shown. Anything else is dropped and counted.
2. No prices in the text at all. Prices appear only on the cards, which are built from DB
   rows. A sentence that mentions a price is removed.
3. No links, e-mail addresses or phone numbers in the text. Sentences with them are removed.
If nothing is left, a plain template answer is used instead.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

ARABIC = re.compile(r"[؀-ۿ]")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

CURRENCY = (
    r"(?:qar|qr|q\.r|riyals?|rials?|usd|us\$|\$|dollars?|aed|dhs?|dirhams?|sar|eur|€|£"
    r"|ريال|ريالات|ر\.ق|دولار|درهم)"
)
NUMBER = r"\d[\d,.]*(?:\s?(?:k|m|million|thousand|الف|ألف|مليون))?"
PRICE_PATTERNS = [
    re.compile(rf"{CURRENCY}\s?{NUMBER}", re.IGNORECASE),  # QAR 3,500 / $900
    re.compile(rf"{NUMBER}\s?{CURRENCY}", re.IGNORECASE),  # 3500 QAR / 900$ / 30 الف ريال
    re.compile(
        r"(?:price[sd]?|priced|costs?|for only|asking|budget|سعر|السعر|بسعر)\D{0,12}\d",
        re.IGNORECASE,
    ),
    # A grouped number with no unit after it ("3,500", "1.2 million") reads as an amount.
    re.compile(
        r"\b\d{1,3}(?:,\d{3})+(?!\s?(?:km|kms|gb|tb|sqm|m2|m²|km/h|كم|متر|cc|mah|hz))"
        r"|\b\d+(?:\.\d+)?\s?(?:million|مليون)\b"
        # "under 40k" is a price; "40k km" and a "4K screen" are not.
        r"|\b\d+(?:\.\d+)?\s?k\b(?!\s?(?:km|kms|m\b|screen|display|tv|video|oled|uhd|hdr|كم))",
        re.IGNORECASE,
    ),
]
LINK_PATTERNS = [
    re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE),
    re.compile(r"\b[\w.-]+\.(?:com|qa|net|org|me|io|co|app|link)\b(?:/\S*)?", re.IGNORECASE),
    re.compile(r"\bwa\.me/\S+|\bt\.me/\S+", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),  # e-mail
    re.compile(r"(?:\+?974[\s-]?)?\b\d{4}[\s-]?\d{4}\b"),  # Qatari phone numbers (8 digits)
]
SENTENCE_END = re.compile(r"(?<=[.!?؟。])\s+|\n+")


def has_price(text: str) -> bool:
    t = text.translate(ARABIC_DIGITS)
    return any(p.search(t) for p in PRICE_PATTERNS)


def has_link(text: str) -> bool:
    t = text.translate(ARABIC_DIGITS)
    return any(p.search(t) for p in LINK_PATTERNS)


@dataclass(frozen=True)
class Grounded:
    summary: str
    cited_ids: list[int]
    dropped_ids: list[int]  # cited by the model but not in the provided set (or repeated)
    removed_sentences: int  # sentences removed for a price or a link
    used_template: bool  # nothing usable was left; a template answer was used


def validate_citations(
    refs: Sequence[int], provided_ids: Sequence[int], limit: int = 3
) -> tuple[list[int], list[int]]:
    """Map 1-based candidate numbers to listing ids; drop anything not provided."""
    kept: list[int] = []
    dropped: list[int] = []
    for ref in refs:
        if isinstance(ref, int) and 1 <= ref <= len(provided_ids):
            listing_id = provided_ids[ref - 1]
            if listing_id not in kept and len(kept) < limit:
                kept.append(listing_id)
                continue
        dropped.append(ref)
    return kept, dropped


def clean_summary(text: str) -> tuple[str, int]:
    """Remove every sentence that contains a price or a link. Returns (text, removed)."""
    sentences = [s.strip() for s in SENTENCE_END.split(text or "") if s.strip()]
    kept = [s for s in sentences if not has_price(s) and not has_link(s)]
    return " ".join(kept), len(sentences) - len(kept)


def template_answer(query: str, count: int) -> str:
    if ARABIC.search(query):
        return f"وجدت {count} من الإعلانات المطابقة لطلبك. التفاصيل والأسعار في البطاقات أدناه."
    noun = "listing" if count == 1 else "listings"
    return f"I found {count} matching {noun}. Details and prices are on the cards below."


def ground(query: str, summary: str, refs: Sequence[int], provided_ids: Sequence[int]) -> Grounded:
    cited, dropped = validate_citations(refs, provided_ids)
    text, removed = clean_summary(summary)
    used_template = not text
    if used_template:
        text = template_answer(query, len(provided_ids))
    return Grounded(text, cited, dropped, removed, used_template)
