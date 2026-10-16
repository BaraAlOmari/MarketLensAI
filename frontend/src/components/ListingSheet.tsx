"use client";

import { useEffect, useRef, useState } from "react";

import type { Listing } from "@/lib/chat";
import { COPY, dirOf } from "@/lib/copy";
import {
  attributeRows,
  categoryLabel,
  conditionLabel,
  formatPrice,
  type Lang,
  listingTypeLabel,
} from "@/lib/format";

import { CATEGORY_ICON, CloseIcon, PinIcon, SealIcon } from "./icons";

export type SheetItem = { listing: Listing; lang: Lang; recommended: boolean };

const DISMISS_DISTANCE = 110; // px dragged down
const DISMISS_VELOCITY = 0.6; // px per ms

/**
 * A listing's full details in a sheet (sheets.md): from the bottom edge with a grabber on
 * phones, swipe down to dismiss; a centered card on wider screens. A native modal <dialog>
 * gives the focus trap, Escape and inert page behind it. Read-only, so there is one way out
 * labelled Close (plus swipe, Escape and tapping outside), and no Done.
 */
export function ListingSheet({ item, onClose }: { item: SheetItem | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [drag, setDrag] = useState(0);
  const [dragging, setDragging] = useState(false);
  const start = useRef<{ y: number; t: number } | null>(null);
  const closing = useRef(false);

  useEffect(() => {
    const dialog = ref.current;
    if (item && dialog && !dialog.open) {
      closing.current = false;
      dialog.showModal();
      document.documentElement.style.overflow = "hidden"; // no page scroll behind the sheet
    }
  }, [item]);

  function close() {
    const dialog = ref.current;
    if (!dialog?.open || closing.current) return;
    closing.current = true;
    const finish = () => {
      dialog.removeAttribute("data-closing");
      dialog.close();
      document.documentElement.style.overflow = "";
      setDrag(0);
      onClose();
    };
    dialog.dataset.closing = "";
    dialog.addEventListener("animationend", finish, { once: true });
    window.setTimeout(() => dialog.open && finish(), 400); // if no animation runs
  }

  function onPointerDown(e: React.PointerEvent) {
    if (window.matchMedia("(min-width: 640px)").matches) return; // swipe only for the phone sheet
    start.current = { y: e.clientY, t: performance.now() };
    setDragging(true);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent) {
    if (start.current) setDrag(Math.max(0, e.clientY - start.current.y));
  }
  function onPointerUp(e: React.PointerEvent) {
    if (!start.current) return;
    const dy = e.clientY - start.current.y;
    const velocity = dy / Math.max(1, performance.now() - start.current.t);
    start.current = null;
    setDragging(false);
    if (dy > DISMISS_DISTANCE || velocity > DISMISS_VELOCITY) close();
    else setDrag(0);
  }

  const listing = item?.listing;
  const lang = item?.lang ?? "en";
  const copy = COPY[lang];
  const Icon = listing ? CATEGORY_ICON[listing.category] : undefined;
  const rows = listing
    ? [
        { label: copy.sheet.location, value: listing.location },
        ...(listing.condition
          ? [{ label: copy.sheet.condition, value: conditionLabel(listing.condition, lang) }]
          : []),
        { label: copy.sheet.type, value: listingTypeLabel(listing, lang) },
        ...attributeRows(listing, lang),
      ]
    : [];

  return (
    <dialog
      ref={ref}
      dir={dirOf(lang)}
      aria-labelledby="sheet-title"
      onCancel={(e) => {
        e.preventDefault(); // Escape: animate out instead of vanishing
        close();
      }}
      onClick={(e) => e.target === e.currentTarget && close()} // a tap on the backdrop
      className="sheet fixed inset-x-0 top-auto bottom-0 m-0 max-h-[92dvh] w-full max-w-none overflow-hidden rounded-t-[2rem] bg-raised p-0 text-content shadow-[var(--glass-shadow)] open:flex open:flex-col sm:inset-0 sm:m-auto sm:max-h-[85dvh] sm:max-w-lg sm:rounded-[1.75rem]"
      style={{
        transform: drag ? `translateY(${drag}px)` : undefined,
        transition: dragging ? "none" : "transform 380ms var(--ease-ios)",
      }}
    >
      {listing && (
        <>
          {/* Grab area: the grabber and the bar; dragging it down dismisses on phones. */}
          <div
            className="shrink-0 touch-none select-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            <div
              aria-hidden="true"
              className="mx-auto mt-2 h-[5px] w-9 rounded-full bg-tertiary/35 sm:hidden"
            />
            <div className="flex items-center justify-end px-3 pt-1 sm:pt-3">
              <button
                type="button"
                onClick={close}
                aria-label={copy.sheet.close}
                title={copy.sheet.close}
                className="press flex h-11 w-11 items-center justify-center rounded-full"
              >
                <span className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-fill text-secondary">
                  <CloseIcon size={13} />
                </span>
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-[max(env(safe-area-inset-bottom),1.5rem)]">
            <div
              className="tile flex aspect-[16/9] items-center justify-center rounded-[1.25rem]"
              style={
                {
                  "--tile": `var(--cat-${listing.category}, var(--tertiary))`,
                } as React.CSSProperties
              }
            >
              {listing.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- listing photos come from arbitrary hosts
                <img
                  src={listing.image_url}
                  alt=""
                  className="h-full w-full rounded-[inherit] object-cover"
                />
              ) : (
                Icon && <Icon size={56} strokeWidth={1.2} />
              )}
              <span className="sr-only">{categoryLabel(listing.category, lang)}</span>
            </div>

            <div className="mt-4 flex flex-col gap-1.5">
              {item.recommended && (
                <span className="flex items-center gap-1 self-start rounded-full bg-accent-fill py-0.5 ps-1.5 pe-2.5 text-caption font-semibold text-on-accent">
                  <SealIcon size={13} />
                  {copy.recommended}
                </span>
              )}
              <h2
                id="sheet-title"
                dir="auto"
                className="text-title3 font-semibold [text-align:match-parent]"
              >
                {listing.title}
              </h2>
              <p className="text-title2 font-bold tabular-nums">
                <bdi dir="ltr">{formatPrice(listing)}</bdi>
              </p>
              <p className="flex items-center gap-1 text-subhead text-secondary">
                <PinIcon size={15} className="shrink-0 text-tertiary" />
                <span dir="auto">{listing.location}</span>
              </p>
            </div>

            {/* Inset grouped list (lists-and-tables.md). */}
            <h3 className="mt-6 px-4 pb-1.5 text-footnote text-secondary">{copy.sheet.details}</h3>
            <dl className="overflow-hidden rounded-[1.125rem] bg-[var(--grouped)]">
              {rows.map((row, i) => (
                <div
                  key={row.label}
                  className="relative flex min-h-11 items-center gap-4 px-4 py-2.5"
                >
                  {i > 0 && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-x-0 top-0 ms-4 border-t-[0.5px] border-separator"
                    />
                  )}
                  <dt className="text-body text-secondary">{row.label}</dt>
                  <dd dir="auto" className="ms-auto text-end text-body">
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>

            {listing.description && (
              <>
                <h3 className="mt-6 px-4 pb-1.5 text-footnote text-secondary">
                  {copy.sheet.description}
                </h3>
                <p
                  dir="auto"
                  className="rounded-[1.125rem] bg-[var(--grouped)] px-4 py-3 text-body leading-[1.55] whitespace-pre-line"
                >
                  {listing.description}
                </p>
              </>
            )}

            <p className="mt-4 px-4 text-footnote text-tertiary">
              <bdi>{copy.sheet.listing(listing.external_id)}</bdi>
            </p>
          </div>
        </>
      )}
    </dialog>
  );
}
