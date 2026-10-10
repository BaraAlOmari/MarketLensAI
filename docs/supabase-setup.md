# Supabase Setup (Stage 0)

About 10 minutes. You end with a free Supabase project that has pgvector enabled and a `DATABASE_URL` in `backend/.env`.

Facts below were checked on 2026-10-10 (see `docs/decisions.md`). Dashboard labels change from time to time; if a button has moved, look for the same words.

## 1. Create the project

1. Go to https://supabase.com/dashboard and sign in (GitHub sign-in is fine).
2. If asked, create an **organization** and choose the **Free** plan.
3. Click **New project** and fill in:
   - **Name:** `marketlens`
   - **Database password:** click **Generate a password**, then **copy it into a password manager right now**. You need it for the connection string, and Supabase will not show it again (you can only reset it).
     Tip: a password with only letters and digits saves you from URL-encoding later.
   - **Region:** pick the region closest to you. Later the Azure backend should go in a nearby region too, so latency stays low.
   - Leave the other options (Data API, security settings) at their defaults.
4. Click **Create new project** and wait 1 to 2 minutes for it to provision.

## 2. Enable pgvector

Pick **one** option.

**Option A, dashboard:**
1. Left sidebar: **Database**, then **Extensions**.
2. Search for `vector`.
3. Toggle it on. When asked for a schema, choose **`extensions`**.

**Option B, SQL editor:**
1. Left sidebar: **SQL Editor**, then **New query**.
2. Run:
   ```sql
   create extension if not exists vector with schema extensions;
   select extversion from pg_extension where extname = 'vector';
   ```
3. The second statement should return one row with a version number.

(Option C: skip this and run `verify_db.py --enable` in step 4. The script creates the extension for you.)

## 3. Get the connection string

1. Click the **Connect** button at the top of the project page.
2. Choose **Session pooler**. This mode works over IPv4. The "Direct connection" mode is IPv6-only on the free plan and often fails from home networks and from Azure.
3. Copy the URI. It looks like:
   ```
   postgresql://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```
   Copy the host exactly as shown; don't build it by hand. The `aws-0` / `aws-1` prefix varies.
4. Replace `[YOUR-PASSWORD]` (brackets included) with your database password. If the password contains reserved characters, percent-encode them: `@` → `%40`, `#` → `%23`, `&` → `%26`, `?` → `%3F`, `/` → `%2F`, `:` → `%3A`, space → `%20`.

## 4. Configure and verify locally

From the project root in PowerShell:

```powershell
cd backend
Copy-Item .env.example .env
notepad .env        # paste the URI into DATABASE_URL=...
.venv\Scripts\python scripts\verify_db.py
```

Expected output:

```
OK: connected (Postgres <version>)
OK: pgvector 0.8.x installed in schema 'extensions'
OK: vector distance query works (L2 distance = 1.0)
OK: configured EMBEDDING_DIMENSION=1536 (HNSW on vector supports <= 2000)
```

If pgvector is missing, run `.venv\Scripts\python scripts\verify_db.py --enable`.

Then confirm it end to end:

```powershell
# terminal 1 (backend/)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# terminal 2 (frontend/)
npm run dev
```

Open http://localhost:3000. The status card should show **API OK**, **Database connected**, and **pgvector v0.8.x**.

## 5. Gemini API key (needed from Stage 1)

1. Go to https://aistudio.google.com/apikey and click **Create API key**.
2. Paste it into `GEMINI_API_KEY=` in `backend/.env`.
3. Open https://aistudio.google.com/rate-limit and note the free-tier RPM / TPM / RPD for `gemini-3.8-flash` and `gemini-embedding-2`. The docs no longer publish these numbers, and the Stage 1 generator is sized from them.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `getaddrinfo failed` / `gaierror` | You used the Direct connection (IPv6). Switch to the **Session pooler** URI. |
| `password authentication failed` | Wrong password or un-encoded special characters. Reset it under **Project Settings > Database**, or percent-encode it. |
| `Tenant or user not found` | The username must be `postgres.<project-ref>` for the pooler, not plain `postgres`. Copy the URI again from **Connect**. |
| Timeouts after a quiet week | Free projects **pause after 7 days of inactivity**. Open the dashboard and click **Restore project**. |

## Security notes

- `backend/.env` is git-ignored. Never commit it, and never paste the password into the frontend.
- MarketLens talks to Postgres directly and does not use Supabase's auto-generated REST API. Stage 1 migrations will **enable Row Level Security** on every table (with no public policies), so the public `anon` key cannot read or change them through the Data API. The backend's `postgres` role is unaffected.
