#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python prepare_static.py
export FF_ENV=development
export FF_COOKIE_SECURE=0
export FF_PUBLIC_BASE_URL="https://${REPLIT_DEV_DOMAIN:?Replit development domain is required}"
exec python -m uvicorn app:app --host 0.0.0.0 --port 5000 --proxy-headers --forwarded-allow-ips="*"