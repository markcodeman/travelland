#!/usr/bin/env bash
# Live MCP screenshot streamer
# Usage: ./scripts/mcp_live.sh
set -euo pipefail
BASE_MCP=http://127.0.0.1:8766/mcp/execute
OUT_DIR=./tmp
OUT_IMAGE=${OUT_DIR}/mcp_screenshot.png
mkdir -p "$OUT_DIR"
# initial actions: navigate, fill city and query, click
curl -s -X POST -H "Content-Type: application/json" -d '{"tool_id":"navigate","params":{"url":"http://127.0.0.1:5010/"}}' "$BASE_MCP" >/dev/null
sleep 0.2
curl -s -X POST -H "Content-Type: application/json" -d '{"tool_id":"type_text","params":{"selector":"#city","text":"London"}}' "$BASE_MCP" >/dev/null
sleep 0.1
curl -s -X POST -H "Content-Type: application/json" -d '{"tool_id":"type_text","params":{"selector":"#q","text":"burger"}}' "$BASE_MCP" >/dev/null
sleep 0.1
curl -s -X POST -H "Content-Type: application/json" -d '{"tool_id":"click","params":{"selector":"#searchBtn"}}' "$BASE_MCP" >/dev/null
sleep 1
# loop: request screenshot and save locally
while true; do
  curl -s -X POST -H "Content-Type: application/json" -d "{\"tool_id\":\"screenshot\",\"params\":{\"path\":\"$(pwd)/${OUT_IMAGE}\"}}" "$BASE_MCP" >/dev/null
  sleep 1
done
