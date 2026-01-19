#!/usr/bin/env bash
set -euo pipefail
# Start Vite dev server from repository frontend directory
cd "$(dirname "$0")/../frontend"
# Use npx to ensure correct binary, forward any args to vite
npm run dev "$@"
