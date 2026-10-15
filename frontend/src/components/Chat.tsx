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

import { FilterTokens } from "./FilterTokens";
import { ActivityIndicator, AlertIcon, ArrowUpIcon, ChevronIcon, ComposeIcon } from "./icons";
import { ListingCard, ListingCardSkeleton } from "./ListingCard";
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
};

const EXAMPLES = [
  "Find me a used iPhone 17 in great condition for around $900",
  "2 bedroom apartment for rent in Lusail under 12,000 a month",
  "لاندكروزر برادو موديل 2022 أو أحدث",
  "Office chair with delivery",
];

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
      },
    ]); // prettier-ignore
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const events = await streamChat(
        { session_id: (sessionRef.current ??= newSessionId()), message: text, filters },
        controller.signal,
      );
      for await (const event of events) handle(id, event);
    } catch (err) {
      if (controller.signal.aborted) return;
      const kind: ErrorKind =
        err instanceof ChatRequestError && (err.status === 413 || err.status === 422)
          ? "invalid"
          : "connection";
      update(id, () => ({ status: "error", error: kind }));
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

  return (
    <div className="flex min-h-dvh flex-col">
      {/* Navigation bar: translucent material over content, centered title (toolbars.md). */}
      <header className="sticky top-0 z-10 border-b-[0.5px] border-separator bg-surface/75 pt-[env(safe-area-inset-top)] backdrop-blur-xl backdrop-saturate-150">
        <div className="mx-auto grid h-12 w-full max-w-5xl grid-cols-[1fr_auto_1fr] items-center px-2 sm:px-4">
          <div className="justify-self-start ps-2 sm:ps-0">
            <ThemeSwitch />
          </div>
          <h1 className="text-headline">MarketLens</h1>
          {turns.length > 0 ? (
            <button
              type="button"
              onClick={startOver}
              className="flex h-11 min-w-11 items-center justify-center gap-1 justify-self-end rounded-full px-2.5 text-body text-accent hover:bg-accent/10"
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
              />
            ))}
          </ol>
        )}
        <div ref={endRef} />
      </main>

      {/* Composer: a Messages-style field with the send button inside it, within thumb reach. */}
      <div className="sticky bottom-0 border-t-[0.5px] border-separator bg-surface/75 pb-[max(env(safe-area-inset-bottom),0.625rem)] pt-2.5 backdrop-blur-xl backdrop-saturate-150">
        <form
          className="mx-auto w-full max-w-5xl px-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div className="flex items-end rounded-[1.375rem] border-[0.5px] border-separator bg-raised ps-4 pe-1 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
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
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent py-2.5 text-body outline-none placeholder:text-tertiary focus-visible:outline-none"
              style={{ fieldSizing: "content" } as React.CSSProperties}
            />
            {/* 32 pt circle, 44 pt hit area (accessibility.md: control size). */}
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              aria-label="Search"
              className="group flex h-11 w-11 shrink-0 items-center justify-center rounded-full focus-visible:outline-offset-0"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-fill text-on-accent transition-opacity group-disabled:opacity-30">
                <ArrowUpIcon size={18} />
              </span>
            </button>
          </div>
        </form>
        <p className="mx-auto mt-1.5 w-full max-w-5xl px-4 text-center text-caption text-tertiary">
          AI reads your request and writes the summaries. Prices and details always come from the
          listings.
        </p>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (query: string) => void }) {
  return (
    <section
      className="flex flex-1 flex-col justify-center py-10 sm:max-w-xl"
      aria-labelledby="empty-title"
    >
      <h2 id="empty-title" className="text-large-title">
        What are you looking for?
      </h2>
      <p lang="ar" dir="rtl" className="mt-1 self-start text-title2 font-semibold text-secondary">
        عن ماذا تبحث؟
      </p>
      <p className="mt-3 text-body text-secondary">
        Describe it the way you would to a friend: the item, your budget, the condition, the area.
        MarketLens shows what it understood, and you can remove anything it got wrong.
      </p>

      {/* Inset grouped list (lists-and-tables.md): one rounded group, inset separators. */}
      <h3 id="examples-title" className="mt-8 px-4 pb-1.5 text-footnote text-secondary">
        Try asking
      </h3>
      <ul aria-labelledby="examples-title" className="overflow-hidden rounded-[1.25rem] bg-raised">
        {EXAMPLES.map((q, i) => (
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
              className="flex min-h-11 w-full items-center gap-3 px-4 py-3 text-start text-body hover:bg-fill/60 active:bg-fill focus-visible:-outline-offset-2"
            >
              <span dir="auto" className="flex-1">
                {q}
              </span>
              <ChevronIcon size={16} className="shrink-0 text-tertiary" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function TurnView({
  turn,
  editable,
  onEdit,
  onRetry,
}: {
  turn: Turn;
  editable: boolean;
  onEdit: (next: Filters, label: string) => void;
  onRetry: () => void;
}) {
  const copy = COPY[turn.lang];
  const dir = dirOf(turn.lang);
  const streaming = turn.status !== "done" && turn.status !== "error";
  // An empty, non-reset result is shown by <NoMatch>, with the real filter values; the
  // backend's own sentence for it is not repeated.
  const empty = turn.listings !== null && turn.listings.length === 0 && !turn.reset;
  return (
    <li className="flex flex-col gap-3">
      {turn.removed ? (
        <p dir={dir} className="self-end text-footnote text-secondary">
          {copy.youRemoved(turn.removed)}
        </p>
      ) : (
        <p
          dir="auto"
          className="max-w-[80%] self-end rounded-[1.25rem] bg-accent-fill px-3.5 py-2 text-body text-on-accent"
        >
          {turn.message}
        </p>
      )}

      <FilterTokens filters={turn.filters} lang={turn.lang} editable={editable} onRemove={onEdit} />

      {streaming && turn.status !== "nearby" && (
        <p role="status" dir={dir} className="flex items-center gap-2 text-subhead text-secondary">
          <ActivityIndicator />
          <span dir="auto">
            {statusText(
              turn.status as "understanding" | "searching" | "writing" | "nearby",
              turn.filters,
              turn.listings?.length ?? null,
              turn.lang,
            )}
          </span>
        </p>
      )}

      {turn.reply && !empty && (
        <p
          dir="auto"
          aria-live="polite"
          aria-busy={streaming}
          className="max-w-3xl text-body leading-[1.6]"
        >
          {turn.reply}
        </p>
      )}

      {turn.status === "error" && turn.error && (
        <div
          role="alert"
          dir={dir}
          className="flex flex-wrap items-center gap-3 rounded-[1.25rem] bg-raised p-4 text-subhead"
        >
          <AlertIcon size={20} className="shrink-0 text-danger" />
          <span className="min-w-0 flex-1">{copy.errors[turn.error]}</span>
          <button
            type="button"
            onClick={onRetry}
            className="h-11 rounded-full bg-accent-surface px-5 text-subhead font-semibold text-accent hover:bg-accent/15"
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
            {statusText("nearby", turn.filters, null, turn.lang)}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <ListingCardSkeleton key={i} />
            ))}
          </div>
        </>
      )}

      {turn.nearby && turn.nearby.length > 0 && <Closest turn={turn} />}

      {turn.listings === null && streaming && turn.status !== "understanding" && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <ListingCardSkeleton key={i} />
          ))}
        </div>
      )}

      {turn.listings && turn.listings.length > 0 && (
        <section aria-label={listingCount(turn.listings.length, turn.lang)}>
          <h3 dir={dir} className="mb-1.5 px-1 text-footnote text-secondary">
            {listingCount(turn.listings.length, turn.lang)}
          </h3>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {turn.listings.map((listing, i) => (
              <li key={listing.id} className="flex">
                <ListingCard
                  listing={listing}
                  index={i}
                  recommended={turn.cited.includes(listing.id)}
                  lang={turn.lang}
                />
              </li>
            ))}
          </ul>
        </section>
      )}
    </li>
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
      className="flex flex-col gap-2"
    >
      <h3 id={`nomatch-${turn.id}`} className="text-headline">
        {copy.noMatchTitle}
      </h3>
      <p className="max-w-3xl text-body text-secondary">
        <span dir="auto">{copy.noMatchBody(describeSearch(turn.filters, turn.lang))}</span>{" "}
        {options.length > 0 ? copy.noMatchHint : copy.noMatchNoHint}
      </p>
      {options.length > 0 && (
        <ul className="mt-1 flex flex-wrap gap-2">
          {options.map(({ r, token }) => {
            const count = listingCount(r.count, turn.lang);
            return (
              <li key={r.constraint}>
                {/* Tinted capsule buttons (buttons.md › Style). */}
                <button
                  type="button"
                  disabled={!editable}
                  onClick={() => onEdit(token.without(), token.label)}
                  aria-label={copy.withoutLabel(token.label, count)}
                  className="flex h-11 items-center gap-1.5 rounded-full bg-accent-surface px-4 text-subhead hover:bg-accent/15 disabled:opacity-40"
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
function Closest({ turn }: { turn: Turn }) {
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
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
