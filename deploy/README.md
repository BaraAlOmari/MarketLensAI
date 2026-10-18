# Deploying MarketLens to Azure

```
Browser ──► marketlens-web  (Next.js, public HTTPS)
                │  internal ingress, same environment
                ▼
            marketlens-api  (FastAPI, not reachable from the internet)
                ├──► Supabase Postgres (Tokyo)
                └──► Gemini API
```

Both run on Azure Container Apps (Consumption plan) in **Japan East**, next to the Supabase
database in Tokyo. They scale to zero when idle and to at most one replica, which keeps them
inside the monthly free grant. Images are built by GitHub Actions and stored in GitHub
Container Registry.

## One-time setup

1. **Azure resources.** Logged in with `az login`, from the repository root:

   ```bash
   bash deploy/azure-setup.sh
   ```

   This creates the resource group `marketlens-rg`, a Log Analytics workspace (30-day
   retention), the Container Apps environment and both apps (with a placeholder image), and
   copies `DATABASE_URL` and `GEMINI_API_KEY` from `backend/.env` into Container Apps secrets.
   It is safe to re-run, for example after rotating a key.

2. **Deploy identity for GitHub Actions.** A user-assigned managed identity that GitHub can
   log in as with a short-lived OIDC token, so no Azure password or key is stored in GitHub.
   It may manage only `marketlens-rg`, and only from the repository's `production`
   environment. GitHub's token subject names the owner and repository with their numeric
   IDs (`owner@id/repo@id`); a failed login prints the exact subject it presented.

   ```bash
   az identity create -g marketlens-rg -n marketlens-github-deploy -l japaneast
   az identity federated-credential create -g marketlens-rg \
     --identity-name marketlens-github-deploy -n github-production \
     --issuer https://token.actions.githubusercontent.com \
     --subject "repo:BaraAlOmari@195624165/MarketLensAI@1408861496:environment:production" \
     --audiences api://AzureADTokenExchange
   MSYS_NO_PATHCONV=1 az role assignment create --role Contributor \
     --assignee-object-id "$(az identity show -g marketlens-rg -n marketlens-github-deploy --query principalId -o tsv)" \
     --assignee-principal-type ServicePrincipal \
     --scope "$(az group show -n marketlens-rg --query id -o tsv)"
   ```

3. **Repository variables** (GitHub → Settings → Secrets and variables → Actions →
   Variables). These are identifiers, not secrets:

   | Variable | Value |
   |---|---|
   | `AZURE_CLIENT_ID` | `az identity show -g marketlens-rg -n marketlens-github-deploy --query clientId -o tsv` |
   | `AZURE_TENANT_ID` | `az account show --query tenantId -o tsv` |
   | `AZURE_SUBSCRIPTION_ID` | `az account show --query id -o tsv` |

4. **First deploy.** Push to `main`. When CI passes, the Deploy workflow builds and pushes
   `ghcr.io/baraalomari/marketlens-api` and `marketlens-web`. New GHCR packages are private,
   and Container Apps pulls without credentials, so make both packages public once (GitHub →
   your profile → Packages → package → Package settings → Change visibility). The images hold
   only the code that is already public in this repository. Then re-run the Deploy workflow.

After that, every push to `main` that passes CI is deployed automatically, tagged with its
commit SHA.

## Running it

| Task | Command |
|---|---|
| Live logs of the API | `az containerapp logs show -g marketlens-rg -n marketlens-api --follow` |
| Roll back | `az containerapp update -g marketlens-rg -n marketlens-api --image ghcr.io/baraalomari/marketlens-api:<older sha>` |
| Rotate a secret | edit `backend/.env`, then `bash deploy/azure-setup.sh` |
| Delete everything | `az group delete -n marketlens-rg` |

To explain a request from the deployed logs (the UI shows its reference on errors), query
the Log Analytics workspace:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "marketlens-api" and Log_s has "<request id>"
| project TimeGenerated, Log_s
```

## Known limits

- **Cold starts.** After about 5 idle minutes both apps scale to zero. Waking takes about
  17 s for the UI and 25 s for the API, almost all of it Azure pulling and creating the
  container. The page pings `/api/health` as it loads, so the API wakes while the visitor
  is still typing.
- **Rate-limit counts reset** when the API scales to zero (they live in memory).
  Conversations are kept in Postgres, so they survive it.
- **Cost guard.** A $1 monthly budget on `marketlens-rg` emails the account owner when actual
  or forecast spending passes $1. Normal demo traffic stays inside the free grant (about 100
  hours a month with both apps awake); one replica per app caps the worst case.
- **One shared Gemini free quota** for every visitor; the per-IP limit (12 a minute, 300 a
  day) stops one visitor from using it all.
- **Supabase free projects pause** after a week without activity. `keepalive.yml` calls
  `/api/health` (which queries the database) every three days to prevent that.
