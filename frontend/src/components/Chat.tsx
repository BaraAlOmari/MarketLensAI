"use client";

import { useEffect, useRef, useState } from "react";

import {
  ChatRequestError,
  type ChatEvent,
  type Filters,
  type Listing,
  type Relaxation,
  streamChat,
} from "@/lib/chat";
import {
  COPY,
  describeSearch,
  dirOf,
  type ErrorKind,
  type Lang,
  languageOf,
  listingCount,
  statusText,
} from "@/lib/copy";
import { filterTokens } from "@/lib/format";

import { EmptyIllustration } from "./EmptyIllustration";
import { FilterTokens } from "./FilterTokens";
import {
  ActivityIndicator,
  AlertIcon,
  ArrowUpIcon,
  ChevronIcon,
  ComposeIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  StopIcon,
} from "./icons";
import { ListingCard, ListingCardSkeleton } from "./ListingCard";
import { type SheetItem, ListingSheet } from "./ListingSheet";
import { ThemeSwitch } from "./ThemeSwitch";

type Status = "understanding" | "searching" | "writing" | "nearby" | "done" | "error";

type Turn = {
  id: number;
  message: string;
  lang: Lang; // of the person's message; an edit keeps the conversation's language
  removed: string | null; // label of the token the person removed, instead of typing
  sentFilters: Filters | undefined; // what an edit sent, so "Try again" can resend it
  status: Status;
  filters: Filters | null;
  reset: boolean; // "start over": the reply stands alone, with no results
  listings: Listing[] | null;
  reply: string;
  cited: number[];
  noMatch: boolean;
  relaxations: Relaxation[];
  nearby: Listing[] | null; // closest listings when nothing matches exactly
  misses: Record<string, string[]>; // listing id -> constraints it fails
  error: ErrorKind | null;
  requestId: string | null; // names this turn in the backend logs; shown on errors
  stopped: boolean; // the person pressed Stop
};

const MAX_LENGTH = 500;

function newSessionId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function Chat() {
  // Made on the first message, never during render: a prerendered page must not carry a
  // session id every visitor would share.
  const sessionRef = useRef<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Plain functions: the React Compiler memoizes them.
  function update(id: number, patch: (t: Turn) => Partial<Turn>) {
    setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...patch(t) } : t)));
  }

  /** A typed message, or (with `filters` and `removed`) an edit of the filter tokens. */
  async function send(message: string, filters?: Filters, removed?: string) {
    const text = message.trim();
    if (!text) return;
    if (busy) {
      // Only an edit may interrupt, and only while the closest matches are loading: the
      // turn's answer is complete by then, so stop that extra search and move on.
      const current = turns.at(-1);
      if (!removed || current?.status !== "nearby") return;
      abortRef.current?.abort();
      update(current.id, () => ({ status: "done", nearby: [] }));
    }
    const id = nextId.current++;
    const lang = removed ? (turns.at(-1)?.lang ?? "en") : languageOf(text);
    setTurns((all) => [
      ...all,
      {
        id, message: text, lang, removed: removed ?? null, sentFilters: filters,
        status: "understanding", filters: null, reset: false, listings: null, reply: "",
        cited: [], noMatch: false, relaxations: [], nearby: null, misses: {}, error: null,
        requestId: null,
        stopped: false,
      },
    ]); // prettier-ignore
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const { events, requestId } = await streamChat(
        { session_id: (sessionRef.current ??= newSessionId()), message: text, filters },
        controller.signal,
      );
      update(id, () => ({ requestId }));
      for await (const event of events) handle(id, event);
    } catch (err) {
      if (controller.signal.aborted) return;
      const status = err instanceof ChatRequestError ? err.status : 0;
      const kind: ErrorKind =
        status === 429 ? "rate" : status === 413 || status === 422 ? "invalid" : "connection";
      const requestId = err instanceof ChatRequestError ? err.requestId : null;
      update(id, () => ({ status: "error", error: kind, requestId }));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setBusy(false);
      }
    }
  }

  function handle(id: number, event: ChatEvent) {
    switch (event.type) {
      case "filters":
        update(id, () => ({
          filters: event.filters,
          reset: Boolean(event.reset),
          status: "searching",
        }));
        break;
      case "listings":
        update(id, () => ({ listings: event.listings, status: "writing" }));
        break;
      case "no_match":
        update(id, () => ({ noMatch: true, relaxations: event.relaxations, status: "nearby" }));
        break;
      case "nearby":
        update(id, () => ({ nearby: event.listings, misses: event.misses }));
        break;
      case "token":
        update(id, (t) => ({ reply: t.reply + event.text }));
        break;
      case "done":
        update(id, (t) => ({
          status: t.status === "error" ? "error" : "done",
          cited: event.cited_ids ?? [],
          noMatch: Boolean(event.no_match),
          relaxations: event.relaxations ?? t.relaxations,
        }));
        break;
      case "error":
        // The backend's message is for developers (logs); people get a plain sentence.
        update(id, () => ({ status: "error", error: "unavailable" }));
        break;
    }
  }

  // Keep the newest turn in view while it streams.
  const last = turns.at(-1);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length, last?.status, last?.listings?.length]);

  // Wake the search service while the person reads and types: when deployed it scales to zero,
  // and a cold start takes about 25 s. Failures don't matter: a chat request waits for the start.
  useEffect(() => {
    fetch("/api/health", { cache: "no-store" }).catch(() => {});
  }, []);

  // The bar turns to glass, with its hairline, only once content scrolls under it (as on iOS).
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 2);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const [sheet, setSheet] = useState<SheetItem | null>(null);

  /** Stop the search in progress (the send button becomes Stop while busy). */
  function stop() {
    const current = turns.at(-1);
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    if (current && current.status !== "done" && current.status !== "error") {
      update(current.id, (t) => ({ status: "done", stopped: true, nearby: t.nearby ?? [] }));
    }
    inputRef.current?.focus();
  }

  function startOver() {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    setTurns([]);
    setDraft("");
    sessionRef.current = null;
    inputRef.current?.focus();
  }

  function submit() {
    if (!draft.trim() || busy) return;
    const text = draft;
    setDraft("");
    void send(text);
  }

  const canSend = draft.trim().length > 0;

  return (
    <div className="flex min-h-dvh flex-col">
      {/* Navigation bar: clear at rest, glass once content scrolls beneath (toolbars.md). */}
      <header
        data-scrolled={scrolled}
        className="bar sticky top-0 z-20 pt-[env(safe-area-inset-top)]"
      >
        <div className="mx-auto grid h-12 w-full max-w-5xl grid-cols-[1fr_auto_1fr] items-center px-2 sm:px-4">
          <div className="justify-self-start ps-2 sm:ps-0">
            <ThemeSwitch />
          </div>
          <h1 className="text-headline">MarketLens</h1>
          {turns.length > 0 ? (
            <button
              type="button"
              onClick={startOver}
              className="press flex h-11 min-w-11 items-center justify-center gap-1 justify-self-end rounded-full px-2.5 text-body text-accent hover:bg-accent/10"
            >
              <ComposeIcon size={22} />
              <span className="max-sm:sr-only">New search</span>
            </button>
          ) : (
            <span />
          )}
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4">
        {turns.length === 0 ? (
          <EmptyState onPick={(q) => void send(q)} />
        ) : (
          <ol className="flex flex-col gap-10 py-6" aria-label="Conversation" aria-busy={busy}>
            {turns.map((turn) => (
              <TurnView
                key={turn.id}
                turn={turn}
                editable={(!busy || turn.status === "nearby") && turn.id === last?.id}
                onEdit={(next, label) => void send(`Removed ${label}`, next, label)}
                onRetry={() => void send(turn.message, turn.sentFilters, turn.removed ?? undefined)}
                onOpen={setSheet}
              />
            ))}
          </ol>
        )}
        <div ref={endRef} />
      </main>

      {/* Composer: a floating glass field over a scroll edge fade, in thumb reach. The send
          button is a filled circle that comes alive when there is text, and turns into Stop
          while a search runs (sf-symbols.md › Animations: replace). */}
      <div className="scroll-edge-bottom pointer-events-none sticky bottom-0 z-10 pt-8 pb-[max(env(safe-area-inset-bottom),0.75rem)]">
        <form
          className="pointer-events-auto mx-auto w-full max-w-3xl px-3 sm:px-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div className="glass glass-float flex items-end rounded-[1.625rem] py-0.5 ps-4 pe-1 has-[textarea:focus-visible]:outline-2 has-[textarea:focus-visible]:outline-offset-0 has-[textarea:focus-visible]:outline-accent">
            <MagnifyingGlassIcon size={17} className="mb-[14px] shrink-0 text-tertiary" />
            <label htmlFor="ask" className="sr-only">
              Ask MarketLens
            </label>
            <textarea
              id="ask"
              ref={inputRef}
              dir="auto"
              rows={1}
              maxLength={MAX_LENGTH}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder="Ask in English or Arabic"
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-body outline-none placeholder:text-tertiary focus-visible:outline-none"
              style={{ fieldSizing: "content" } as React.CSSProperties}
            />
            {busy ? (
              <button
                type="button"
                onClick={stop}
                aria-label="Stop"
                title="Stop"
                className="press flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
              >
                <span
                  key="stop"
                  className="pop-in flex h-8 w-8 items-center justify-center rounded-full bg-content text-surface"
                >
                  <StopIcon size={15} />
                </span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!canSend}
                aria-label="Search"
                title="Search"
                className="press flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
              >
                <span
                  key={canSend ? "ready" : "idle"}
                  className={`flex h-8 w-8 items-center justify-center rounded-full ${
                    canSend ? "pop-in bg-accent-fill text-on-accent" : "bg-fill text-tertiary"
                  }`}
                >
                  <ArrowUpIcon size={17} />
                </span>
              </button>
            )}
          </div>
        </form>
        <p className="pointer-events-auto mx-auto mt-2 w-full max-w-3xl px-4 text-center text-caption text-tertiary">
          AI reads your request and writes the summaries. Prices and details always come from the
          listings.
        </p>
      </div>

      <ListingSheet item={sheet} onClose={() => setSheet(null)} />
    </div>
  );
}

const EXAMPLES = [
  "Find me a used iPhone 17 in great condition for around $900",
  "2 bedroom apartment for rent in Lusail under 12,000 a month",
  "لاندكروزر برادو موديل 2022 أو أحدث",
  "Office chair with delivery",
];

function EmptyState({ onPick }: { onPick: (query: string) => void }) {
  return (
    <section className="flex flex-1 items-center gap-14 py-10" aria-labelledby="empty-title">
      <div className="flex min-w-0 flex-1 flex-col sm:max-w-xl">
        <h2 id="empty-title" className="rise-in text-large-title">
          What are you looking for?
        </h2>
        <p
          lang="ar"
          dir="rtl"
          className="rise-in mt-1 self-start text-title2 font-semibold text-secondary"
          style={{ animationDelay: "40ms" }}
        >
          عن ماذا تبحث؟
        </p>
        <p className="rise-in mt-3 text-body text-secondary" style={{ animationDelay: "80ms" }}>
          Describe it the way you would to a friend: the item, your budget, the condition, the area.
          MarketLens understands what you mean and picks out the best matches.
        </p>

        {/* Inset grouped list (lists-and-tables.md). */}
        <h3 id="examples-title" className="mt-8 px-4 pb-1.5 text-footnote text-secondary">
          Try asking
        </h3>
        <ul
          aria-labelledby="examples-title"
          className="rise-in overflow-hidden rounded-[1.25rem] bg-raised shadow-[var(--card-shadow)]"
          style={{ animationDelay: "120ms" }}
        >
          {EXAMPLES.map((q, i) => {
            return (
              <li key={q} className="relative">
                {i > 0 && (
                  <span
                    aria-hidden="true"
                    className="absolute inset-x-0 top-0 ms-4 border-t-[0.5px] border-separator"
                  />
                )}
                <button
                  type="button"
                  onClick={() => onPick(q)}
                  className="flex min-h-11 w-full items-center gap-3 px-4 py-2.5 text-start text-body transition-colors duration-150 hover:bg-fill/50 focus-visible:-outline-offset-2 active:bg-fill"
                >
                  <span dir="auto" className="flex-1">
                    {q}
                  </span>
                  <ChevronIcon size={14} className="shrink-0 text-tertiary" />
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      {/* Wide screens only: the space beside the text. */}
      <div className="hidden min-w-0 flex-1 lg:block">
        <EmptyIllustration />
      </div>
    </section>
  );
}

function TurnView({
  turn,
  editable,
  onEdit,
  onRetry,
  onOpen,
}: {
  turn: Turn;
  editable: boolean;
  onEdit: (next: Filters, label: string) => void;
  onRetry: () => void;
  onOpen: (item: SheetItem) => void;
}) {
  const copy = COPY[turn.lang];
  const dir = dirOf(turn.lang);
  const streaming = turn.status !== "done" && turn.status !== "error";
  // An empty, non-reset result is shown by <NoMatch>, with the real filter values; the
  // backend's own sentence for it is not repeated.
  const empty = turn.listings !== null && turn.listings.length === 0 && !turn.reset;
  const hasCards = Boolean(turn.listings && turn.listings.length > 0);
  return (
    <li className="flex flex-col gap-3">
      {turn.removed ? (
        <p dir={dir} className="pop-in self-end text-footnote text-secondary">
          {copy.youRemoved(turn.removed)}
        </p>
      ) : (
        <p
          dir="auto"
          className="bubble-in max-w-[80%] self-end rounded-[1.25rem] bg-accent-fill px-3.5 py-2 text-body text-on-accent"
        >
          {turn.message}
        </p>
      )}

      <FilterTokens filters={turn.filters} lang={turn.lang} editable={editable} onRemove={onEdit} />

      {streaming && turn.status !== "nearby" && (
        <p role="status" dir={dir} className="flex items-center gap-2 text-subhead text-secondary">
          <ActivityIndicator />
          <span dir="auto" className="shine">
            {statusText(
              turn.status as "understanding" | "searching" | "writing",
              turn.filters,
              turn.listings?.length ?? null,
              turn.lang,
            )}
          </span>
        </p>
      )}

      {turn.reply && !empty && (
        // Full width in the turn's direction, so a capped-width Arabic summary starts at the
        // right edge instead of sitting in a left-pinned box.
        <div dir={dir} className="reveal">
          {hasCards && (
            <p className="mb-1 flex items-center gap-1.5 text-footnote font-medium text-secondary">
              <SparklesIcon size={14} className="text-accent" />
              {copy.summary}
            </p>
          )}
          <p
            dir="auto"
            aria-live="polite"
            aria-busy={streaming}
            className="max-w-3xl text-body leading-[1.6]"
          >
            {turn.reply}
          </p>
        </div>
      )}

      {turn.stopped && !turn.reply && (
        <p dir={dir} className="pop-in text-footnote text-secondary">
          {copy.stopped}
        </p>
      )}

      {turn.status === "error" && turn.error && (
        <div
          role="alert"
          dir={dir}
          className="pop-in flex flex-wrap items-center gap-3 rounded-[1.25rem] bg-raised p-4 text-subhead shadow-[var(--card-shadow)]"
        >
          <AlertIcon size={22} className="shrink-0 text-danger" />
          <span className="min-w-0 flex-1">
            {copy.errors[turn.error]}
            {turn.requestId && (
              <span className="mt-0.5 block text-footnote text-tertiary">
                <bdi>{copy.reference(turn.requestId.slice(0, 12))}</bdi>
              </span>
            )}
          </span>
          <button
            type="button"
            onClick={onRetry}
            className="press h-11 rounded-full bg-accent-surface px-5 text-subhead font-semibold text-accent hover:bg-accent/15"
          >
            {copy.tryAgain}
          </button>
        </div>
      )}

      {empty && turn.noMatch && <NoMatch turn={turn} editable={editable} onEdit={onEdit} />}

      {turn.status === "nearby" && (
        <>
          <p
            role="status"
            dir={dir}
            className="flex items-center gap-2 text-subhead text-secondary"
          >
            <ActivityIndicator />
            <span className="shine">{statusText("nearby", turn.filters, null, turn.lang)}</span>
          </p>
          <SkeletonGrid />
        </>
      )}

      {turn.nearby && turn.nearby.length > 0 && <Closest turn={turn} onOpen={onOpen} />}

      {turn.listings === null && streaming && turn.status !== "understanding" && <SkeletonGrid />}

      {turn.listings && turn.listings.length > 0 && (
        <section aria-label={listingCount(turn.listings.length, turn.lang)}>
          <h3 dir={dir} className="mb-1.5 px-1 text-footnote text-secondary">
            {listingCount(turn.listings.length, turn.lang)}
          </h3>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {turn.listings.map((listing, i) => {
              const recommended = turn.cited.includes(listing.id);
              return (
                <li key={listing.id} className="flex">
                  <ListingCard
                    listing={listing}
                    index={i}
                    recommended={recommended}
                    lang={turn.lang}
                    onOpen={(l) => onOpen({ listing: l, lang: turn.lang, recommended })}
                  />
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </li>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <ListingCardSkeleton key={i} index={i} />
      ))}
    </div>
  );
}

/**
 * "No exact matches": what was searched, in the token labels, and one-tap ways to drop a
 * single filter, each with the real number of listings it would bring back.
 */
function NoMatch({
  turn,
  editable,
  onEdit,
}: {
  turn: Turn;
  editable: boolean;
  onEdit: (next: Filters, label: string) => void;
}) {
  const copy = COPY[turn.lang];
  const tokens = filterTokens(turn.filters, turn.lang);
  const options = turn.relaxations
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 3)
    .map((r) => ({ r, token: tokens.find((t) => t.key === r.constraint) }))
    .filter((o): o is { r: Relaxation; token: NonNullable<typeof o.token> } => Boolean(o.token));
  return (
    <section
      dir={dirOf(turn.lang)}
      aria-labelledby={`nomatch-${turn.id}`}
      className="reveal flex flex-col gap-2"
    >
      <h3 id={`nomatch-${turn.id}`} className="flex items-center gap-2 text-headline">
        <span
          aria-hidden="true"
          className="flex h-7 w-7 items-center justify-center rounded-full bg-fill text-secondary"
        >
          <MagnifyingGlassIcon size={14} />
        </span>
        {copy.noMatchTitle}
      </h3>
      <p className="max-w-3xl text-body text-secondary">
        <span dir="auto">{copy.noMatchBody(describeSearch(turn.filters, turn.lang))}</span>{" "}
        {options.length > 0 ? copy.noMatchHint : copy.noMatchNoHint}
      </p>
      {options.length > 0 && (
        <ul className="mt-1 flex flex-wrap gap-2">
          {options.map(({ r, token }, i) => {
            const count = listingCount(r.count, turn.lang);
            return (
              <li key={r.constraint} className="pop-in" style={{ animationDelay: `${i * 50}ms` }}>
                {/* Tinted capsule buttons (buttons.md › Style). */}
                <button
                  type="button"
                  disabled={!editable}
                  onClick={() => onEdit(token.without(), token.label)}
                  aria-label={copy.withoutLabel(token.label, count)}
                  className="press flex h-11 items-center gap-1.5 rounded-full bg-accent-surface px-4 text-subhead hover:bg-accent/15 disabled:opacity-40"
                >
                  <span className="font-semibold text-accent">
                    {copy.without(token.label, token.key)}
                  </span>
                  <span aria-hidden="true" className="text-secondary">
                    · {count}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/**
 * The closest listings after a no-match: ranked by the person's own words with only the kind
 * of item kept, each card saying which of the person's filters it misses (with the value).
 */
function Closest({ turn, onOpen }: { turn: Turn; onOpen: (item: SheetItem) => void }) {
  const copy = COPY[turn.lang];
  const dir = dirOf(turn.lang);
  const labels = new Map(filterTokens(turn.filters, turn.lang).map((t) => [t.key, t.label]));
  const nearby = turn.nearby ?? [];
  return (
    <section aria-labelledby={`closest-${turn.id}`} className="mt-2 flex flex-col gap-1.5">
      <div dir={dir} className="px-1">
        <h3 id={`closest-${turn.id}`} className="text-headline">
          {copy.closestTitle}
        </h3>
        <p className="text-footnote text-secondary">{copy.closestNote}</p>
      </div>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {nearby.map((listing, i) => (
          <li key={listing.id} className="flex">
            <ListingCard
              listing={listing}
              index={i}
              recommended={false}
              lang={turn.lang}
              notes={(turn.misses[String(listing.id)] ?? [])
                .map((key) => (labels.has(key) ? copy.misses(labels.get(key)!, key) : null))
                .filter((n): n is string => Boolean(n))}
              onOpen={(l) => onOpen({ listing: l, lang: turn.lang, recommended: false })}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
