#!/usr/bin/env bash
# Start the scan engine container.
#
# Usage:
#   ./run-engine.sh
#   CORS_ORIGINS='*' ./run-engine.sh
#
# Run this AFTER the image is built:
#   docker build -f docker/Dockerfile -t scan-engine .
#
# To update later: stop + remove the old container, then re-run this script.
#   docker stop scan-engine && docker rm scan-engine

set -euo pipefail

CORS_ORIGINS="${CORS_ORIGINS:-*}"
MAX_CONCURRENT_SCANS="${MAX_CONCURRENT_SCANS:-3}"
LEADS_DIR="${LEADS_DIR:-$HOME/scan-leads}"

# Host-mounted so captured leads survive container recreation. uid 10001
# matches the non-root `appuser` the image runs as (see docker/Dockerfile).
mkdir -p "$LEADS_DIR"
sudo chown 10001:10001 "$LEADS_DIR"

docker run -d \
  --name scan-engine \
  --restart unless-stopped \
  -p 127.0.0.1:8001:8001 \
  -e "CORS_ORIGINS=${CORS_ORIGINS}" \
  -e "MAX_CONCURRENT_SCANS=${MAX_CONCURRENT_SCANS}" \
  -v "${LEADS_DIR}:/app/leads" \
  scan-engine

echo "Engine started. Health check:"
sleep 2
curl -sf http://localhost:8001/health | python3 -m json.tool || echo "(curl failed — container may still be starting)"
