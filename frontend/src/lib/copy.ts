// Interface copy for one turn, in the language of the person's message (writing.md: say what
// is happening, with the real values; no jargon). Values such as "iPhone 17" or
// "765–1,035 USD" come from the same labels as the filter tokens, so the words match.

import type { Filters } from "./chat";
import { filterTokens, type Lang } from "./format";

export type { Lang };

const ARABIC = /[؀-ۿ]/;

export function languageOf(text: string): Lang {
  return ARABIC.test(text) ? "ar" : "en";
}

export function dirOf(lang: Lang): "rtl" | "ltr" {
  return lang === "ar" ? "rtl" : "ltr";
}

/** "8 listings" / "8 إعلانات" (Arabic: 1, 2, 3–10 and 11+ take different forms). */
export function listingCount(n: number, lang: Lang): string {
  if (lang === "ar") {
    if (n === 1) return "إعلان واحد";
    if (n === 2) return "إعلانان";
    if (n >= 3 && n <= 10) return `${n} إعلانات`;
    return `${n} إعلاناً`;
  }
  return `${n} ${n === 1 ? "listing" : "listings"}`;
}

/** Lower-case a generic label ("Like new" → "like new") but not a name or acronym ("GCC"). */
// Brands, models and places are names: their capitals stay ("Galaxy S25 Ultra").
const NAMES = new Set(["brands", "models", "location"]);

/** A token label inside a sentence: generic words lower-cased, names untouched. */
function inSentence(label: string, key: string): string {
  return NAMES.has(key) ? label : soften(label);
}

function soften(label: string): string {
  return /^[A-Z][a-z]/.test(label) ? label[0].toLowerCase() + label.slice(1) : label;
}

// Filters that read as a feature of the item: "with delivery", "with a private pool".
const FEATURES = new Set([
  "attr:delivery_available",
  "attr:private_pool",
  "attr:gcc_specs",
  "attr:amenities",
]);

/**
 * The search in words, from the filter tokens: "iPhone 17, like new or good, 765–1,035 USD" or
 * "apartments, 2 bedrooms, for rent, in Lusail". Empty when there are no filters.
 */
export function describeSearch(filters: Filters | null, lang: Lang): string {
  const ar = lang === "ar";
  const tokens = filterTokens(filters, lang);
  if (tokens.length === 0) return "";
  const label = (key: string) => tokens.find((t) => t.key === key)?.label;
  const category = label("category");
  const brands = label("brands");
  let subject = label("models");
  if (!subject && brands && category) {
    subject = ar ? `${category} ${brands}` : `${brands} ${soften(category)}`;
  } else if (!subject) {
    subject = brands ?? (category && !ar ? soften(category) : category);
  }
  const rest = tokens
    .filter((t) => !["models", "brands", "category"].includes(t.key))
    .map((t) => {
      if (t.key === "location") return ar ? `في ${t.label}` : `in ${t.label}`;
      if (FEATURES.has(t.key)) return ar ? `مع ${t.label}` : `with ${soften(t.label)}`;
      return ar ? t.label : soften(t.label);
    });
  return [subject, ...rest].filter(Boolean).join(ar ? "، " : ", ");
}

export type Stage = "understanding" | "searching" | "writing" | "nearby";

/** The status line: what MarketLens is doing right now, with the real search in it. */
export function statusText(
  stage: Stage,
  filters: Filters | null,
  listings: number | null,
  lang: Lang,
): string {
  const ar = lang === "ar";
  if (stage === "understanding") return ar ? "جارٍ البحث…" : "Searching…";
  if (stage === "searching") {
    const what = describeSearch(filters, lang);
    if (!what) return ar ? "نبحث في كل الإعلانات…" : "Searching all listings…";
    return ar ? `نبحث عن ${what}…` : `Looking for ${what}…`;
  }
  if (stage === "nearby") return ar ? "نبحث عن أقرب الخيارات…" : "Finding the closest matches…";
  if (!listings) return ar ? "نتحقق من الخيارات القريبة…" : "Checking what's close…";
  return ar
    ? `نقارن ${listings === 2 ? "إعلانين" : listings === 1 ? "إعلاناً واحداً" : listingCount(listings, lang)}…`
    : `Comparing ${listingCount(listings, lang)}…`;
}

export const COPY = {
  en: {
    understoodAs: "Understood as",
    removeToken: (label: string) => `Remove ${label}`,
    youRemoved: (label: string) => `You removed ${label}`,
    recommended: "Recommended",
    noMatchTitle: "No exact matches",
    noMatchBody: (what: string) =>
      what ? `Nothing matches ${what}.` : "Nothing matches that yet.",
    noMatchHint: "Remove one filter to see more:",
    noMatchNoHint: "Try removing a filter, or describe what you want in a different way.",
    without: (label: string, key: string) => `Without ${inSentence(label, key)}`,
    closestTitle: "Closest matches",
    closestNote: "Each of these misses at least one of your filters.",
    misses: (label: string, key: string) =>
      key === "location" ? `Not in ${label}` : `Not ${inSentence(label, key)}`,
    withoutLabel: (label: string, count: string) => `Remove ${label} to see ${count}`,
    tryAgain: "Try again",
    summary: "Summary",
    stopped: "Stopped.",
    sheet: {
      close: "Close",
      details: "Details",
      description: "Description",
      condition: "Condition",
      location: "Location",
      type: "Type",
      listing: (id: string) => `Listing ${id}`,
      open: (title: string) => `Details for ${title}`,
    },
    errors: {
      connection: "Couldn't connect to MarketLens. Check your connection and try again.",
      unavailable: "Search isn't available right now. Try again in a moment.",
      invalid: "That message couldn't be sent. Try a shorter one.",
    },
  },
  ar: {
    understoodAs: "فهمنا:",
    removeToken: (label: string) => `إزالة ${label}`,
    youRemoved: (label: string) => `حذفت ${label}`,
    recommended: "مقترح",
    noMatchTitle: "لا توجد نتائج مطابقة تماماً",
    noMatchBody: (what: string) =>
      what ? `لا يوجد إعلان يطابق: ${what}.` : "لا يوجد إعلان يطابق طلبك بعد.",
    noMatchHint: "احذف شرطاً واحداً لترى المزيد:",
    noMatchNoHint: "جرّب حذف أحد الشروط، أو صف طلبك بطريقة أخرى.",
    without: (label: string) => `بدون ${label}`,
    closestTitle: "أقرب النتائج",
    closestNote: "كل منها لا يطابق شرطاً واحداً على الأقل من شروطك.",
    misses: (label: string, key: string) =>
      key === "location" ? `ليس في ${label}` : `لا يطابق: ${label}`,
    withoutLabel: (label: string, count: string) => `احذف ${label} لترى ${count}`,
    tryAgain: "حاول مرة أخرى",
    summary: "الملخص",
    stopped: "تم الإيقاف.",
    sheet: {
      close: "إغلاق",
      details: "التفاصيل",
      description: "الوصف",
      condition: "الحالة",
      location: "الموقع",
      type: "النوع",
      listing: (id: string) => `إعلان ${id}`,
      open: (title: string) => `تفاصيل ${title}`,
    },
    errors: {
      connection: "تعذّر الاتصال بـ MarketLens. تحقّق من اتصالك وحاول مرة أخرى.",
      unavailable: "البحث غير متاح حالياً. حاول مرة أخرى بعد قليل.",
      invalid: "تعذّر إرسال الرسالة. جرّب رسالة أقصر.",
    },
  },
} as const;

export type ErrorKind = keyof (typeof COPY)["en"]["errors"];
