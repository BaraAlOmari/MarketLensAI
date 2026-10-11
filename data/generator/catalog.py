"""Synthetic product catalog. Prices are approximate new prices in QAR (synthetic, not quotes).

Only models released up to 2025 are included: later launches were not verified.
"""

from dataclasses import dataclass

DATASET_YEAR = 2026


@dataclass(frozen=True)
class Phone:
    brand: str
    model: str
    year: int
    base_qar: int  # smallest storage tier, new
    storages: tuple[int, ...]
    colors: tuple[str, ...]


@dataclass(frozen=True)
class Laptop:
    brand: str
    model: str
    year: int
    base_qar: int
    cpu: str
    rams: tuple[int, ...]
    storages: tuple[int, ...]
    screen_in: float
    gpu: str | None = None


@dataclass(frozen=True)
class Car:
    brand: str
    model: str
    new_qar: int
    trims: tuple[str, ...]
    fuel: str = "petrol"
    cylinders: int | None = 4
    first_year: int = 2012


@dataclass(frozen=True)
class FurnitureItem:
    item_type: str
    new_qar_range: tuple[int, int]
    materials: tuple[str, ...]
    brands: tuple[str, ...]  # "" means unbranded
    sizes: tuple[str, ...] = ()


APPLE_COLORS = ("black", "white", "natural titanium", "blue", "desert titanium", "silver")
SAMSUNG_COLORS = ("titanium black", "titanium gray", "silver", "icy blue", "mint", "navy")
GENERIC_COLORS = ("black", "white", "blue", "green", "gray", "silver", "purple")

PHONES = (
    Phone("Apple", "iPhone 17 Pro Max", 2025, 5099, (256, 512, 1024, 2048), APPLE_COLORS),
    Phone("Apple", "iPhone 17 Pro", 2025, 4599, (256, 512, 1024), APPLE_COLORS),
    Phone("Apple", "iPhone 17", 2025, 3399, (256, 512), APPLE_COLORS),
    Phone("Apple", "iPhone Air", 2025, 4299, (256, 512, 1024), APPLE_COLORS),
    Phone("Apple", "iPhone 16 Pro Max", 2024, 4999, (256, 512, 1024), APPLE_COLORS),
    Phone("Apple", "iPhone 16 Pro", 2024, 4299, (128, 256, 512, 1024), APPLE_COLORS),
    Phone("Apple", "iPhone 16", 2024, 3399, (128, 256, 512), APPLE_COLORS),
    Phone("Apple", "iPhone 15 Pro Max", 2023, 4999, (256, 512, 1024), APPLE_COLORS),
    Phone("Apple", "iPhone 15 Pro", 2023, 4299, (128, 256, 512), APPLE_COLORS),
    Phone("Apple", "iPhone 15", 2023, 3399, (128, 256, 512), APPLE_COLORS),
    Phone("Apple", "iPhone 14", 2022, 3199, (128, 256), APPLE_COLORS),
    Phone("Apple", "iPhone 13", 2021, 2999, (128, 256), APPLE_COLORS),
    Phone("Samsung", "Galaxy S25 Ultra", 2025, 4999, (256, 512, 1024), SAMSUNG_COLORS),
    Phone("Samsung", "Galaxy S25", 2025, 3199, (128, 256), SAMSUNG_COLORS),
    Phone("Samsung", "Galaxy S24 Ultra", 2024, 4799, (256, 512), SAMSUNG_COLORS),
    Phone("Samsung", "Galaxy S24", 2024, 2999, (128, 256), SAMSUNG_COLORS),
    Phone("Samsung", "Galaxy Z Fold7", 2025, 6999, (256, 512, 1024), SAMSUNG_COLORS),
    Phone("Samsung", "Galaxy Z Flip7", 2025, 3999, (256, 512), SAMSUNG_COLORS),
    Phone("Samsung", "Galaxy A56", 2025, 1499, (128, 256), GENERIC_COLORS),
    Phone("Google", "Pixel 10 Pro", 2025, 3999, (128, 256, 512), GENERIC_COLORS),
    Phone("Google", "Pixel 10", 2025, 2999, (128, 256), GENERIC_COLORS),
    Phone("Google", "Pixel 9", 2024, 2799, (128, 256), GENERIC_COLORS),
    Phone("Xiaomi", "Xiaomi 15 Ultra", 2025, 4299, (256, 512), GENERIC_COLORS),
    Phone("Xiaomi", "Redmi Note 14 Pro", 2025, 1199, (256, 512), GENERIC_COLORS),
    Phone("Huawei", "Pura 70 Pro", 2024, 3999, (256, 512), GENERIC_COLORS),
    Phone("Huawei", "Mate X6", 2025, 7499, (512, 1024), GENERIC_COLORS),
    Phone("OnePlus", "OnePlus 13", 2025, 3299, (256, 512), GENERIC_COLORS),
)

LAPTOPS = (
    Laptop("Apple", "MacBook Air 13 M4", 2025, 3999, "Apple M4", (16, 24, 32), (256, 512, 1024), 13.6),
    Laptop("Apple", "MacBook Air 15 M4", 2025, 4799, "Apple M4", (16, 24, 32), (256, 512, 1024), 15.3),
    Laptop("Apple", "MacBook Pro 14 M4 Pro", 2024, 7999, "Apple M4 Pro", (24, 48), (512, 1024, 2048), 14.2),
    Laptop("Apple", "MacBook Pro 16 M4 Max", 2024, 13999, "Apple M4 Max", (36, 48, 64), (1024, 2048), 16.2),
    Laptop("Apple", "MacBook Air 13 M2", 2022, 3699, "Apple M2", (8, 16), (256, 512), 13.6),
    Laptop("Apple", "MacBook Pro 14 M3", 2023, 6499, "Apple M3", (8, 16, 24), (512, 1024), 14.2),
    Laptop("Dell", "XPS 13", 2024, 5499, "Intel Core Ultra 7", (16, 32), (512, 1024), 13.4),
    Laptop("Dell", "XPS 14", 2024, 7299, "Intel Core Ultra 7", (16, 32), (512, 1024), 14.5, "RTX 4050"),
    Laptop("Dell", "Inspiron 15", 2023, 2399, "Intel Core i5", (8, 16), (256, 512), 15.6),
    Laptop("HP", "Spectre x360 14", 2024, 5999, "Intel Core Ultra 7", (16, 32), (512, 1024, 2048), 14.0),
    Laptop("HP", "Pavilion 15", 2023, 2199, "Intel Core i5", (8, 16), (256, 512), 15.6),
    Laptop("HP", "Victus 16", 2024, 3499, "AMD Ryzen 7", (16, 32), (512, 1024), 16.1, "RTX 4060"),
    Laptop("Lenovo", "ThinkPad X1 Carbon Gen 13", 2025, 6999, "Intel Core Ultra 7", (16, 32, 64), (512, 1024), 14.0),
    Laptop("Lenovo", "Legion 5", 2024, 4999, "AMD Ryzen 7", (16, 32), (512, 1024), 16.0, "RTX 4070"),
    Laptop("Lenovo", "IdeaPad Slim 5", 2024, 2599, "AMD Ryzen 5", (8, 16), (512,), 14.0),
    Laptop("ASUS", "ROG Zephyrus G14", 2025, 7499, "AMD Ryzen AI 9", (16, 32), (1024, 2048), 14.0, "RTX 5070"),
    Laptop("ASUS", "ROG Strix G16", 2024, 5999, "Intel Core i9", (16, 32), (1024,), 16.0, "RTX 4070"),
    Laptop("ASUS", "Zenbook 14 OLED", 2024, 3799, "Intel Core Ultra 5", (16, 32), (512, 1024), 14.0),
    Laptop("Acer", "Nitro V 15", 2024, 2899, "Intel Core i5", (8, 16), (512,), 15.6, "RTX 4050"),
    Laptop("MSI", "Katana 15", 2024, 3999, "Intel Core i7", (16, 32), (1024,), 15.6, "RTX 4060"),
    Laptop("Microsoft", "Surface Laptop 7", 2024, 4999, "Snapdragon X Elite", (16, 32), (512, 1024), 13.8),
)  # fmt: skip

CARS = (
    Car("Toyota", "Land Cruiser", 330_000, ("GXR", "VXR", "GR Sport"), cylinders=6),
    Car("Toyota", "Land Cruiser Prado", 220_000, ("TX", "TXL", "VX"), cylinders=4),
    Car("Toyota", "Camry", 115_000, ("LE", "SE", "GLE", "Grande"), fuel="hybrid"),
    Car("Toyota", "Corolla", 85_000, ("XLI", "GLI", "Hybrid")),
    Car("Toyota", "Hilux", 110_000, ("Single Cab", "Double Cab GLX", "Adventure")),
    Car("Toyota", "Fortuner", 145_000, ("EXR", "GXR", "VXR"), cylinders=6),
    Car("Nissan", "Patrol", 300_000, ("XE", "SE", "LE Platinum", "Nismo"), cylinders=6),
    Car("Nissan", "Sunny", 60_000, ("S", "SV", "SL")),
    Car("Nissan", "X-Trail", 115_000, ("S", "SV", "SL")),
    Car("Lexus", "LX 600", 520_000, ("Premier", "Luxury", "F Sport"), cylinders=6),
    Car("Lexus", "ES 350", 190_000, ("Premier", "Platinum", "F Sport"), cylinders=6),
    Car("Lexus", "RX 350", 260_000, ("Premier", "Platinum", "F Sport")),
    Car("Hyundai", "Elantra", 75_000, ("Smart", "Comfort", "N Line")),
    Car("Hyundai", "Tucson", 110_000, ("Smart", "Comfort", "Premium")),
    Car("Hyundai", "Santa Fe", 150_000, ("Smart", "Premium", "Calligraphy")),
    Car("Kia", "Sportage", 105_000, ("LX", "EX", "GT Line")),
    Car("Kia", "Pegas", 48_000, ("Base", "LX")),
    Car("Mitsubishi", "Pajero", 130_000, ("GLS", "GLX"), cylinders=6),
    Car("GMC", "Yukon", 300_000, ("SLE", "SLT", "Denali"), cylinders=8),
    Car("Chevrolet", "Tahoe", 280_000, ("LS", "LT", "High Country"), cylinders=8),
    Car("Ford", "Mustang", 200_000, ("EcoBoost", "GT", "Mach 1"), cylinders=8),
    Car("Mercedes-Benz", "G 63 AMG", 950_000, ("AMG",), cylinders=8, first_year=2015),
    Car("Mercedes-Benz", "C 200", 230_000, ("Avantgarde", "AMG Line")),
    Car("BMW", "X5", 380_000, ("xDrive40i", "M50i", "M Sport"), cylinders=6),
    Car("Land Rover", "Range Rover Sport", 450_000, ("SE", "HSE", "Autobiography"), cylinders=6),
    Car("Porsche", "Cayenne", 450_000, ("Base", "S", "Coupe", "Turbo"), cylinders=6),
    Car("Honda", "Accord", 110_000, ("LX", "Sport", "Touring")),
    Car("Honda", "Civic", 90_000, ("LX", "Sport", "RS")),
    Car("Tesla", "Model Y", 200_000, ("Long Range", "Performance"), fuel="electric", cylinders=None, first_year=2021),
    Car("BYD", "Seal", 160_000, ("Premium", "Performance"), fuel="electric", cylinders=None, first_year=2023),
    Car("MG", "ZS", 65_000, ("STD", "COM", "LUX"), first_year=2018),
    Car("Jetour", "T2", 115_000, ("Dashing", "Traveller"), first_year=2023),
)  # fmt: skip

FURNITURE = (
    FurnitureItem("L-shaped sofa", (2500, 9000), ("fabric", "leather", "velvet"), ("IKEA", "Home Centre", "Pan Emirates", "Marina Home", ""), ("5-seater", "6-seater", "7-seater")),
    FurnitureItem("3-seater sofa", (1200, 5500), ("fabric", "leather", "linen"), ("IKEA", "Home Centre", "Home Box", "Ashley", "")),
    FurnitureItem("king bed frame", (1500, 6000), ("wood", "upholstered", "metal"), ("IKEA", "Home Centre", "Pan Emirates", ""), ("180x200 cm", "200x200 cm")),
    FurnitureItem("queen bed with mattress", (1800, 5000), ("wood", "upholstered"), ("IKEA", "Home Box", "Danube Home", ""), ("160x200 cm",)),
    FurnitureItem("mattress", (600, 3500), ("memory foam", "spring", "hybrid"), ("IKEA", "Sleep Number", "King Koil", ""), ("single", "queen", "king")),
    FurnitureItem("dining table set", (1200, 7000), ("wood", "glass", "marble"), ("IKEA", "Home Centre", "Pan Emirates", "Marina Home", ""), ("4 chairs", "6 chairs", "8 chairs")),
    FurnitureItem("wardrobe", (800, 4500), ("wood", "MDF", "mirror sliding"), ("IKEA", "Home Centre", "Danube Home", ""), ("2-door", "3-door", "4-door")),
    FurnitureItem("office chair", (300, 5500), ("mesh", "leather"), ("IKEA", "Herman Miller", "Secretlab", "Ergohuman", "")),
    FurnitureItem("study desk", (300, 2500), ("wood", "metal", "glass"), ("IKEA", "Home Box", "")),
    FurnitureItem("TV unit", (400, 3000), ("wood", "MDF", "marble top"), ("IKEA", "Home Centre", "Pan Emirates", "")),
    FurnitureItem("coffee table", (250, 2500), ("wood", "glass", "marble"), ("IKEA", "Home Centre", "Marina Home", "")),
    FurnitureItem("recliner", (900, 4500), ("fabric", "leather"), ("Home Centre", "Ashley", "La-Z-Boy", "")),
    FurnitureItem("majlis set", (3000, 15000), ("fabric", "velvet"), ("", "Pan Emirates"), ("8 seats", "10 seats", "12 seats")),
    FurnitureItem("bookshelf", (200, 1500), ("wood", "metal"), ("IKEA", "Home Box", "")),
    FurnitureItem("kids bunk bed", (900, 3500), ("wood", "metal"), ("IKEA", "Home Centre", "")),
    FurnitureItem("outdoor patio set", (900, 6000), ("rattan", "aluminium", "wood"), ("IKEA", "Home Centre", "ACE", ""), ("4 seats", "6 seats")),
)  # fmt: skip

FURNITURE_COLORS = ("gray", "beige", "white", "black", "brown", "navy", "green", "cream")
CAR_COLORS = ("white", "black", "silver", "gray", "pearl white", "blue", "red", "beige")

# Property pricing in QAR by rent tier (1 = cheapest areas, 4 = premium).
APARTMENT_RENT_BY_BEDS = {0: 3500, 1: 5000, 2: 7000, 3: 9500, 4: 13000}  # tier-2 baseline, monthly
TIER_RENT_MULTIPLIER = {1: 0.75, 2: 1.0, 3: 1.25, 4: 1.6}
APARTMENT_SALE_PER_SQM = {1: 7000, 2: 8500, 3: 10500, 4: 13500}
VILLA_RENT_BY_BEDS = {3: 11000, 4: 14000, 5: 17000, 6: 21000, 7: 26000}
VILLA_SALE_PER_SQM = {1: 6000, 2: 7000, 3: 8500, 4: 11000}
