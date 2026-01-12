#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/codeworm}"
CONFIG_DIR="${CONFIG_DIR:-$INSTALL_DIR/config}"
DATA_DIR="${DATA_DIR:-$INSTALL_DIR/data}"
LOG_DIR="${LOG_DIR:-/var/log/codeworm}"
CODEWORM_USER="${CODEWORM_USER:-codeworm}"
CODEWORM_GROUP="${CODEWORM_GROUP:-codeworm}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_dependencies() {
    log_info "Checking dependencies..."

    local deps=("git" "python3")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "$dep is not installed"
            exit 1
        fi
    done

    python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ $(echo "$python_version < 3.11" | bc -l) -eq 1 ]]; then
        log_error "Python 3.11+ required, found $python_version"
        exit 1
    fi

    log_info "Dependencies OK (Python $python_version)"
}

create_user() {
    if id "$CODEWORM_USER" &>/dev/null; then
        log_info "User $CODEWORM_USER already exists"
    else
        log_info "Creating user $CODEWORM_USER..."
        useradd --system --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin "$CODEWORM_USER"
    fi
}

setup_directories() {
    log_info "Setting up directories..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$LOG_DIR"

    chown -R "$CODEWORM_USER:$CODEWORM_GROUP" "$INSTALL_DIR"
    chown -R "$CODEWORM_USER:$CODEWORM_GROUP" "$LOG_DIR"

    chmod 750 "$INSTALL_DIR"
    chmod 750 "$CONFIG_DIR"
    chmod 750 "$DATA_DIR"
    chmod 750 "$LOG_DIR"
}

install_codeworm() {
    log_info "Installing CodeWorm..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    cp -r "$PROJECT_DIR/codeworm" "$INSTALL_DIR/"
    cp "$PROJECT_DIR/pyproject.toml" "$INSTALL_DIR/"

    if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
        cp "$PROJECT_DIR/config/"*.yaml "$CONFIG_DIR/"
        log_info "Config files copied to $CONFIG_DIR"
    else
        log_warn "Config files already exist, skipping copy"
    fi

    log_info "Creating virtual environment..."
    python3 -m venv "$INSTALL_DIR/.venv"

    log_info "Installing Python dependencies..."
    "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR"

    chown -R "$CODEWORM_USER:$CODEWORM_GROUP" "$INSTALL_DIR"
}

install_systemd_service() {
    log_info "Installing systemd service..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    cp "$PROJECT_DIR/systemd/codeworm.service" /etc/systemd/system/

    sed -i "s|/opt/codeworm|$INSTALL_DIR|g" /etc/systemd/system/codeworm.service
    sed -i "s|User=codeworm|User=$CODEWORM_USER|g" /etc/systemd/system/codeworm.service
    sed -i "s|Group=codeworm|Group=$CODEWORM_GROUP|g" /etc/systemd/system/codeworm.service

    systemctl daemon-reload
    log_info "Systemd service installed"
}

print_next_steps() {
    echo ""
    echo "=============================================="
    echo -e "${GREEN}CodeWorm installed successfully${NC}"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Configure your repositories:"
    echo "   sudo -u $CODEWORM_USER nano $CONFIG_DIR/repos.yaml"
    echo ""
    echo "2. Configure main settings:"
    echo "   sudo -u $CODEWORM_USER nano $CONFIG_DIR/config.yaml"
    echo ""
    echo "3. Set up DevLog repository:"
    echo "   The devlog.repo_path in config.yaml needs to be accessible"
    echo "   by the $CODEWORM_USER user"
    echo ""
    echo "4. Ensure Ollama is running:"
    echo "   ollama serve"
    echo "   ollama pull qwen2.5:7b"
    echo ""
    echo "5. Test the installation:"
    echo "   sudo -u $CODEWORM_USER $INSTALL_DIR/.venv/bin/codeworm --help"
    echo ""
    echo "6. Start the service:"
    echo "   sudo systemctl enable codeworm"
    echo "   sudo systemctl start codeworm"
    echo ""
    echo "7. Check status:"
    echo "   sudo systemctl status codeworm"
    echo "   sudo journalctl -u codeworm -f"
    echo ""
}

main() {
    echo "=============================================="
    echo "  CodeWorm Installation Script"
    echo "=============================================="
    echo ""

    check_root
    check_dependencies
    create_user
    setup_directories
    install_codeworm
    install_systemd_service
    print_next_steps
}

main "$@"
