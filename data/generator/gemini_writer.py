"""Gemini text writer: rewrites listing text in batches from structured facts."""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field

from app.providers.gemini import GeminiJsonClient, JsonResult
from generator.facts import ListingFacts
from generator.writers import ListingText, TextWriter, validate_text

logger = logging.getLogger(__name__)

SYSTEM = """\
You write realistic classified-ad text for a second-hand marketplace in Qatar.
For each input item write a `title` and a `description` the way a real seller would.

Rules:
1. Use ONLY the facts given. Never invent specs, accessories or defects that contradict them.
   You may leave facts out.
2. NEVER write a price or money amount (no numbers next to QAR, QR, USD, $, riyal, "k").
   Phrases like "negotiable" or "final price" are fine.
3. Language:
   - en: English only.
   - ar: Gulf Arabic (Qatari/Khaleeji colloquial is fine). Keep brand and model names in
     Latin letters, as sellers do.
   - mixed: mostly Arabic with English words, specs and model names mixed in.
   Always use Western digits 0-9, never Arabic-Indic digits.
4. Apply every style hint:
   terse = 1-2 short fragments; typos = several realistic spelling mistakes;
   abbrev = heavy abbreviations (w/, gd cond, pls, neg, BR, apt); caps = title in capitals
   with "!!"; detailed = 3-6 sentences covering most facts; emoji = a few emojis;
   partial = do NOT mention the facts listed in `omit`; casual = chatty, give a reason for
   selling or renting.
5. Express condition naturally: new = sealed / never used; like_new = barely used;
   good = normal use, minor marks; fair = visible wear; poor = damaged or needs repair
   (you may name one plausible defect).
6. Title: 3-12 words. Description: 1-6 sentences, under 600 characters.
7. Vary wording between items; do not reuse the same opening line.

Return JSON with exactly one entry per input `ref`.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["ref", "title", "description"],
            },
        }
    },
    "required": ["items"],
}


def facts_payload(ref: str, f: ListingFacts) -> dict:
    attrs = {k: v for k, v in f.attributes.items() if k not in f.omit}
    listing = "sale" if f.listing_type == "sale" else f"rent per {f.price_period}"
    return {
        "ref": ref,
        "category": f.category,
        "item": f.item_label,
        "brand": f.brand,
        "model": f.model,
        "condition": f.condition,
        "listing": listing,
        "location": f.location,
        "seller": f.seller_kind,
        "attributes": attrs,
        "language": f.language,
        "style": f.styles,
        "omit": f.omit,
    }


@dataclass
class BatchReport:
    requested: int
    accepted: int
    rejected: Counter = field(default_factory=Counter)
    rejected_ids: list[str] = field(default_factory=list)
    usage: JsonResult | None = None


class GeminiWriter(TextWriter):
    name = "gemini"

    def __init__(self, client: GeminiJsonClient) -> None:
        self.client = client
        self.last_report: BatchReport | None = None

    async def write(self, batch: list[ListingFacts]) -> dict[str, ListingText]:
        refs = {str(i): f for i, f in enumerate(batch, start=1)}
        prompt = json.dumps(
            {"items": [facts_payload(r, f) for r, f in refs.items()]}, ensure_ascii=False
        )
        result = await self.client.generate_json(system=SYSTEM, prompt=prompt, schema=SCHEMA)
        report = BatchReport(requested=len(batch), accepted=0, usage=result)
        out: dict[str, ListingText] = {}
        try:
            items = json.loads(result.text)["items"]
        except (json.JSONDecodeError, KeyError, TypeError):
            report.rejected["unparseable response"] = len(batch)
            self.last_report = report
            return out
        for item in items:
            f = refs.get(str(item.get("ref")))
            if f is None or f.external_id in out:
                report.rejected["unknown or repeated ref"] += 1
                continue
            title = str(item.get("title", "")).strip()
            desc = str(item.get("description", "")).strip()
            reason = validate_text(f, title, desc)
            if reason:
                report.rejected[reason] += 1
                report.rejected_ids.append(f.external_id)
                continue
            out[f.external_id] = ListingText(title=title, description=desc, writer=self.name)
        missing = [f.external_id for f in batch if f.external_id not in out]
        report.rejected["missing"] += len(set(missing) - set(report.rejected_ids))
        report.accepted = len(out)
        self.last_report = report
        return out
