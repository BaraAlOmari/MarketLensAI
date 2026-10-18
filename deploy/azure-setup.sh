#!/usr/bin/env bash
# One-time Azure setup for MarketLens: two container apps (private API, public UI) in Japan East,
# next to the Supabase database in Tokyo. Safe to re-run: existing resources are updated.
#
# Needs `az login` and backend/.env with DATABASE_URL and GEMINI_API_KEY. The two secrets go
# straight from that file into Container Apps secrets; they are never printed.
# Images are deployed by .github/workflows/deploy.yml (see deploy/README.md for its identity);
# until its first run the apps run a placeholder image.
#
#   bash deploy/azure-setup.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1 # Git Bash on Windows: leave /subscriptions/... arguments alone

LOCATION=${LOCATION:-japaneast}
RG=${RG:-marketlens-rg}
LOGS=${LOGS:-marketlens-logs}
ENV_NAME=${ENV_NAME:-marketlens-env}
API=${API:-marketlens-api}
WEB=${WEB:-marketlens-web}
PLACEHOLDER=mcr.microsoft.com/k8se/quickstart:latest

cd "$(dirname "$0")/.."
env_value() { sed -n "s/^$1=//p" backend/.env | tr -d '\r' | tail -n 1; }
DATABASE_URL=$(env_value DATABASE_URL)
GEMINI_API_KEY=$(env_value GEMINI_API_KEY)
if [ -z "$DATABASE_URL" ] || [ -z "$GEMINI_API_KEY" ]; then
  echo "backend/.env needs DATABASE_URL and GEMINI_API_KEY" >&2
  exit 1
fi

exists() { "$@" --only-show-errors >/dev/null 2>&1; }

echo "Resource group $RG ($LOCATION)"
az group create -n "$RG" -l "$LOCATION" --only-show-errors -o none

echo "Log Analytics workspace $LOGS (30-day retention, inside the 31 free days)"
az monitor log-analytics workspace create -g "$RG" -n "$LOGS" -l "$LOCATION" \
  --retention-time 30 --only-show-errors -o none
LOGS_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LOGS" --query customerId -o tsv)
LOGS_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "$LOGS" \
  --query primarySharedKey -o tsv)

if ! exists az containerapp env show -g "$RG" -n "$ENV_NAME"; then
  echo "Container Apps environment $ENV_NAME"
  az containerapp env create -g "$RG" -n "$ENV_NAME" -l "$LOCATION" \
    --logs-workspace-id "$LOGS_ID" --logs-workspace-key "$LOGS_KEY" --only-show-errors -o none
fi

# Both apps: scale to zero when idle (inside the monthly free grant), one replica at most
# (the per-IP rate limit counts in process memory; also caps the cost).
SIZE=(--min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi)
# Browser -> external ingress -> UI -> internal ingress -> API: both ingress hops append to
# X-Forwarded-For, so the client is 2 entries from the right.
API_ENV=(DATABASE_URL=secretref:database-url GEMINI_API_KEY=secretref:gemini-api-key
  ENVIRONMENT=production LOG_LEVEL=INFO FORWARDED_HOPS=2)

if exists az containerapp show -g "$RG" -n "$API"; then
  echo "Updating $API secrets and settings"
  az containerapp secret set -g "$RG" -n "$API" --only-show-errors -o none \
    --secrets database-url="$DATABASE_URL" gemini-api-key="$GEMINI_API_KEY"
  az containerapp update -g "$RG" -n "$API" "${SIZE[@]}" --set-env-vars "${API_ENV[@]}" \
    --only-show-errors -o none
else
  echo "Creating $API (internal ingress: reachable only from inside the environment)"
  az containerapp create -g "$RG" -n "$API" --environment "$ENV_NAME" --image "$PLACEHOLDER" \
    --ingress internal --target-port 8000 "${SIZE[@]}" --only-show-errors -o none \
    --secrets database-url="$DATABASE_URL" gemini-api-key="$GEMINI_API_KEY" \
    --env-vars "${API_ENV[@]}"
fi
API_FQDN=$(az containerapp show -g "$RG" -n "$API" \
  --query properties.configuration.ingress.fqdn -o tsv)

if exists az containerapp show -g "$RG" -n "$WEB"; then
  echo "Updating $WEB settings"
  az containerapp update -g "$RG" -n "$WEB" "${SIZE[@]}" \
    --set-env-vars BACKEND_URL="https://$API_FQDN" --only-show-errors -o none
else
  echo "Creating $WEB (public ingress)"
  az containerapp create -g "$RG" -n "$WEB" --environment "$ENV_NAME" --image "$PLACEHOLDER" \
    --ingress external --target-port 3000 "${SIZE[@]}" --only-show-errors -o none \
    --env-vars BACKEND_URL="https://$API_FQDN"
fi
WEB_FQDN=$(az containerapp show -g "$RG" -n "$WEB" \
  --query properties.configuration.ingress.fqdn -o tsv)
az containerapp update -g "$RG" -n "$API" --set-env-vars CORS_ORIGINS="https://$WEB_FQDN" \
  --only-show-errors -o none

echo
echo "Done."
echo "  UI:  https://$WEB_FQDN"
echo "  API: https://$API_FQDN (internal only)"
