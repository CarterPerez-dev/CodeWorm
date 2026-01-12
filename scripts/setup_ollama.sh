#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-qwen2.5:7b}"
OLLAMA_HOST="${OLLAMA_HOST:-localhost}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_ollama_installed() {
    if ! command -v ollama &> /dev/null; then
        log_error "Ollama is not installed"
        echo ""
        echo "Install Ollama:"
        echo "  curl -fsSL https://ollama.com/install.sh | sh"
        echo ""
        exit 1
    fi
    log_info "Ollama is installed"
}

check_ollama_running() {
    if curl -s "http://$OLLAMA_HOST:$OLLAMA_PORT/api/tags" > /dev/null 2>&1; then
        log_info "Ollama is running at $OLLAMA_HOST:$OLLAMA_PORT"
        return 0
    else
        log_warn "Ollama is not running"
        return 1
    fi
}

start_ollama() {
    log_info "Starting Ollama..."

    if systemctl is-active --quiet ollama 2>/dev/null; then
        log_info "Ollama systemd service is already running"
        return 0
    fi

    if systemctl list-unit-files | grep -q ollama.service; then
        log_info "Starting Ollama via systemd..."
        sudo systemctl start ollama
        sleep 3
    else
        log_info "Starting Ollama in background..."
        nohup ollama serve > /dev/null 2>&1 &
        sleep 5
    fi

    if check_ollama_running; then
        return 0
    else
        log_error "Failed to start Ollama"
        exit 1
    fi
}

pull_model() {
    log_info "Pulling model $MODEL..."

    if ollama list | grep -q "$MODEL"; then
        log_info "Model $MODEL is already downloaded"
    else
        log_info "Downloading $MODEL (this may take a while)..."
        ollama pull "$MODEL"
    fi
}

configure_ollama_systemd() {
    log_info "Configuring Ollama systemd overrides..."

    if [[ ! -f /etc/systemd/system/ollama.service ]]; then
        log_warn "Ollama systemd service not found, skipping configuration"
        return 0
    fi

    mkdir -p /etc/systemd/system/ollama.service.d

    cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_KEEP_ALIVE=-1"
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF

    systemctl daemon-reload
    log_info "Ollama systemd overrides configured"
}

prewarm_model() {
    log_info "Pre-warming model $MODEL..."

    curl -s "http://$OLLAMA_HOST:$OLLAMA_PORT/api/generate" \
        -d "{\"model\": \"$MODEL\", \"prompt\": \"\", \"keep_alive\": \"-1\"}" \
        > /dev/null

    log_info "Model loaded and will stay in memory"
}

test_model() {
    log_info "Testing model $MODEL..."

    response=$(curl -s "http://$OLLAMA_HOST:$OLLAMA_PORT/api/generate" \
        -d "{\"model\": \"$MODEL\", \"prompt\": \"Say hello in exactly 5 words.\", \"stream\": false}" \
        | grep -o '"response":"[^"]*"' | head -1 || echo "")

    if [[ -n "$response" ]]; then
        log_info "Model test successful"
        echo "Response: $response"
    else
        log_error "Model test failed"
        exit 1
    fi
}

print_status() {
    echo ""
    echo "=============================================="
    echo -e "${GREEN}Ollama Setup Complete${NC}"
    echo "=============================================="
    echo ""
    echo "Status:"
    echo "  Host: $OLLAMA_HOST:$OLLAMA_PORT"
    echo "  Model: $MODEL"
    echo ""
    echo "Model info:"
    ollama show "$MODEL" --modelfile 2>/dev/null | head -5 || echo "  (run 'ollama show $MODEL' for details)"
    echo ""
    echo "Test with:"
    echo "  ollama run $MODEL \"Hello, world\""
    echo ""
}

main() {
    echo "=============================================="
    echo "  Ollama Setup for CodeWorm"
    echo "=============================================="
    echo ""

    check_ollama_installed

    if ! check_ollama_running; then
        start_ollama
    fi

    pull_model

    if [[ $EUID -eq 0 ]]; then
        configure_ollama_systemd
    else
        log_warn "Not running as root, skipping systemd configuration"
    fi

    prewarm_model
    test_model
    print_status
}

main "$@"
