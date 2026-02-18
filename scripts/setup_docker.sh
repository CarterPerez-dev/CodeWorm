#!/usr/bin/env bash
# ©AngelaMos | 2026
# setup_docker.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[setup]${NC} $*"; }
ok()  { echo -e "${GREEN}[  ok ]${NC} $*"; }
warn(){ echo -e "${YELLOW}[ warn]${NC} $*"; }
err() { echo -e "${RED}[error]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

command -v docker >/dev/null 2>&1 || err "docker is not installed"
ok "docker found"

docker compose version >/dev/null 2>&1 || err "docker compose plugin not found"
ok "docker compose found"

if command -v nvidia-smi >/dev/null 2>&1; then
    ok "nvidia GPU detected"
    if dpkg -l 2>/dev/null | grep -q nvidia-container-toolkit; then
        ok "nvidia-container-toolkit installed"
    else
        warn "nvidia-container-toolkit not found - GPU passthrough may not work"
        warn "Install with: sudo apt install nvidia-container-toolkit"
    fi
else
    warn "No nvidia GPU detected - Ollama will run on CPU"
fi

ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example "$ENV_FILE"
        ok "Created .env from .env.example"
    else
        err ".env.example not found"
    fi
fi

log "Starting docker compose stack..."
docker compose --env-file "$ENV_FILE" up -d

log "Waiting for Ollama to be ready..."
OLLAMA_CONTAINER="${APP_NAME:-codeworm}-ollama"
for i in $(seq 1 30); do
    if docker exec "$OLLAMA_CONTAINER" curl -sf http://localhost:11434/ >/dev/null 2>&1; then
        ok "Ollama is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        err "Ollama failed to start within 60s"
    fi
    sleep 2
done

MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
log "Pulling model: $MODEL"
docker exec "$OLLAMA_CONTAINER" ollama pull "$MODEL"
ok "Model $MODEL pulled"

log "Pre-warming model..."
docker exec "$OLLAMA_CONTAINER" sh -c "echo 'hello' | ollama run $MODEL --nowordwrap" >/dev/null 2>&1 || true
ok "Model pre-warmed"

log "Verifying services..."
docker compose --env-file "$ENV_FILE" ps

echo ""
ok "Setup complete!"
log "Ollama: http://localhost:${OLLAMA_HOST_PORT:-47311}"
log "Redis:  localhost:${REDIS_HOST_PORT:-26849}"
log "Dashboard: http://localhost:${NGINX_HOST_PORT:-38491}"
