#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export FF_ENV=development
export FF_COOKIE_SECURE=0
export FF_PUBLIC_BASE_URL="${FF_PUBLIC_BASE_URL:-http://127.0.0.1:8000}"
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
