import { connection } from "next/server";
import { Suspense } from "react";

import { getHealth } from "@/lib/backend";

function Row({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <dt className="text-sm opacity-70">{label}</dt>
      <dd className="flex items-center gap-2 font-mono text-sm">
        <span
          aria-hidden
          className={`inline-block h-2 w-2 rounded-full ${good ? "bg-emerald-500" : "bg-amber-500"}`}
        />
        {value}
      </dd>
    </div>
  );
}

async function HealthCard() {
  await connection(); // render at request time, never prerender a stale status
  const result = await getHealth();

  if (!result.ok) {
    return (
      <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm">
        <p className="font-semibold">Backend is down</p>
        <p className="mt-1 break-words opacity-80">{result.error}</p>
      </div>
    );
  }

  const { data, latencyMs } = result;
  const db = data.database;
  const dbValue = !db.configured ? "not configured" : db.ok ? "connected" : "error";

  return (
    <dl className="divide-y divide-current/10">
      <Row label="API" value={`${data.status.toUpperCase()} (${latencyMs} ms)`} good />
      <Row label="Version" value={data.version} good />
      <Row label="Database" value={dbValue} good={db.ok} />
      <Row
        label="pgvector"
        value={db.pgvector ? `v${db.pgvector}` : "not detected"}
        good={db.pgvector !== null}
      />
    </dl>
  );
}

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">MarketLens</h1>
      <p className="mt-1 text-sm opacity-70">Natural-language marketplace search. System status:</p>
      <section className="mt-6 rounded-xl border border-current/15 p-5">
        <Suspense fallback={<p className="text-sm opacity-70">Checking backend…</p>}>
          <HealthCard />
        </Suspense>
      </section>
    </main>
  );
}
