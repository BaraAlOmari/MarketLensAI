import { getHealth } from "@/lib/backend";

// Proxies the FastAPI liveness check so it can be called from the browser or curl.
export async function GET() {
  const result = await getHealth();
  if (result.ok) return Response.json(result.data);
  return Response.json({ status: "error", error: result.error }, { status: 502 });
}
