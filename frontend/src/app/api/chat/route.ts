import { BACKEND_URL } from "@/lib/backend";

const MAX_BODY_BYTES = 8_000;

/**
 * Streams the FastAPI chat (server-sent events) to the browser. The backend URL stays on the
 * server, and the event stream is passed through untouched as it arrives.
 */
export async function POST(request: Request) {
  const body = await request.text();
  if (body.length > MAX_BODY_BYTES) {
    return Response.json({ detail: "Request too large" }, { status: 413 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body,
      cache: "no-store",
      signal: request.signal, // stop the backend work if the person leaves
    });
  } catch {
    return Response.json(
      { detail: "MarketLens can't reach its search service right now." },
      { status: 502 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return new Response(
      detail || JSON.stringify({ detail: `Search failed (${upstream.status})` }),
      {
        status: upstream.status === 422 ? 422 : 502,
        headers: { "content-type": "application/json" },
      },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
    },
  });
}
