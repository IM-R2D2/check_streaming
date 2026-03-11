#!/bin/bash

# Простое развертывание icecast-checker в Docker
# Использование:
#   chmod +x deploy.sh
#   ./deploy.sh

set -e

echo "=== Развертывание icecast-checker в Docker ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Проверка наличия Docker
if ! command -v docker &>/dev/null; then
  echo "Ошибка: Docker не установлен или не доступен в PATH."
  exit 1
fi

# 2. Проверка наличия docker compose (новый синтаксис)
if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
  # На случай старых установок
  COMPOSE_CMD="docker-compose"
else
  echo "Ошибка: ни 'docker compose', ни 'docker-compose' не найдены."
  exit 1
fi

# 3. Создание необходимых директорий и файлов
LOGS_DIR="$SCRIPT_DIR/logs"
STATUS_FILE="$SCRIPT_DIR/status-online.json"
CONFIG_FILE="$SCRIPT_DIR/config.json"
CONFIG_EXAMPLE="$SCRIPT_DIR/config_icecast_example.json"

echo "Создаем директорию для логов: $LOGS_DIR"
mkdir -p "$LOGS_DIR"

if [ ! -f "$STATUS_FILE" ]; then
  echo "Создаем пустой файл статуса: $STATUS_FILE"
  echo '{}' > "$STATUS_FILE"
fi

if [ ! -f "$CONFIG_FILE" ]; then
  if [ -f "$CONFIG_EXAMPLE" ]; then
    echo "config.json не найден. Копируем шаблон config_icecast_example.json."
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    echo "ВНИМАНИЕ: отредактируйте $CONFIG_FILE перед запуском в продакшене."
    echo "Если нужен custom-формат, возьмите за основу config_custom_example.json."
  else
    echo "Ошибка: ни config.json, ни config_icecast_example.json не найдены."
    exit 1
  fi
fi

# 4. Сборка и запуск контейнера
# Образ тегируется как icecast-checker:latest. Без --build будет использован уже собранный образ.
echo "Собираем и запускаем контейнер через $COMPOSE_CMD..."
$COMPOSE_CMD up -d --build

echo "=== Развертывание завершено ==="
echo "Проверьте логи сервиса в директории: $LOGS_DIR"

