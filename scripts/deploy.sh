#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "🚀 Iniciando deploy en $(hostname) — $(date)"

docker compose up -d --build

docker image prune -f >/dev/null 2>&1 || true

echo "✅ Deploy completado — $(date)"
docker compose ps
