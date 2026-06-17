#!/usr/bin/env bash
# Pull an Ollama model into the running containerized `ollama` service.
#
# Run AFTER the stack is up:
#   docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml up -d
#   dev/ollama/pull-model.sh            # uses DEFAULT_MODEL from the repo-root .env
#   dev/ollama/pull-model.sh bielik     # or pass an explicit model name
#
# The gateway uses the model named by DEFAULT_MODEL (repo-root .env) unless a
# request overrides it, so pull the SAME model you set there.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
core_compose="$repo_root/docker-compose.yml"
ollama_compose="$repo_root/dev/ollama/docker-compose.ollama.yml"

model="${1:-}"

if [[ -z "$model" && -f "$repo_root/.env" ]]; then
  model="$(grep -E '^DEFAULT_MODEL=' "$repo_root/.env" | tail -n 1 | cut -d= -f2- | tr -d '"' | xargs || true)"
fi

if [[ -z "$model" ]]; then
  echo "No model given and DEFAULT_MODEL not found in .env." >&2
  echo "Usage: $0 <model>   (e.g. $0 llama3)" >&2
  exit 1
fi

echo "Pulling Ollama model: $model"
docker compose -f "$core_compose" -f "$ollama_compose" exec ollama ollama pull "$model"
echo "Done. Set DEFAULT_MODEL=$model in .env so the gateway uses it."
