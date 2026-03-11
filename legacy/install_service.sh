#!/bin/bash

# Скрипт установки systemd service для icecast-checker
# Использование: sudo ./install_service.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Установка systemd service для icecast-checker ===${NC}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Ошибка: Запустите скрипт с правами root (sudo)${NC}"
    exit 1
fi

# Определяем пути
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="icecast-checker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_DIR="/opt/icecast-checker"
LOG_DIR="/var/log/scripts/check_streaming"

echo -e "${YELLOW}1. Создание пользователя icecast...${NC}"
if ! id "icecast" &>/dev/null; then
    useradd -r -s /bin/false -d /opt/icecast-checker icecast
    echo -e "${GREEN}Пользователь icecast создан${NC}"
else
    echo -e "${GREEN}Пользователь icecast уже существует${NC}"
fi

echo -e "${YELLOW}2. Создание директорий...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$LOG_DIR"

echo -e "${YELLOW}3. Копирование файлов...${NC}"
cp "$SCRIPT_DIR/icecast_checker.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/config.json" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

# Установка зависимостей Python в виртуальном окружении
echo -e "${YELLOW}4. Создание виртуального окружения Python...${NC}"
if command -v python3 &> /dev/null; then
    # Создаем виртуальное окружение
    python3 -m venv "$INSTALL_DIR/venv"
    
    # Активируем виртуальное окружение и устанавливаем зависимости
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    
    echo -e "${GREEN}Виртуальное окружение создано и зависимости установлены${NC}"
else
    echo -e "${RED}Ошибка: python3 не найден. Установите Python3${NC}"
    exit 1
fi

echo -e "${YELLOW}5. Установка прав доступа...${NC}"
chown -R icecast:icecast "$INSTALL_DIR"
chown -R icecast:icecast "$LOG_DIR"

echo -е "${YELLOW}6. Установка systemd service...${NC}"
cp "$SCRIPT_DIR/icecast-checker.service" "$SERVICE_FILE"

# Обновление путей в service файле
sed -i "s|/opt/icecast-checker|$INSTALL_DIR|g" "$SERVICE_FILE"

echo -e "${YELLOW}7. Перезагрузка systemd...${NC}"
systemctl daemon-reload

echo -e "${YELLOW}8. Включение автозапуска...${NC}"
systemctl enable "$SERVICE_NAME"

echo -e "${GREEN}=== Установка завершена! ===${NC}"
echo ""
echo -e "${YELLOW}Команды управления:${NC}"
echo -e "  Запуск:     ${GREEN}sudo systemctl start $SERVICE_NAME${NC}"
echo -е "  Остановка:  ${GREEN}sudo systemctl stop $SERVICE_NAME${NC}"
echo -е "  Перезапуск: ${GREEN}sudo systemctl restart $SERVICE_NAME${NC}"
echo -е "  Статус:     ${GREEN}sudo systemctl status $SERVICE_NAME${NC}"
echo ""
echo -е "${YELLOW}Конфигурация:${NC}"
echo -е "  Файл конфигурации: ${GREEN}$INSTALL_DIR/config.json${NC}"
echo -е "  Логи:              ${GREEN}$LOG_DIR/icecast_check.log${NC}"
echo -е "  JSON статус:       ${GREEN}$INSTALL_DIR/status-online.json${NC}"
echo ""
echo -е "${YELLOW}Следующие шаги:${NC}"
echo -е "  1. Отредактируйте конфигурацию: ${GREEN}nano $INSTALL_DIR/config.json${NC}"
echo -е "  2. Запустите сервис: ${GREEN}sudo systemctl start $SERVICE_NAME${NC}"
echo -е "  3. Проверьте статус: ${GREEN}sudo systemctl status $SERVICE_NAME${NC}"

