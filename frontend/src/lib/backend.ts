import "server-only";

// Server-side only: the browser talks to Next.js, and Next.js talks to FastAPI.
export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: "ok";
  app: string;
  version: string;
  database: { configured: boolean; ok: boolean; pgvector: string | null };
};

export type HealthResult =
  | { ok: true; data: HealthResponse; latencyMs: number }
  | { ok: false; error: string; latencyMs: number };

export async function getHealth(): Promise<HealthResult> {
  const started = performance.now();
  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const latencyMs = Math.round(performance.now() - started);
    if (!res.ok) return { ok: false, error: `Backend returned HTTP ${res.status}`, latencyMs };
    return { ok: true, data: (await res.json()) as HealthResponse, latencyMs };
  } catch (err) {
    const latencyMs = Math.round(performance.now() - started);
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, error: `Backend unreachable at ${BACKEND_URL}: ${message}`, latencyMs };
  }
}
