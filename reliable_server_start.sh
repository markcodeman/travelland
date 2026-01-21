#!/bin/bash
# Reliable Hypercorn server start script for TravelLand
set -e
cd "$(dirname "$0")/city_guides"
export PYTHONPATH=..
source venv/bin/activate
# Kill any existing Hypercorn processes
pkill -f 'hypercorn' || true
sleep 1
# Check if port 5010 is free
if ss -tuln | grep -q ':5010'; then
  echo "Port 5010 is still in use. Aborting."
  exit 1
fi
# Start Hypercorn and log output
exec hypercorn app.py --bind 0.0.0.0:5010 2>&1 | tee ../../hypercorn.log
