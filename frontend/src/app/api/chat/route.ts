import { BACKEND_URL } from "@/lib/backend";

const MAX_BODY_BYTES = 8_000;

/**
 * Streams the FastAPI chat (server-sent events) to the browser. The backend URL stays on the
 * server, and the event stream is passed through untouched as it arrives.
 *
 * One request ID is made here and sent to the backend, so the UI (it shows the ID on errors)
 * and the backend logs (`scripts/explain.py <id>`) name the same request. The client's address
 * chain is forwarded for the backend's per-IP limit; `next start` fills x-forwarded-for from
 * the socket when no load balancer has set it.
 */
export async function POST(request: Request) {
  const body = await request.text();
  if (body.length > MAX_BODY_BYTES) {
    return Response.json({ detail: "Request too large" }, { status: 413 });
  }

  const requestId = crypto.randomUUID().replaceAll("-", "");
  const forwardedFor = request.headers.get("x-forwarded-for");
  const traced = { "x-request-id": requestId };

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "text/event-stream",
        ...traced,
        ...(forwardedFor ? { "x-forwarded-for": forwardedFor } : {}),
      },
      body,
      cache: "no-store",
      signal: request.signal, // stop the backend work if the person leaves
    });
  } catch {
    return Response.json(
      { detail: "MarketLens can't reach its search service right now." },
      { status: 502, headers: traced },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    // 413 / 422 (bad input) and 429 (rate limit) mean something to the client; the rest is
    // the service failing.
    const status = [413, 422, 429].includes(upstream.status) ? upstream.status : 502;
    const retryAfter = upstream.headers.get("retry-after");
    return new Response(
      detail || JSON.stringify({ detail: `Search failed (${upstream.status})` }),
      {
        status,
        headers: {
          "content-type": "application/json",
          ...traced,
          ...(retryAfter ? { "retry-after": retryAfter } : {}),
        },
      },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
      ...traced,
    },
  });
}
