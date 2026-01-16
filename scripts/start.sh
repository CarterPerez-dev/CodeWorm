#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

OLLAMA_HOST="${OLLAMA_HOST:-localhost}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
MODEL="${MODEL:-qwen2.5:7b}"

check_ollama() {
    curl -s "http://$OLLAMA_HOST:$OLLAMA_PORT/" > /dev/null 2>&1
}

ensure_ollama() {
    if check_ollama; then
        log_info "Ollama is running"
        return 0
    fi

    log_warn "Ollama not running, starting..."

    if systemctl is-active --quiet ollama 2>/dev/null; then
        log_info "Ollama service already active"
        return 0
    fi

    if systemctl list-unit-files 2>/dev/null | grep -q "^ollama.service"; then
        sudo systemctl start ollama
        sleep 3
    else
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 5
    fi

    if check_ollama; then
        log_info "Ollama started successfully"

        if ! ollama list 2>/dev/null | grep -q "$MODEL"; then
            log_warn "Model $MODEL not found, pulling..."
            ollama pull "$MODEL"
        fi

        log_info "Pre-warming model..."
        curl -s "http://$OLLAMA_HOST:$OLLAMA_PORT/api/generate" \
            -d "{\"model\": \"$MODEL\", \"prompt\": \"\", \"keep_alive\": \"-1\"}" > /dev/null
        log_info "Model loaded"
        return 0
    else
        log_error "Failed to start Ollama"
        return 1
    fi
}

show_status() {
    echo ""
    echo "═══════════════════════════════════════════"
    echo "  CodeWorm Status"
    echo "═══════════════════════════════════════════"
    echo ""

    if check_ollama; then
        echo -e "  Ollama:    ${GREEN}Running${NC} (http://$OLLAMA_HOST:$OLLAMA_PORT)"
    else
        echo -e "  Ollama:    ${RED}Not Running${NC}"
    fi

    if pgrep -f "codeworm run" > /dev/null 2>&1; then
        echo -e "  CodeWorm:  ${GREEN}Running${NC}"
    else
        echo -e "  CodeWorm:  ${YELLOW}Not Running${NC}"
    fi

    echo ""
}

start_daemon() {
    if pgrep -f "codeworm run" > /dev/null 2>&1; then
        log_info "CodeWorm is already running"
        return 0
    fi

    log_info "Starting CodeWorm daemon..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    if [[ -f "$PROJECT_DIR/.venv/bin/codeworm" ]]; then
        nohup "$PROJECT_DIR/.venv/bin/codeworm" run > /tmp/codeworm.log 2>&1 &
    elif command -v codeworm &> /dev/null; then
        nohup codeworm run > /tmp/codeworm.log 2>&1 &
    else
        log_error "CodeWorm not found. Run: uv sync && uv pip install -e ."
        return 1
    fi

    sleep 2

    if pgrep -f "codeworm run" > /dev/null 2>&1; then
        log_info "CodeWorm daemon started (PID: $(pgrep -f 'codeworm run'))"
        log_info "Logs: tail -f /tmp/codeworm.log"
    else
        log_error "Failed to start CodeWorm"
        log_error "Check logs: cat /tmp/codeworm.log"
        return 1
    fi
}

stop_daemon() {
    if pgrep -f "codeworm run" > /dev/null 2>&1; then
        log_info "Stopping CodeWorm..."
        pkill -f "codeworm run" || true
        sleep 2
        log_info "CodeWorm stopped"
    else
        log_warn "CodeWorm is not running"
    fi
}

case "${1:-start}" in
    start)
        echo ""
        echo "═══════════════════════════════════════════"
        echo "  Starting CodeWorm"
        echo "═══════════════════════════════════════════"
        echo ""
        ensure_ollama
        start_daemon
        show_status
        ;;
    stop)
        stop_daemon
        ;;
    restart)
        stop_daemon
        sleep 1
        ensure_ollama
        start_daemon
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        tail -f /tmp/codeworm.log
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
