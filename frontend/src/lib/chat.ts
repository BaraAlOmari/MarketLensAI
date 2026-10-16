// The /api/chat contract (backend app/answers/chat.py). Everything shown on a listing card
// comes from `Listing`, which the backend re-reads from the database; the reply text never
// carries prices or links.

export type Condition = "new" | "like_new" | "good" | "fair" | "poor";

export type Listing = {
  id: number;
  external_id: string;
  title: string;
  description: string;
  category: string;
  brand: string | null;
  model: string | null;
  price: string; // decimal string, e.g. "2100.00"
  currency: string;
  price_qar: string;
  condition: Condition | null;
  listing_type: "sale" | "rent";
  price_period: "total" | "month" | "year";
  attributes: Record<string, unknown>;
  location: string;
  language: "en" | "ar" | "mixed";
  image_url: string | null;
  score: number;
  ranks: Record<string, number>;
};

export type AttributeFilter = {
  eq?: unknown;
  any_of?: string[];
  min?: string | number;
  max?: string | number;
  contains?: string[];
};

export type Filters = {
  category?: string;
  brands?: string[];
  models?: string[];
  conditions?: Condition[];
  min_price?: string;
  max_price?: string;
  currency?: string;
  price_period?: "total" | "month" | "year";
  listing_type?: "sale" | "rent";
  location?: string;
  attributes?: Record<string, AttributeFilter>;
  keywords?: string[];
};

export type Relaxation = { constraint: string; count: number };

export type ChatEvent =
  | {
      type: "filters";
      filters: Filters | null;
      notes?: string[];
      reset?: boolean;
      error?: string | null;
    }
  | { type: "listings"; listings: Listing[] }
  | { type: "no_match"; relaxations: Relaxation[] }
  // Closest listings after a no-match; `misses` maps a listing id to the constraints it
  // fails, named like the filter tokens ("price", "models", "attr:bedrooms").
  | { type: "nearby"; listings: Listing[]; misses: Record<string, string[]> }
  | { type: "token"; text: string }
  | {
      type: "done";
      cited_ids: number[];
      no_match?: boolean;
      reset?: boolean;
      relaxations?: Relaxation[];
      timings_ms?: Record<string, number>;
    }
  | { type: "error"; message: string };

/** Parse a text/event-stream body into events as they arrive. */
export async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      let name = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7).trim();
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;
      yield { type: name, ...JSON.parse(data) } as ChatEvent;
    }
  }
}

export class ChatRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** The request's ID in the backend logs (`scripts/explain.py <id>`). */
    readonly requestId: string | null = null,
  ) {
    super(message);
  }
}

export type ChatStream = { events: AsyncGenerator<ChatEvent>; requestId: string | null };

export async function streamChat(
  payload: { session_id: string; message: string; filters?: Filters },
  signal?: AbortSignal,
): Promise<ChatStream> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok || !response.body) {
    let detail = "";
    try {
      const data = await response.json();
      detail = typeof data.detail === "string" ? data.detail : "";
    } catch {
      // not JSON; fall through to the generic message
    }
    throw new ChatRequestError(
      detail || `HTTP ${response.status}`,
      response.status,
      response.headers.get("x-request-id"),
    );
  }
  return { events: readEvents(response.body), requestId: response.headers.get("x-request-id") };
}
