#!/bin/bash

set -e

INSTALL_DIR="/opt/relaysms/relaysms-gateway-server"
SERVICE_NAME="relaysms-gateway-server"
REPO_URL="https://github.com/smswithoutborders/RelaySMS-Gateway-Server.git"
BRANCH="${BRANCH:-main}"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"; }
error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
  exit 1
}
check_root() { [ "$EUID" -eq 0 ] || error "This script must be run with sudo"; }

install_dependencies() {
  log "Installing dependencies"
  apt update || error "Failed to update package list"
  apt install -y python3 python3-pip python3-venv python3-dev \
    libmariadb-dev git curl make || error "Failed to install dependencies"
}

clone_repository() {
  log "Cloning repository"
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Repository exists, updating"
    cd "$INSTALL_DIR"
    git fetch origin && git checkout "$BRANCH" && git pull origin "$BRANCH" || error "Failed to update"
  else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR" || error "Failed to clone"
  fi
}

setup_virtualenv() {
  log "Setting up virtual environment"
  cd "$INSTALL_DIR"
  [ -d "venv" ] || python3 -m venv venv || error "Failed to create venv"
  venv/bin/pip install --upgrade pip || error "Failed to upgrade pip"
  venv/bin/pip install -r requirements.txt || error "Failed to install dependencies"
}

compile_grpc() {
  log "Compiling gRPC protos"
  make grpc-compile || error "Failed to compile gRPC"
}

setup_env() {
  log "Setting up configuration"
  [ -f ".env" ] && log ".env already exists" && return
  [ -f "template.env" ] || error "template.env not found"
  cp template.env .env
}

setup_runtime() {
  log "Setting up runtime"
  mkdir -p data/ftp_file_store
  set -a && source .env && set +a
}

install_systemd_service() {
  log "Installing systemd services"
  for service in relaysms-gateway-server.target relaysms-gateway-server-rest.service relaysms-gateway-server-imap.service relaysms-gateway-server-ftp.service; do
    [ -f "$service" ] || error "Service file $service not found"
    cp "$service" /etc/systemd/system/$service || error "Failed to install $service"
  done
  systemctl daemon-reload || error "Failed to reload systemd"
  systemctl enable "$SERVICE_NAME.target" || error "Failed to enable services"
  systemctl start "$SERVICE_NAME.target" || error "Failed to start services"
}

set_permissions() {
  log "Setting permissions"
  chmod 600 .env 2>/dev/null || true
}

main() {
  log "Starting installation"

  check_root
  install_dependencies
  clone_repository
  setup_virtualenv

  cd "$INSTALL_DIR"
  source venv/bin/activate

  compile_grpc
  setup_env
  setup_runtime
  set_permissions
  install_systemd_service

  log "Installation complete"
  log ""
  log "Services started and enabled"
  log "Manage: $INSTALL_DIR/manage.sh {start|stop|restart|status|logs}"
  log "Config: $INSTALL_DIR/.env"
}

main "$@"
