import type { Listing } from "@/lib/chat";
import { COPY, dirOf } from "@/lib/copy";
import { categoryLabel, conditionLabel, formatPrice, keyFacts, type Lang } from "@/lib/format";

import { CATEGORY_ICON, PinIcon, SealIcon } from "./icons";

/**
 * A listing card. The whole card opens the detail sheet: its title is a button whose ::after
 * covers the card (a "stretched" button, so the card keeps real headings and text), and the
 * card shows that button's press, hover and focus states.
 */
export function ListingCard({
  listing,
  recommended,
  index,
  lang,
  notes = [],
  onOpen,
}: {
  listing: Listing;
  recommended: boolean;
  index: number;
  /** The turn's language, for labels; listing text stays as written. */
  lang: Lang;
  /** How this listing differs from the request (closest matches only). */
  notes?: string[];
  onOpen: (listing: Listing) => void;
}) {
  const Icon = CATEGORY_ICON[listing.category];
  const facts = keyFacts(listing, lang);
  const copy = COPY[lang];
  return (
    <article
      dir={dirOf(lang)} // an Arabic turn mirrors the card (right-to-left.md)
      className="rise-in relative flex w-full min-w-0 flex-row overflow-hidden rounded-[1.375rem] bg-raised shadow-[var(--card-shadow)] transition-[transform,box-shadow] duration-200 ease-[var(--ease-ios)] has-[button:active]:scale-[0.98] has-[button:focus-visible]:outline-2 has-[button:focus-visible]:outline-offset-2 has-[button:focus-visible]:outline-accent motion-reduce:has-[button:active]:scale-100 sm:flex-col [@media(hover:hover)]:hover:shadow-[var(--card-shadow-hover)]"
      style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}
    >
      {/* Phones: a compact row with a square tile. Wider: a card with a 16:9 tile. */}
      <div
        className="tile relative flex w-24 shrink-0 items-center justify-center sm:aspect-[16/9] sm:w-full"
        style={
          { "--tile": `var(--cat-${listing.category}, var(--tertiary))` } as React.CSSProperties
        }
      >
        {listing.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- listing photos come from arbitrary hosts
          <img src={listing.image_url} alt="" className="h-full w-full object-cover" />
        ) : (
          Icon && <Icon size={34} strokeWidth={1.4} />
        )}
        {/* The number the summary uses when it points at a listing. */}
        <span className="glass absolute start-2 top-2 flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-caption font-semibold tabular-nums text-content">
          <span className="sr-only">{lang === "ar" ? "إعلان " : "Listing "}</span>
          {index + 1}
        </span>
        <span className="sr-only">{categoryLabel(listing.category, lang)}</span>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 p-4">
        {recommended && (
          <span className="mb-0.5 flex items-center gap-1 self-start rounded-full bg-accent-fill py-0.5 ps-1.5 pe-2.5 text-caption font-semibold text-on-accent">
            <SealIcon size={13} />
            {copy.recommended}
          </span>
        )}
        <h3 className="text-subhead font-semibold">
          <button
            type="button"
            onClick={() => onOpen(listing)}
            aria-label={copy.sheet.open(listing.title)}
            className="block w-full text-start after:absolute after:inset-0 after:rounded-[inherit] focus-visible:outline-none"
          >
            <span dir="auto" className="line-clamp-2 [text-align:match-parent]">
              {listing.title}
            </span>
          </button>
        </h3>
        <p className="text-headline tabular-nums">
          <bdi dir="ltr">{formatPrice(listing)}</bdi>
        </p>
        {notes.length > 0 && (
          <p className="text-footnote font-medium text-danger">
            {notes.map((note, i) => (
              <span key={note}>
                {i > 0 && " · "}
                <bdi>{note}</bdi>
              </span>
            ))}
          </p>
        )}
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-footnote text-secondary">
          {listing.condition && (
            <span className="rounded-full bg-fill px-2 py-0.5 font-medium text-content">
              {conditionLabel(listing.condition, lang)}
            </span>
          )}
          {facts.map((fact) => (
            <span key={fact} dir="auto">
              {fact}
            </span>
          ))}
        </div>
        <p className="mt-auto flex items-center gap-1 pt-1.5 text-footnote text-secondary">
          <PinIcon size={14} className="shrink-0 text-tertiary" />
          <span dir="auto" className="truncate">
            {listing.location}
          </span>
        </p>
      </div>
    </article>
  );
}

/** A redacted card: the same shapes as a real one, under one shared highlight sweep. */
export function ListingCardSkeleton({ index = 0 }: { index?: number }) {
  return (
    <div
      aria-hidden="true"
      className="rise-in flex w-full flex-row overflow-hidden rounded-[1.375rem] bg-raised shadow-[var(--card-shadow)] sm:flex-col"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="skeleton w-24 shrink-0 sm:aspect-[16/9] sm:w-full" />
      <div className="flex flex-1 flex-col gap-2.5 p-4">
        <div className="skeleton h-3.5 w-11/12 rounded-full" />
        <div className="skeleton h-3.5 w-3/5 rounded-full" />
        <div className="skeleton mt-1 h-4.5 w-2/5 rounded-full" />
        <div className="flex gap-2">
          <div className="skeleton h-5 w-16 rounded-full" />
          <div className="skeleton h-5 w-12 rounded-full" />
        </div>
        <div className="skeleton mt-1 h-3 w-1/3 rounded-full" />
      </div>
    </div>
  );
}
