#!/usr/bin/env bash
set -euo pipefail

# scripts/wiki_login.sh
#  - Logs into Wikimedia Enterprise using username/password
#  - Saves access_token with expiry to .wiki_token.json OR saves cookies to .wiki_cookies.txt
#  - Usage: ./scripts/wiki_login.sh   (prompts for username/password) or
#           WIKI_USER=... WIKI_PASS=... ./scripts/wiki_login.sh

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

WIKI_AUTH_URL="${WIKI_AUTH_URL:-https://auth.enterprise.wikimedia.com/v1/login}"

# Read username/password from env or prompt
if [ -z "${WIKI_USER:-}" ]; then
  read -p "WIKI_USER: " WIKI_USER
fi
if [ -z "${WIKI_PASS:-}" ]; then
  read -s -p "Password: " WIKI_PASS; echo
fi

TMP_RESP=".wiki_login_resp.json"
HEADERS=".wiki_login_headers.txt"
COOKIES=".wiki_cookies.txt"
TOKEN_FILE=".wiki_token.json"

# Try JSON response auth (common pattern)
# Save body and headers so we can inspect both
curl -sS -X POST "$WIKI_AUTH_URL" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$WIKI_USER\",\"password\":\"$WIKI_PASS\"}" \
  -D "$HEADERS" -o "$TMP_RESP"

# Try to extract access_token and expires_in using python json parsing (no jq required)
access_token=$(python - <<PY
import json,sys
try:
    j=json.load(open('$TMP_RESP'))
    t=j.get('access_token')
    if t:
        print(t)
except Exception:
    pass
PY
)

if [ -n "$access_token" ] ; then
  expires_in=$(python - <<PY
import json
try:
    j=json.load(open('$TMP_RESP'))
    print(int(j.get('expires_in',0)))
except Exception:
    print(0)
PY
)
  now=$(date +%s)
  expiry=$(( now + (expires_in?expires_in:0) - 60 ))
  # If expires_in is zero or missing, set a long-ish expiry (1h) defensively
  if [ "$expiry" -le "$now" ]; then
    expiry=$(( now + 3600 - 60 ))
  fi
  # Write token file
  python - <<PY
import json
obj={'access_token':'%s','expires_at':%d}
obj['access_token']='%s'
obj['expires_at']=%d
open('$TOKEN_FILE','w').write(json.dumps(obj))
PY
  # The above python block uses placeholders handled by shell; simpler: use printf
  printf '{"access_token": "%s", "expires_at": %d}\n' "$access_token" "$expiry" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  rm -f "$TMP_RESP" "$HEADERS"
  echo "Saved token to $TOKEN_FILE (expires: $(date -d @$expiry))"
  exit 0
fi

# Otherwise try cookie-based session
# Re-run curl to capture cookies explicitly (some endpoints may set cookies only on form posts)
curl -sS -c "$COOKIES" -X POST "$WIKI_AUTH_URL" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$WIKI_USER\",\"password\":\"$WIKI_PASS\"}" -D "$HEADERS" -o /dev/null

# Check if cookies file has at least one cookie
if [ -f "$COOKIES" ] && [ -s "$COOKIES" ]; then
  chmod 600 "$COOKIES"
  rm -f "$TMP_RESP" "$HEADERS"
  echo "Saved cookies to $COOKIES"
  exit 0
fi

# If we get here, login failed
echo "Login failed: response preview:" >&2
python - <<PY
import json,sys
try:
    print(open('$TMP_RESP').read())
except Exception as e:
    print('No response')
PY

exit 1
