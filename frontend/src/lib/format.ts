import type { Condition, Filters, Listing } from "./chat";

// Labels for filters and card details, in English or Arabic. Data values (brands, models,
// places, colors, item types) are shown as listed. Prices always use English and Western
// digits, in both languages (project rule).

export type Lang = "en" | "ar";

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function formatAmount(value: string | number): string {
  return number.format(Math.round(Number(value)));
}

/** Price exactly as listed (currency kept), e.g. "2,100 QAR" or "8,000 QAR / month". */
export function formatPrice(
  listing: Pick<Listing, "price" | "currency" | "listing_type" | "price_period">,
) {
  const base = `${formatAmount(listing.price)} ${listing.currency.trim()}`;
  if (listing.listing_type === "rent" && listing.price_period !== "total") {
    return `${base} / ${listing.price_period}`;
  }
  return base;
}

const CONDITION: Record<Lang, Record<Condition, string>> = {
  en: { new: "New", like_new: "Like new", good: "Good", fair: "Fair", poor: "Poor" },
  ar: { new: "جديد", like_new: "شبه جديد", good: "جيد", fair: "مقبول", poor: "سيئ" },
};

export function conditionLabel(condition: Condition, lang: Lang = "en"): string {
  return CONDITION[lang][condition];
}

const CATEGORY: Record<Lang, Record<string, string>> = {
  en: {
    phones: "Phones",
    laptops: "Laptops",
    cars: "Cars",
    furniture: "Furniture",
    apartments: "Apartments",
    villas: "Villas",
  },
  ar: {
    phones: "هواتف",
    laptops: "لابتوبات",
    cars: "سيارات",
    furniture: "أثاث",
    apartments: "شقق",
    villas: "فلل",
  },
};

export function categoryLabel(category: string, lang: Lang = "en"): string {
  return CATEGORY[lang][category] ?? category;
}

const OR: Record<Lang, string> = { en: " or ", ar: " أو " };

function conditionsLabel(conditions: Condition[], lang: Lang): string {
  const key = [...conditions].sort().join(",");
  const named: Record<Lang, Record<string, string>> = {
    en: {
      "like_new,new": "Like new or better",
      "good,like_new": "Like new or good",
      "good,like_new,new": "Good or better",
      "fair,good,like_new,poor": "Used",
    },
    ar: {
      "like_new,new": "شبه جديد أو أفضل",
      "good,like_new": "شبه جديد أو جيد",
      "good,like_new,new": "جيد أو أفضل",
      "fair,good,like_new,poor": "مستعمل",
    },
  };
  return named[lang][key] ?? conditions.map((c) => CONDITION[lang][c]).join(OR[lang]);
}

function priceLabel(f: Filters, lang: Lang): string {
  const currency = f.currency ?? "QAR";
  const per = f.price_period === "month" ? " / month" : f.price_period === "year" ? " / year" : "";
  const amount = (v: string) => `${formatAmount(v)} ${currency}${per}`;
  if (f.min_price && f.max_price) {
    return `${formatAmount(f.min_price)}–${formatAmount(f.max_price)} ${currency}${per}`;
  }
  if (f.max_price)
    return lang === "ar" ? `أقل من ${amount(f.max_price)}` : `Under ${amount(f.max_price)}`;
  const min = f.min_price ?? "0";
  return lang === "ar" ? `أكثر من ${amount(min)}` : `Over ${amount(min)}`;
}

function sizeLabel(gb: number): string {
  return gb >= 1024 && gb % 1024 === 0 ? `${gb / 1024} TB` : `${gb} GB`;
}

/** "2 bedrooms" / "غرفتا نوم"; `short` gives the card form, "2 bed" / "غرفتان". */
export function bedroomsLabel(n: number, lang: Lang, short = false): string {
  if (n === 0) return lang === "ar" ? "استوديو" : "Studio";
  if (lang === "ar") {
    if (n === 1) return short ? "غرفة واحدة" : "غرفة نوم واحدة";
    if (n === 2) return short ? "غرفتان" : "غرفتا نوم";
    if (n <= 10) return short ? `${n} غرف` : `${n} غرف نوم`;
    return short ? `${n} غرفة` : `${n} غرفة نوم`;
  }
  return short ? `${n} bed` : `${n} bedroom${n === 1 ? "" : "s"}`;
}

const VALUE_AR: Record<string, string> = {
  furnished: "مفروشة",
  "semi-furnished": "نصف مفروشة",
  unfurnished: "غير مفروشة",
  apartment: "شقة",
  villa: "فيلا",
  "compound villa": "فيلا في كمباوند",
  studio: "استوديو",
  townhouse: "تاون هاوس",
  duplex: "دوبلكس",
  penthouse: "بنتهاوس",
  parking: "موقف سيارات",
  "kids play area": "منطقة ألعاب للأطفال",
  gym: "نادٍ رياضي",
  balcony: "شرفة",
  "maid room": "غرفة خادمة",
  security: "حراسة",
  "sea view": "إطلالة بحرية",
  pool: "مسبح",
};

/** A data value in the person's language when it is one of the fixed ones, else as listed. */
function value(v: unknown, lang: Lang): string {
  const s = String(v);
  if (lang === "ar") return VALUE_AR[s] ?? s;
  return s.replace(/^./, (c) => c.toUpperCase());
}

function attributeLabel(
  key: string,
  rule: NonNullable<Filters["attributes"]>[string],
  lang: Lang,
): string {
  const ar = lang === "ar";
  const eq = rule.eq;
  const min = rule.min !== undefined ? Number(rule.min) : undefined;
  const max = rule.max !== undefined ? Number(rule.max) : undefined;
  switch (key) {
    case "bedrooms":
      if (eq !== undefined) return bedroomsLabel(Number(eq), lang);
      return ar ? `${min}+ غرف نوم` : `${min}+ bedrooms`;
    case "mileage_km":
      return ar ? `أقل من ${formatAmount(max ?? 0)} كم` : `Under ${formatAmount(max ?? 0)} km`;
    case "year":
      if (min !== undefined && max !== undefined) return min === max ? `${min}` : `${min}–${max}`;
      if (min !== undefined) return ar ? `${min} أو أحدث` : `${min} or newer`;
      return ar ? `${max} أو أقدم` : `${max} or older`;
    case "storage_gb":
      return sizeLabel(Number(eq));
    case "ram_gb":
      return ar ? `رام ${sizeLabel(min ?? 0)} أو أكثر` : `${sizeLabel(min ?? 0)}+ RAM`;
    case "area_sqm":
      if (min !== undefined && max !== undefined) return `${min}–${max} m²`;
      if (min !== undefined) return ar ? `أكثر من ${min} m²` : `Over ${min} m²`;
      return ar ? `أقل من ${max} m²` : `Under ${max} m²`;
    case "furnished":
    case "property_type":
      return value(eq, lang);
    case "item_type":
      return (rule.any_of ?? []).map((v) => value(v, lang)).join(OR[lang]);
    case "amenities":
      return (rule.contains ?? []).map((v) => value(v, lang)).join(" + ");
    case "private_pool":
      return ar ? "مسبح خاص" : "Private pool";
    case "gcc_specs":
      return ar ? "مواصفات خليجية" : "GCC specs";
    case "accident_free":
      return ar ? "بدون حوادث" : "Accident-free";
    case "delivery_available":
      return ar ? "توصيل" : "Delivery";
    default:
      return key.replace(/_/g, " ");
  }
}

export type FilterToken = {
  key: string;
  label: string;
  /** The filters without this token: what the search becomes if the person removes it. */
  without: () => Filters;
};

/**
 * The filters as removable tokens: the item first, then what narrows it (attributes, sale or
 * rent, place, condition, price). Keywords are internal and not shown.
 */
export function filterTokens(filters: Filters | null, lang: Lang = "en"): FilterToken[] {
  if (!filters) return [];
  const f = filters;
  const tokens: FilterToken[] = [];
  const drop = (patch: Partial<Filters>) => () => {
    const next: Filters = { ...f, ...patch };
    for (const k of Object.keys(patch) as (keyof Filters)[]) {
      if (patch[k] === undefined) delete next[k];
    }
    return next;
  };
  const push = (key: string, label: string, without: () => Filters) =>
    tokens.push({ key, label, without });

  if (f.category) push("category", categoryLabel(f.category, lang), drop({ category: undefined }));
  if (f.brands?.length) push("brands", f.brands.join(OR[lang]), drop({ brands: undefined }));
  if (f.models?.length) {
    const many = lang === "ar" ? `${f.models.length} موديلات` : `${f.models.length} models`;
    push(
      "models",
      f.models.length > 2 ? many : f.models.join(OR[lang]),
      drop({ models: undefined }),
    );
  }
  for (const [key, rule] of Object.entries(f.attributes ?? {})) {
    push(`attr:${key}`, attributeLabel(key, rule, lang), () => {
      const rest = { ...(f.attributes ?? {}) };
      delete rest[key];
      const next: Filters = { ...f, attributes: rest };
      if (Object.keys(rest).length === 0) delete next.attributes;
      return next;
    });
  }
  if (f.listing_type) {
    const rent = lang === "ar" ? "للإيجار" : "For rent";
    const sale = lang === "ar" ? "للبيع" : "For sale";
    push(
      "listing_type",
      f.listing_type === "rent" ? rent : sale,
      drop({ listing_type: undefined }),
    );
  }
  if (f.location) push("location", f.location, drop({ location: undefined }));
  if (f.conditions?.length) {
    push("conditions", conditionsLabel(f.conditions, lang), drop({ conditions: undefined }));
  }
  if (f.min_price || f.max_price) {
    push(
      "price",
      priceLabel(f, lang),
      drop({ min_price: undefined, max_price: undefined, price_period: undefined }),
    );
  }
  return tokens;
}

/** Card details: the two facts that matter most for scanning a category. */
export function keyFacts(listing: Listing, lang: Lang = "en"): string[] {
  const a = listing.attributes;
  const ar = lang === "ar";
  const text = (v: unknown) => (typeof v === "string" ? value(v, lang) : null);
  const size = (gb: unknown) => {
    const n = Number(gb);
    return Number.isFinite(n) && n > 0 ? sizeLabel(n) : null;
  };
  const facts: (string | null)[] = [];
  switch (listing.category) {
    case "phones":
      facts.push(size(a.storage_gb), typeof a.color === "string" ? a.color : null);
      break;
    case "laptops":
      facts.push(
        a.ram_gb ? (ar ? `رام ${a.ram_gb} GB` : `${a.ram_gb} GB RAM`) : null,
        size(a.storage_gb),
      );
      break;
    case "cars":
      facts.push(
        a.year ? String(a.year) : null,
        a.mileage_km !== undefined
          ? `${formatAmount(Number(a.mileage_km))} ${ar ? "كم" : "km"}`
          : null,
      );
      break;
    case "furniture":
      facts.push(
        typeof a.item_type === "string" ? a.item_type : null,
        typeof a.material === "string" ? a.material : null,
      );
      break;
    default:
      facts.push(
        a.bedrooms === undefined ? null : bedroomsLabel(Number(a.bedrooms), lang, true),
        a.area_sqm ? `${formatAmount(Number(a.area_sqm))} m²` : null,
        text(a.furnished),
      );
  }
  return facts.filter((f): f is string => Boolean(f)).slice(0, 3);
}
