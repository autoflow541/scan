#!/usr/bin/env bash
# Bootstrap the accessibility scanner onto a VM that ALREADY hosts
# pdf.auto-flow.co (the remediation engine) with its own Caddy instance.
#
# Usage:
#   REPO_DIR=~/scan CORS_ORIGINS='*' bash setup-vm.sh
#
# What this does:
#   1. Verify Docker + Caddy are already installed (remediation's setup-vm.sh
#      installs both; this script does NOT reinstall them).
#   2. Build the scan-engine image (Playwright + Chromium + the compiled
#      frontend, all in one image -- see docker/Dockerfile) and start it on
#      127.0.0.1:8001.
#   3. Ensure /etc/caddy/Caddyfile imports /etc/caddy/sites/*.conf, then write
#      ONLY /etc/caddy/sites/scan.conf -- this script never overwrites the
#      whole Caddyfile and never touches remediation's site block.
#   4. Reload Caddy and verify the HTTPS health endpoint.
#
# One-time manual step if this is the FIRST product to adopt the per-site
# layout on this VM (i.e. /etc/caddy/Caddyfile still contains pdf.auto-flow.co's
# block directly, written by remediation's older setup-vm.sh): move that
# existing block into /etc/caddy/sites/pdf.conf by hand, then replace
# /etc/caddy/Caddyfile's contents with a single line:
#   import /etc/caddy/sites/*.conf
# This script deliberately does NOT do that migration for you, since it
# involves editing a file this project doesn't own.

set -euo pipefail

ENGINE_HOST="${ENGINE_HOST:-scan.auto-flow.co}"
CORS_ORIGINS="${CORS_ORIGINS:-*}"
MAX_CONCURRENT_SCANS="${MAX_CONCURRENT_SCANS:-3}"
REPO_DIR="${REPO_DIR:-$HOME/scan}"
CADDY_CFG="/etc/caddy/Caddyfile"
SITES_DIR="/etc/caddy/sites"
SITE_CFG="${SITES_DIR}/scan.conf"

echo "==> [1/5] Checking Docker + Caddy are present"
command -v docker &>/dev/null || { echo "ERROR: docker not found. Run remediation's setup-vm.sh first, or install it manually."; exit 1; }
command -v caddy &>/dev/null  || { echo "ERROR: caddy not found. Run remediation's setup-vm.sh first, or install it manually."; exit 1; }

echo "==> [2/5] Building the scan engine image (this takes a few minutes -- downloads Chromium + compiles the frontend)"
if [ ! -d "$REPO_DIR" ]; then
  echo "ERROR: Repo not found at $REPO_DIR"
  echo "Copy the project there first, e.g.:"
  echo "  scp -r ./scan user@VM_IP:~/scan"
  exit 1
fi
cd "$REPO_DIR"
docker build -f docker/Dockerfile -t scan-engine .

echo "==> [3/5] Starting the engine container"
docker rm -f scan-engine 2>/dev/null || true
docker run -d \
  --name scan-engine \
  --restart unless-stopped \
  -p 127.0.0.1:8001:8001 \
  -e "CORS_ORIGINS=${CORS_ORIGINS}" \
  -e "MAX_CONCURRENT_SCANS=${MAX_CONCURRENT_SCANS}" \
  scan-engine

echo "==> [4/5] Wiring up Caddy (merge-safe: only writes ${SITE_CFG})"
sudo mkdir -p "$SITES_DIR"
if ! grep -q "import ${SITES_DIR}/\*.conf" "$CADDY_CFG" 2>/dev/null; then
  echo ""
  echo "ERROR: ${CADDY_CFG} does not import ${SITES_DIR}/*.conf yet."
  echo "This VM's Caddyfile needs a one-time manual migration before this script"
  echo "can safely add scan.auto-flow.co without touching pdf.auto-flow.co's config:"
  echo "  1. Move the existing site block(s) in ${CADDY_CFG} into"
  echo "     ${SITES_DIR}/<name>.conf files (one block per file)."
  echo "  2. Replace ${CADDY_CFG}'s contents with just:"
  echo "       import ${SITES_DIR}/*.conf"
  echo "Re-run this script after that migration."
  exit 1
fi
sudo cp "$(dirname "$0")/Caddyfile" "$SITE_CFG"
sudo systemctl reload caddy || sudo systemctl restart caddy

echo "==> [5/5] Waiting for engine to be ready (up to 30s)"
for i in $(seq 1 15); do
  if curl -sf "https://${ENGINE_HOST}/health" | python3 -m json.tool; then
    echo ""
    echo "SUCCESS: scanner is live at https://${ENGINE_HOST}"
    exit 0
  fi
  echo "  (attempt $i/15, retrying in 2s...)"
  sleep 2
done

echo ""
echo "WARN: health check did not pass within 30s."
echo "Check container logs: docker logs scan-engine"
echo "Check Caddy logs:     sudo journalctl -u caddy -n 50"
