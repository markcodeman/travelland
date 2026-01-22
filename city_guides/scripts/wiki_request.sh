#!/usr/bin/env bash
set -euo pipefail

# scripts/wiki_request.sh
# Usage:
#   ./scripts/wiki_request.sh GET "https://enterprise.wikimedia.com/endpoint" [--data '{"key": "val"}']
# This script picks the best auth (Bearer token or cookies) and refreshes if needed.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

METHOD=${1:-GET}
URL=${2:-}
shift 2 || true
DATA=""
if [ "${1:-}" = "--data" ]; then
  DATA=${2:-}
fi

TOKEN_FILE=".wiki_token.json"
COOKIES=".wiki_cookies.txt"

# helper: refresh token via login script
_refresh() {
  echo "Refreshing login..."
  ./scripts/wiki_login.sh
}

# pick auth mode
if [ -f "$TOKEN_FILE" ]; then
  # Check expiry
  exp=$(python - <<PY
import json
j=json.load(open('$TOKEN_FILE'))
print(j.get('expires_at',0))
PY
)
  now=$(date +%s)
  if [ "$exp" -lt "$now" ]; then
    echo "Token expired, refreshing..."
    _refresh
  fi
  TOKEN=$(python - <<PY
import json
j=json.load(open('$TOKEN_FILE'))
print(j.get('access_token',''))
PY
)
  if [ -n "$TOKEN" ]; then
    if [ -n "$DATA" ]; then
      curl -sS -X "$METHOD" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$DATA" "$URL"
    else
      curl -sS -X "$METHOD" -H "Authorization: Bearer $TOKEN" "$URL"
    fi
    exit 0
  fi
fi

# fallback to cookies
if [ -f "$COOKIES" ]; then
  if [ -n "$DATA" ]; then
    curl -sS -b "$COOKIES" -X "$METHOD" -H "Content-Type: application/json" -d "$DATA" "$URL"
  else
    curl -sS -b "$COOKIES" -X "$METHOD" "$URL"
  fi
  exit 0
fi

# no auth present: run login and retry
echo "No token or cookies found — logging in..."
_refresh
exec "$0" "$METHOD" "$URL" --data "$DATA"
