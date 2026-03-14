#!/bin/bash

# Deploy icecast-checker in Docker.
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh

set -e

echo "=== Deploying icecast-checker in Docker ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker &>/dev/null; then
  echo "Error: Docker is not installed or not available in PATH."
  exit 1
fi

if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
else
  echo "Error: neither 'docker compose' nor 'docker-compose' found."
  exit 1
fi

LOGS_DIR="$SCRIPT_DIR/logs"
STATUS_FILE="$SCRIPT_DIR/status-online.json"
CONFIG_FILE="$SCRIPT_DIR/config.json"
CONFIG_EXAMPLE="$SCRIPT_DIR/config_icecast_example.json"

echo "Creating logs directory: $LOGS_DIR"
mkdir -p "$LOGS_DIR"

if [ ! -f "$STATUS_FILE" ]; then
  echo "Creating empty status file: $STATUS_FILE"
  echo '{}' > "$STATUS_FILE"
fi

if [ ! -f "$CONFIG_FILE" ]; then
  if [ -f "$CONFIG_EXAMPLE" ]; then
    echo "config.json not found. Copying template config_icecast_example.json."
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    echo "WARNING: edit $CONFIG_FILE before running in production."
    echo "For custom format, use config_custom_example.json as a base."
  else
    echo "Error: neither config.json nor config_icecast_example.json found."
    exit 1
  fi
fi

echo '{}' > "$STATUS_FILE"
echo "Status file reset: $STATUS_FILE"

echo "Building image without cache..."
$COMPOSE_CMD build --no-cache

echo "Starting container..."
$COMPOSE_CMD up -d --force-recreate

echo "=== Deployment complete ==="
echo "Check service logs in directory: $LOGS_DIR"

