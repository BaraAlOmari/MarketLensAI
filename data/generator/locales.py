"""Locale profiles: where listings are, which languages and currencies they use."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Locale:
    code: str
    # General (non-property) listing locations: (label, weight)
    locations: tuple[tuple[str, float], ...]
    # Property areas: name -> (city, rent tier 1..4, freehold i.e. sale allowed)
    property_areas: dict[str, tuple[str, int, bool]]
    languages: dict[str, float]  # en / ar / mixed
    currency_mix: dict[str, float]
    first_names: tuple[str, ...]
    last_initials: str = "ABDFHKMNRSTZ"
    business_words: tuple[tuple[str, ...], tuple[str, ...]] = field(
        default=(
            ("Golden", "Pearl", "Desert", "Crescent", "Falcon", "Oasis", "Lagoon", "Sidra"),
            ("Gate", "Line", "Point", "Star", "Bay", "Key", "Way", "Crown"),
        )
    )


QATAR = Locale(
    code="qa",
    locations=(
        ("Al Sadd, Doha", 8),
        ("West Bay, Doha", 6),
        ("The Pearl, Doha", 6),
        ("Lusail", 7),
        ("Al Waab, Doha", 5),
        ("Old Airport, Doha", 5),
        ("Bin Mahmoud, Doha", 4),
        ("Najma, Doha", 4),
        ("Msheireb, Doha", 3),
        ("Al Duhail, Doha", 3),
        ("Al Gharrafa, Al Rayyan", 4),
        ("Muaither, Al Rayyan", 3),
        ("Al Rayyan", 5),
        ("Al Wakrah", 5),
        ("Umm Salal", 2),
        ("Al Khor", 2),
        ("Madinat Khalifa, Doha", 3),
        ("Abu Hamour, Doha", 3),
    ),
    property_areas={
        "The Pearl": ("Doha", 4, True),
        "West Bay": ("Doha", 4, True),
        "Lusail": ("Lusail", 4, True),
        "Msheireb": ("Doha", 4, False),
        "Al Qassar": ("Doha", 3, True),
        "Al Sadd": ("Doha", 3, False),
        "Bin Mahmoud": ("Doha", 2, False),
        "Najma": ("Doha", 1, False),
        "Old Airport": ("Doha", 2, False),
        "Al Mansoura": ("Doha", 1, False),
        "Al Waab": ("Doha", 3, False),
        "Al Thumama": ("Doha", 2, False),
        "Ain Khaled": ("Doha", 2, False),
        "Abu Hamour": ("Doha", 2, False),
        "Al Duhail": ("Doha", 2, False),
        "Al Gharrafa": ("Al Rayyan", 2, False),
        "Muaither": ("Al Rayyan", 1, False),
        "Al Wakrah": ("Al Wakrah", 2, False),
        "Umm Salal": ("Umm Salal", 1, False),
        "Al Khor": ("Al Khor", 1, True),
    },
    languages={"en": 0.60, "ar": 0.30, "mixed": 0.10},
    currency_mix={"QAR": 0.88, "USD": 0.12},
    first_names=(
        "Ahmed",
        "Mohammed",
        "Khalid",
        "Abdullah",
        "Hamad",
        "Fatima",
        "Mariam",
        "Noora",
        "Aisha",
        "Yousef",
        "Omar",
        "Salman",
        "Rashid",
        "Huda",
        "Layla",
        "Rajesh",
        "Arjun",
        "Priya",
        "Anil",
        "Joseph",
        "Maria",
        "Grace",
        "Jomar",
        "Ana",
        "Imran",
        "Bilal",
        "Ayesha",
        "Hassan",
        "Tariq",
        "Sara",
        "James",
        "Daniel",
        "Emma",
        "Olivia",
        "Karim",
        "Nadia",
        "Ravi",
        "Suresh",
        "Kamal",
        "Lina",
    ),  # fmt: skip
)

US = Locale(
    code="us",
    locations=(
        ("Austin, TX", 5),
        ("Brooklyn, NY", 5),
        ("Seattle, WA", 4),
        ("San Diego, CA", 4),
        ("Chicago, IL", 5),
        ("Denver, CO", 3),
        ("Miami, FL", 4),
    ),
    property_areas={
        "Downtown Austin": ("Austin", 4, True),
        "East Austin": ("Austin", 3, True),
        "Williamsburg": ("Brooklyn", 4, True),
        "Bushwick": ("Brooklyn", 3, True),
        "Capitol Hill": ("Seattle", 3, True),
        "Logan Square": ("Chicago", 2, True),
        "Little Havana": ("Miami", 2, True),
    },
    languages={"en": 1.0},
    currency_mix={"USD": 1.0},
    first_names=(
        "James",
        "Emily",
        "Michael",
        "Sarah",
        "David",
        "Jessica",
        "Chris",
        "Ashley",
        "Daniel",
        "Megan",
        "Carlos",
        "Sofia",
        "Kevin",
        "Rachel",
        "Brian",
        "Laura",
    ),  # fmt: skip
)

LOCALES = {loc.code: loc for loc in (QATAR, US)}
