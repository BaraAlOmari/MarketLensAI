"""Offline template writer: a hand-written phrase bank in English and Gulf Arabic.

Deterministic per listing (seeded by external_id), so reruns produce identical text.
Text never states a price; the structured price field is the only source of truth.
"""

import hashlib
import random
import re

from generator.facts import ListingFacts
from generator.writers import ListingText, TextWriter

# ---------------------------------------------------------------- shared vocabulary

COND_EN = {
    "new": ["brand new", "brand new sealed", "new, never used", "new in box", "BNIB"],
    "like_new": ["like new", "barely used", "mint condition", "used only a few weeks",
                 "excellent condition, like new", "9.5/10 condition"],
    "good": ["good condition", "used but well kept", "very clean", "normal usage",
             "minor scratches, works perfect", "good cond"],
    "fair": ["fair condition", "some scratches and dents", "visible wear", "used, works fine",
             "a few marks here and there"],
    "poor": ["needs repair", "screen cracked", "for parts or repair", "has issues, see details",
             "heavily used"],
}  # fmt: skip
COND_AR = {
    "new": ["جديد بالكرتون", "جديد مسكر", "جديد لم يستخدم", "جديد ما انفتح"],
    "like_new": ["شبه جديد", "استخدام بسيط جداً", "نظيف مثل الجديد", "استعمال شهر بس"],
    "good": ["حالته جيدة", "نظيف ما فيه شي", "استعمال عادي ونظيف", "فيه خدوش بسيطة ما تبين"],
    "fair": ["حالته مقبولة", "فيه خدوش واضحة", "استعمال واضح بس شغال تمام", "فيه آثار استخدام"],
    "poor": ["يحتاج تصليح", "للقطع أو التصليح", "الشاشة مكسورة", "فيه عطل"],
}
COND_SHORT_EN = {"new": "NEW", "like_new": "like new", "good": "good cond", "fair": "used",
                 "poor": "for repair"}  # fmt: skip

COLOR_AR = {
    "black": "أسود", "white": "أبيض", "blue": "أزرق", "green": "أخضر", "gray": "رمادي",
    "silver": "فضي", "purple": "بنفسجي", "red": "أحمر", "beige": "بيج", "brown": "بني",
    "navy": "كحلي", "cream": "كريمي", "pearl white": "أبيض لؤلؤي", "natural titanium":
    "تيتانيوم طبيعي", "desert titanium": "تيتانيوم صحراوي", "titanium black": "تيتانيوم أسود",
    "titanium gray": "تيتانيوم رمادي", "icy blue": "أزرق ثلجي", "mint": "نعناعي",
}  # fmt: skip

AREA_AR = {
    "The Pearl": "اللؤلؤة", "West Bay": "الخليج الغربي", "Lusail": "لوسيل", "Msheireb": "مشيرب",
    "Al Qassar": "القصار", "Al Sadd": "السد", "Bin Mahmoud": "فريج بن محمود", "Najma": "نجمة",
    "Old Airport": "المطار القديم", "Al Mansoura": "المنصورة", "Al Waab": "الوعب",
    "Al Thumama": "الثمامة", "Ain Khaled": "عين خالد", "Abu Hamour": "أبو هامور",
    "Al Duhail": "الدحيل", "Al Gharrafa": "الغرافة", "Muaither": "معيذر", "Al Wakrah": "الوكرة",
    "Umm Salal": "أم صلال", "Al Khor": "الخور", "Al Rayyan": "الريان", "Doha": "الدوحة",
    "Madinat Khalifa": "مدينة خليفة",
}  # fmt: skip

FURNITURE_AR = {
    "L-shaped sofa": "كنب على شكل L", "3-seater sofa": "كنب ثلاثي", "king bed frame": "سرير كنج",
    "queen bed with mattress": "سرير كوين مع المرتبة", "mattress": "مرتبة",
    "dining table set": "طاولة طعام مع الكراسي", "wardrobe": "كبت ملابس",
    "office chair": "كرسي مكتب", "study desk": "مكتب دراسة", "TV unit": "طاولة تلفزيون",
    "coffee table": "طاولة وسط", "recliner": "كرسي استرخاء", "majlis set": "مجلس عربي",
    "bookshelf": "مكتبة كتب", "kids bunk bed": "سرير دورين للأطفال",
    "outdoor patio set": "جلسة خارجية",
}  # fmt: skip

PTYPE_AR = {"apartment": "شقة", "studio": "استوديو", "penthouse": "بنتهاوس", "duplex": "دوبلكس",
            "villa": "فيلا", "townhouse": "تاون هاوس", "compound villa": "فيلا في كمباوند"}  # fmt: skip
FURNISHED_EN = {"furnished": "fully furnished", "semi-furnished": "semi furnished",
                "unfurnished": "unfurnished"}  # fmt: skip
FURNISHED_AR = {"furnished": "مفروشة بالكامل", "semi-furnished": "نص فرش",
                "unfurnished": "بدون فرش"}  # fmt: skip
AMENITY_AR = {"pool": "مسبح", "gym": "جيم", "parking": "موقف سيارات", "balcony": "بلكونة",
              "sea view": "إطلالة على البحر", "security": "حراسة 24 ساعة",
              "kids play area": "منطقة ألعاب للأطفال", "maid room": "غرفة خادمة"}  # fmt: skip
CATEGORY_NOUN_AR = {"phones": ["جوال", "تلفون", "موبايل"], "laptops": ["لابتوب", "لابتوب"],
                    "cars": ["سيارة", "سيارة"]}  # fmt: skip

CLOSERS_EN = ["price negotiable", "final price", "serious buyers only", "whatsapp only",
              "call or whatsapp", "no lowballers pls", "pickup from {area}", "can deliver",
              "first come first serve", "DM for more pics"]  # fmt: skip
CLOSERS_AR = ["السعر قابل للتفاوض", "السعر نهائي", "للجادين فقط", "واتساب فقط", "التواصل واتساب",
              "بدون مساومة", "الاستلام من {area}", "التوصيل متوفر", "اللي يبي صور زيادة يتواصل"]  # fmt: skip
REASONS_EN = ["leaving Qatar soon", "upgraded so selling this one", "moving to a new place",
              "don't use it anymore", "got it as a gift, already have one", "relocating, must go"]  # fmt: skip
REASONS_AR = ["مسافر ونهائي", "بسبب السفر", "غيرت وأبي أبيعه", "ما أحتاجه", "جاني هدية وعندي واحد",
              "بنتقل من البيت"]  # fmt: skip
OPENERS_EN = ["Selling my", "For sale:", "Up for sale", "Selling", "Urgent sale -", ""]
OPENERS_AR = ["للبيع", "للبيع عاجل", "معروض للبيع", "للبيع"]
# Same length as OPENERS_AR so rng.choice consumes the same randomness for every listing.
OPENERS_AR_RENT = ["للإيجار", "للإيجار فوراً", "متاح للإيجار", "للإيجار"]

ABBREVIATIONS = [
    (r"\bwith\b", "w/"), (r"\bcondition\b", "cond"), (r"\bgood\b", "gd"), (r"\bplease\b", "pls"),
    (r"\bnegotiable\b", "neg"), (r"\boriginal\b", "org"), (r"\bkilometers\b", "km"),
    (r"\bexcellent\b", "exc"), (r"\bwarranty\b", "warr"), (r"\bbedrooms?\b", "BR"),
    (r"\bbathrooms?\b", "bath"), (r"\bapartment\b", "apt"), (r"\bfurnished\b", "furn"),
    (r"\bavailable\b", "avail"), (r"\bautomatic\b", "auto"), (r"\bthe\b", ""),
]  # fmt: skip
AR_INFORMAL = [("أ", "ا"), ("إ", "ا"), ("ة ", "ه "), ("ى ", "ي ")]
EMOJI = ["🔥", "✅", "💯", "📱", "🚗", "🏠", "👌", "⭐", "📍", "💥"]


def _rng(f: ListingFacts) -> random.Random:
    return random.Random(int(hashlib.sha256(f.external_id.encode()).hexdigest()[:12], 16))


def _area_name(location: str) -> str:
    return location.split(",")[0].strip()


def _ar_area(name: str, rng: random.Random) -> str:
    return AREA_AR.get(name, name) if rng.random() < 0.7 else name


def _storage(gb: int) -> str:
    return f"{gb // 1024}TB" if gb >= 1024 else f"{gb}GB"


def _num_ar(n: int | float) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


# ---------------------------------------------------------------- spec sentences


def specs_en(f: ListingFacts, rng: random.Random) -> list[str]:
    a = {k: v for k, v in f.attributes.items() if k not in f.omit}
    out: list[str] = []
    if f.category == "phones":
        if "storage_gb" in a:
            out.append(f"{_storage(a['storage_gb'])} storage")
        if "color" in a:
            out.append(f"color {a['color']}")
        if "battery_health" in a:
            out.append(f"battery health {a['battery_health']}%")
        if a.get("box_included"):
            out.append(rng.choice(["comes with box", "comes w/ box and cable", "full box"]))
        if a.get("warranty"):
            out.append(
                "still under apple care / warranty" if f.brand == "Apple" else "warranty left"
            )
        if "sim" in a:
            out.append(a["sim"])
    elif f.category == "laptops":
        parts = [f"{a['ram_gb']}GB RAM" if "ram_gb" in a else "",
                 f"{_storage(a['storage_gb'])} SSD" if "storage_gb" in a else "",
                 a.get("cpu", ""), a.get("gpu", "")]  # fmt: skip
        out.append(", ".join(p for p in parts if p))
        if "screen_in" in a:
            out.append(f'{a["screen_in"]}" screen')
        if "battery_cycles" in a:
            out.append(f"battery cycle count {a['battery_cycles']}")
        if a.get("charger_included"):
            out.append("original charger included")
        if "year" in a:
            out.append(f"bought {a['year']}")
    elif f.category == "cars":
        if "mileage_km" in a:
            out.append(f"{a['mileage_km']:,} km")
        if "trim" in a:
            out.append(f"{a['trim']} option")
        out.append(f"{a.get('transmission', 'automatic')}, {a.get('fuel', 'petrol')}")
        if "cylinders" in a:
            out.append(f"{a['cylinders']} cylinder")
        if "color" in a:
            out.append(f"{a['color']} color")
        if a.get("gcc_specs"):
            out.append("GCC specs")
        if a.get("accident_free"):
            out.append("accident free")
        if a.get("service_history") == "agency":
            out.append("full agency service history")
    elif f.category == "furniture":
        if "material" in a:
            out.append(f"{a['material']}")
        if "color" in a:
            out.append(f"{a['color']} color")
        if "size" in a:
            out.append(a["size"])
        if a.get("delivery_available"):
            out.append("delivery possible for extra")
    else:  # apartments / villas
        beds = a.get("bedrooms")
        if beds is not None and "bedrooms" not in f.omit:
            out.append("studio" if beds == 0 else f"{beds} bedrooms")
        if "bathrooms" in a:
            out.append(f"{a['bathrooms']} bathrooms")
        if "area_sqm" in a:
            out.append(f"{a['area_sqm']} sqm")
        if "furnished" in a:
            out.append(FURNISHED_EN[a["furnished"]])
        if "floor" in a:
            out.append(f"floor {a['floor']}")
        for flag, text in (("private_pool", "private pool"), ("maid_room", "maid room"),
                           ("garden", "garden")):  # fmt: skip
            if a.get(flag):
                out.append(text)
        if a.get("amenities"):
            out.append("amenities: " + ", ".join(a["amenities"]))
        if a.get("bills_included"):
            out.append("kahramaa (electricity & water) included")
    return [s for s in out if s]


def specs_ar(f: ListingFacts, rng: random.Random) -> list[str]:
    a = {k: v for k, v in f.attributes.items() if k not in f.omit}
    out: list[str] = []
    if f.category == "phones":
        if "storage_gb" in a:
            out.append(f"سعة {_storage(a['storage_gb'])}" if rng.random() < 0.5
                       else f"{a['storage_gb']} جيجا")  # fmt: skip
        if "color" in a:
            out.append(f"اللون {COLOR_AR.get(a['color'], a['color'])}")
        if "battery_health" in a:
            out.append(f"البطارية {a['battery_health']}%")
        if a.get("box_included"):
            out.append(rng.choice(["مع الكرتون والشاحن", "مع كامل أغراضه", "مع الكرتون"]))
        if a.get("warranty"):
            out.append("عليه ضمان")
    elif f.category == "laptops":
        if "ram_gb" in a:
            out.append(f"رام {a['ram_gb']} جيجا")
        if "storage_gb" in a:
            out.append(f"هارد {_storage(a['storage_gb'])} SSD")
        if "cpu" in a:
            out.append(f"معالج {a['cpu']}")
        if "gpu" in a:
            out.append(f"كرت شاشة {a['gpu']}")
        if a.get("charger_included"):
            out.append("مع الشاحن الأصلي")
    elif f.category == "cars":
        if "year" in a:
            out.append(f"موديل {a['year']}")
        if "mileage_km" in a:
            out.append(f"ممشى {_num_ar(a['mileage_km'])} كم")
        if a.get("transmission") == "automatic":
            out.append("قير أوتوماتيك")
        elif a.get("transmission") == "manual":
            out.append("قير عادي")
        if "cylinders" in a:
            out.append(f"{a['cylinders']} سلندر")
        if "color" in a:
            out.append(f"اللون {COLOR_AR.get(a['color'], a['color'])}")
        if a.get("gcc_specs"):
            out.append("خليجي")
        if a.get("accident_free"):
            out.append("بدون حوادث")
        if a.get("service_history") == "agency":
            out.append("صيانة وكالة")
        if a.get("fuel") == "hybrid":
            out.append("هايبرد")
        elif a.get("fuel") == "electric":
            out.append("كهربائية")
    elif f.category == "furniture":
        if "color" in a:
            out.append(f"اللون {COLOR_AR.get(a['color'], a['color'])}")
        if "size" in a:
            out.append(f"المقاس {a['size']}")
        if a.get("delivery_available"):
            out.append("التوصيل متوفر برسوم")
    else:
        beds = a.get("bedrooms")
        if beds:
            out.append(f"{beds} غرف نوم")
        if "bathrooms" in a:
            out.append(f"{a['bathrooms']} حمامات")
        if "area_sqm" in a:
            out.append(f"المساحة {a['area_sqm']} متر مربع")
        if "furnished" in a:
            out.append(FURNISHED_AR[a["furnished"]])
        if "floor" in a:
            out.append(f"الدور {a['floor']}")
        for flag, text in (("private_pool", "مسبح خاص"), ("maid_room", "غرفة خادمة"),
                           ("garden", "حديقة")):  # fmt: skip
            if a.get(flag):
                out.append(text)
        for amenity in a.get("amenities", []):
            out.append(AMENITY_AR[amenity])
        if a.get("bills_included"):
            out.append("شامل الكهرباء والماء")
    return out


# ---------------------------------------------------------------- titles


def title_en(f: ListingFacts, rng: random.Random) -> str:
    a = f.attributes
    cond = COND_SHORT_EN.get(f.condition or "", "")
    if f.category == "phones":
        storage = "" if "storage_gb" in f.omit else _storage(a["storage_gb"])
        options = [
            f"{f.model} {storage} {cond}",
            f"{f.model} {storage}",
            f"{f.model} - {cond}",
            f"{(f.model or '').lower()} {storage.lower()}",
            f"{f.brand} {f.model} {storage}",
        ]
    elif f.category == "laptops":
        options = [
            f"{f.brand} {f.model}",
            f"{f.model} {a.get('ram_gb', '')}GB {cond}",
            f"{f.brand} {f.model} for sale",
            f"{(f.model or '').lower()} laptop",
        ]
    elif f.category == "cars":
        year = "" if "year" in f.omit else str(a["year"])
        options = [
            f"{f.brand} {f.model} {year}",
            f"{year} {f.model} {a.get('trim', '')}",
            f"{f.model} {year} {'GCC' if a.get('gcc_specs') else ''}",
            f"{f.brand} {f.model} for sale",
        ]
    elif f.category == "furniture":
        item = a["item_type"]
        options = [
            f"{f.brand + ' ' if f.brand else ''}{item}",
            f"{item} for sale",
            f"{item} - {cond}",
            f"{a.get('color', '')} {item}",
        ]
    else:
        beds, ptype, area = a["bedrooms"], a["property_type"], a["neighborhood"]
        what = "Studio" if beds == 0 else f"{beds}BR {ptype}"
        verb = "for rent" if f.listing_type == "rent" else "for sale"
        options = [
            f"{what} {verb} in {area}",
            f"{FURNISHED_EN[a['furnished']]} {what} {area}",
            f"Spacious {what} - {area}",
            f"{what} {verb} {area}",
        ]
    title = re.sub(r"\s+", " ", rng.choice(options)).strip(" -")
    return title if len(title) >= 8 else f"{f.brand or ''} {title}".strip()


def title_ar(f: ListingFacts, rng: random.Random) -> str:
    a = f.attributes
    cond = rng.choice(COND_AR[f.condition]) if f.condition else ""
    if f.category in ("phones", "laptops", "cars"):
        noun = rng.choice(CATEGORY_NOUN_AR[f.category])
        extra = (f"موديل {a['year']}" if f.category == "cars" and "year" not in f.omit
                 else (_storage(a["storage_gb"]) if "storage_gb" in a and "storage_gb" not in f.omit
                       else ""))  # fmt: skip
        options = [
            f"للبيع {f.model} {extra}",
            f"{noun} {f.model} {cond}",
            f"{f.brand} {f.model} {extra} للبيع",
        ]
    elif f.category == "furniture":
        item = FURNITURE_AR[a["item_type"]]
        options = [f"للبيع {item}", f"{item} {cond}", f"{item} {f.brand or ''} للبيع"]
    else:
        ptype = PTYPE_AR[a["property_type"]]
        area = _ar_area(a["neighborhood"], rng)
        verb = "للإيجار" if f.listing_type == "rent" else "للبيع"
        beds = "" if a["bedrooms"] == 0 else f"{a['bedrooms']} غرف"
        options = [
            f"{ptype} {verb} في {area}",
            f"{ptype} {beds} {verb} - {area}",
            f"{verb} {ptype} {beds} {FURNISHED_AR[a['furnished']]} {area}",
        ]
    return re.sub(r"\s+", " ", rng.choice(options)).strip(" -")


# ---------------------------------------------------------------- style transforms


def add_typos(text: str, rng: random.Random, rate: float = 0.12) -> str:
    def mangle(word: str) -> str:
        if len(word) < 5 or not word.isalpha() or rng.random() > rate:
            return word
        i = rng.randrange(1, len(word) - 1)
        op = rng.choice(("swap", "drop", "double"))
        if op == "swap":
            return word[:i] + word[i + 1] + word[i] + word[i + 2 :]
        if op == "drop":
            return word[:i] + word[i + 1 :]
        return word[:i] + word[i] + word[i:]

    return re.sub(r"[A-Za-z]+", lambda m: mangle(m.group()), text)


def abbreviate(text: str) -> str:
    for pattern, repl in ABBREVIATIONS:
        text = re.sub(pattern, repl, text, flags=re.I)
    return re.sub(r" {2,}", " ", text)


def informal_ar(text: str, rng: random.Random) -> str:
    for a, b in AR_INFORMAL:
        if rng.random() < 0.5:
            text = text.replace(a, b)
    return text


# ---------------------------------------------------------------- assembly


class TemplateWriter(TextWriter):
    name = "template"

    async def write(self, batch: list[ListingFacts]) -> dict[str, ListingText]:
        return {f.external_id: self.write_one(f) for f in batch}

    def write_one(self, f: ListingFacts) -> ListingText:
        rng = _rng(f)
        if f.language == "en":
            title, desc = self._english(f, rng)
        elif f.language == "ar":
            title, desc = self._arabic(f, rng)
        else:
            title, desc = self._mixed(f, rng)
        return ListingText(title=title[:140], description=desc[:1500], writer=self.name)

    def _english(self, f: ListingFacts, rng: random.Random) -> tuple[str, str]:
        styles = set(f.styles)
        title = title_en(f, rng)
        specs = specs_en(f, rng)
        rng.shuffle(specs)
        area = _area_name(f.location)
        parts: list[str] = []
        if f.category not in ("apartments", "villas"):
            opener = rng.choice(OPENERS_EN)
            what = f.item_label if f.category == "furniture" else (f.model or f.item_label)
            parts.append(f"{opener} {what}".strip())
            parts.append(rng.choice(COND_EN[f.condition]))
        else:
            a = f.attributes
            what = (
                "studio" if a["bedrooms"] == 0 else f"{a['bedrooms']} bedroom {a['property_type']}"
            )
            verb = "available for rent" if f.listing_type == "rent" else "for sale"
            adjective = rng.choice(("Nice", "Spacious", "Lovely", ""))
            parts.append(f"{adjective} {what} {verb} in {area}".strip())
            if f.listing_type == "rent":
                parts.append("rent paid monthly" if f.price_period == "month"
                             else "yearly contract, cheques accepted")  # fmt: skip
        keep = 1 if "terse" in styles else (len(specs) if "detailed" in styles else 3)
        parts.extend(specs[:keep])
        if "casual" in styles or rng.random() < 0.2:
            parts.append(rng.choice(REASONS_EN))
        if "terse" not in styles:
            parts.append(rng.choice(CLOSERS_EN).format(area=area))
        sep = rng.choice((". ", ", ", "\n", " - ")) if "terse" not in styles else ", "
        desc = sep.join(p for p in parts if p)
        if "abbrev" in styles:
            desc, title = abbreviate(desc), abbreviate(title)
        if "typos" in styles:
            desc = add_typos(desc, rng)
            title = add_typos(title, rng, rate=0.08)
        if "caps" in styles:
            title = title.upper() + rng.choice(("!!", "!!!", " !!", ""))
        elif rng.random() < 0.35:
            title = title.lower()
        if "emoji" in styles:
            title = f"{rng.choice(EMOJI)} {title}"
            desc = f"{desc} {rng.choice(EMOJI)}{rng.choice(EMOJI)}"
        return title, desc

    def _arabic(self, f: ListingFacts, rng: random.Random) -> tuple[str, str]:
        styles = set(f.styles)
        title = title_ar(f, rng)
        specs = specs_ar(f, rng)
        rng.shuffle(specs)
        area = _ar_area(_area_name(f.location), rng)
        parts: list[str] = []
        if f.category not in ("apartments", "villas"):
            what = (FURNITURE_AR[f.attributes["item_type"]] if f.category == "furniture"
                    else f"{f.brand} {f.model}")  # fmt: skip
            parts.append(f"{rng.choice(OPENERS_AR)} {what}")
            parts.append(rng.choice(COND_AR[f.condition]))
        else:
            parts.append(title)
            if f.listing_type == "rent":
                parts.append("الإيجار شهري" if f.price_period == "month" else "عقد سنوي")
        keep = 1 if "terse" in styles else (len(specs) if "detailed" in styles else 3)
        parts.extend(specs[:keep])
        if "casual" in styles or rng.random() < 0.25:
            parts.append(rng.choice(REASONS_AR))
        if "terse" not in styles:
            parts.append(rng.choice(CLOSERS_AR).format(area=area))
        desc = rng.choice(("، ", " - ", "\n", " ")).join(parts)
        if "typos" in styles or "abbrev" in styles or rng.random() < 0.3:
            desc = informal_ar(desc, rng)
        if "emoji" in styles:
            title = f"{rng.choice(EMOJI)} {title}"
            desc = f"{desc} {rng.choice(EMOJI)}"
        if "caps" in styles:
            title = f"{title} !!!"
        return title, desc

    def _mixed(self, f: ListingFacts, rng: random.Random) -> tuple[str, str]:
        """Arabic sentences with English model names and specs, as Gulf sellers often write."""
        en_title, en_desc = self._english(f, rng)
        ar_title, ar_desc = self._arabic(f, rng)
        specs = specs_en(f, rng)[:2]
        openers = OPENERS_AR_RENT if f.listing_type == "rent" else OPENERS_AR
        title = rng.choice((en_title, f"{en_title} {rng.choice(openers)}", ar_title))
        desc = f"{ar_desc}\n{' / '.join(specs)}" if specs else f"{ar_desc}\n{en_desc[:120]}"
        if title == ar_title and not re.search(r"[A-Za-z]", title + desc):
            desc = f"{desc} {f.item_label}"
        return title, desc
