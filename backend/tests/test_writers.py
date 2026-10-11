import json

import pytest

from app.providers.gemini import JsonResult
from generator.facts import generate_facts
from generator.gemini_writer import GeminiWriter
from generator.locales import QATAR
from generator.template_writer import TemplateWriter
from generator.writers import facts_fingerprint, language_ok, validate_text


@pytest.fixture(scope="module")
def facts():
    return generate_facts(QATAR, seed=11, counts={k: 40 for k in (
        "phones", "laptops", "cars", "furniture", "apartments", "villas")})  # fmt: skip


def test_template_text_is_deterministic(facts):
    w = TemplateWriter()
    assert [w.write_one(f) for f in facts] == [w.write_one(f) for f in facts]


def test_template_text_always_valid(facts):
    w = TemplateWriter()
    failures = [
        (f.external_id, reason)
        for f in facts
        if (reason := validate_text(f, (t := w.write_one(f)).title, t.description))
    ]
    assert failures == []


def test_template_never_uses_arabic_indic_digits(facts):
    w = TemplateWriter()
    for f in facts:
        t = w.write_one(f)
        assert not any("٠" <= ch <= "٩" for ch in t.title + t.description)


@pytest.mark.parametrize(
    ("text", "language", "ok"),
    [
        ("iPhone 17 Pro like new", "en", True),
        ("للبيع ايفون نظيف", "en", False),
        ("للبيع HP Spectre x360 نظيف جداً مع الشاحن", "ar", True),
        ("Selling my HP laptop", "ar", False),
        ("للبيع iPhone 17 Pro نظيف", "mixed", True),
        ("للبيع ايفون نظيف", "mixed", False),
    ],
)
def test_language_check(text, language, ok):
    assert language_ok(text, language) is ok


@pytest.mark.parametrize(
    ("text", "language"),
    [("good condition, only 3500 QAR", "en"), ("price QR 900, gd cond", "en"),
     ("$900 obo, clean", "en"), ("selling for 4.5k", "en"),
     ("للبيع نظيف جداً السعر 900 ريال", "ar")],
)  # fmt: skip
def test_validation_rejects_written_prices(facts, text, language):
    f = next(f for f in facts if f.language == language)
    title = "Nice phone for sale" if language == "en" else "للبيع جوال نظيف"
    assert validate_text(f, title, text) == "mentions a price"


def test_fingerprint_changes_with_facts(facts):
    f = facts[0]
    before = facts_fingerprint(f)
    f.attributes = {**f.attributes, "color": "something else"}
    assert facts_fingerprint(f) != before


class FakeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    async def generate_json(self, *, system, prompt, schema, thinking_level="low"):
        self.prompts.append(prompt)
        return JsonResult(json.dumps(self.payload, ensure_ascii=False), 10, 10, 0)


async def test_gemini_writer_keeps_valid_items_and_drops_bad_ones(facts):
    batch = [f for f in facts if f.language == "en"][:3]
    payload = {
        "items": [
            {"ref": "1", "title": "Clean phone for sale", "description": "barely used, w/ box"},
            {"ref": "2", "title": "Cheap!!", "description": "only 900 QAR, good condition"},
            {"ref": "99", "title": "Invented item", "description": "not in the batch at all"},
        ]
    }
    writer = GeminiWriter(FakeClient(payload))
    out = await writer.write(batch)
    assert list(out) == [batch[0].external_id]
    report = writer.last_report
    assert report.rejected["mentions a price"] == 1
    assert report.rejected["unknown or repeated ref"] == 1
    assert report.rejected["missing"] == 1  # ref 3 never returned


async def test_gemini_prompt_hides_omitted_facts(facts):
    f = next(f for f in facts if f.omit)
    client = FakeClient({"items": []})
    await GeminiWriter(client).write([f])
    sent = json.loads(client.prompts[0])["items"][0]
    assert not set(f.omit) & set(sent["attributes"])
    assert "price" not in json.dumps(sent).lower().replace("price_period", "")
