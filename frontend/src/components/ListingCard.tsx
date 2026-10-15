import type { Listing } from "@/lib/chat";
import { COPY, dirOf } from "@/lib/copy";
import { categoryLabel, conditionLabel, formatPrice, keyFacts, type Lang } from "@/lib/format";

import { CATEGORY_ICON, PinIcon } from "./icons";

export function ListingCard({
  listing,
  recommended,
  index,
  lang,
  notes = [],
}: {
  listing: Listing;
  recommended: boolean;
  index: number;
  /** The turn's language, for labels; listing text stays as written. */
  lang: Lang;
  /** How this listing differs from the request (closest matches only). */
  notes?: string[];
}) {
  const Icon = CATEGORY_ICON[listing.category];
  const facts = keyFacts(listing, lang);
  const titleId = `listing-${listing.id}-title`;
  return (
    <article
      aria-labelledby={titleId}
      dir={dirOf(lang)} // an Arabic turn mirrors the card (right-to-left.md)
      className="rise-in flex w-full min-w-0 flex-row overflow-hidden rounded-[1.25rem] bg-raised sm:flex-col"
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
    >
      {/* Phones: a compact row with a small thumbnail. Wider: a card with a 16:9 image. */}
      <div className="relative flex w-24 shrink-0 items-center justify-center bg-fill text-tertiary sm:aspect-[16/9] sm:w-full">
        {listing.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- listing photos come from arbitrary hosts
          <img src={listing.image_url} alt="" className="h-full w-full object-cover" />
        ) : (
          Icon && <Icon size={32} />
        )}
        {/* The number the summary uses when it points at a listing. */}
        <span className="absolute start-2 top-2 flex h-6 min-w-6 items-center justify-center rounded-full bg-raised/85 px-1.5 text-caption font-semibold tabular-nums text-secondary backdrop-blur">
          <span className="sr-only">{lang === "ar" ? "إعلان " : "Listing "}</span>
          {index + 1}
        </span>
        <span className="sr-only">{categoryLabel(listing.category, lang)}</span>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 p-4">
        {recommended && (
          <span className="mb-0.5 self-start rounded-full bg-accent-fill px-2.5 py-0.5 text-caption font-semibold text-on-accent">
            {COPY[lang].recommended}
          </span>
        )}
        <h3
          id={titleId}
          dir="auto"
          className="line-clamp-2 text-subhead font-semibold [text-align:match-parent]"
        >
          {listing.title}
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
          <PinIcon size={15} />
          <span dir="auto">{listing.location}</span>
        </p>
      </div>
    </article>
  );
}

export function ListingCardSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="flex w-full flex-row overflow-hidden rounded-[1.25rem] bg-raised sm:flex-col"
    >
      <div className="skeleton w-24 shrink-0 sm:aspect-[16/9] sm:w-full" />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="skeleton h-4 w-4/5 rounded" />
        <div className="skeleton h-4 w-2/5 rounded" />
        <div className="skeleton h-3 w-3/5 rounded" />
      </div>
    </div>
  );
}
