import { getHealth } from "@/lib/backend";

// Proxies the FastAPI liveness check so it can be called from the browser or curl. The page
// also calls it on load to wake a scaled-to-zero backend. The detailed error (it names the
// internal backend URL) goes to the server log only.
export async function GET() {
  const result = await getHealth();
  if (result.ok) return Response.json(result.data);
  console.error(`health check failed: ${result.error}`);
  return Response.json(
    { status: "error", error: "The search service isn't reachable yet." },
    { status: 502 },
  );
}
