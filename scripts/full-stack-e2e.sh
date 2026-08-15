#!/usr/bin/env bash
set -euo pipefail

project="${FULL_STACK_COMPOSE_PROJECT:-codearena-full-stack-e2e}"
port="${FULL_STACK_FRONTEND_PORT:-18080}"
compose=(docker compose -p "$project" -f docker-compose.content-test.yml)

if [[ "$project" != codearena-full-stack-e2e* ]]; then
  echo "refusing to use a non-E2E Compose project" >&2
  exit 2
fi

cleanup() {
  python scripts/collect_full_stack_e2e_artifacts.py || true
  docker ps -aq \
    --filter label=codearena.role=untrusted-sandbox \
    --filter label=codearena.environment=codearena-full-stack-e2e \
    | xargs -r docker rm -f >/dev/null 2>&1 || true
  "${compose[@]}" down -v --remove-orphans || true
}
trap cleanup EXIT

export FULL_STACK_FRONTEND_PORT="$port"
export FULL_STACK_COMPOSE_PROJECT="$project"
"${compose[@]}" down -v --remove-orphans
docker pull node:22-bookworm-slim
docker pull node:22-alpine
"${compose[@]}" up --build -d --wait frontend-full-stack-e2e judge-service-content-test
"${compose[@]}" run --rm --no-deps content-invariants-e2e
(
  cd frontend
  npm run test:e2e:full
)
