#!/bin/bash

# Скрипт удаления systemd service для icecast-checker
# Использование: sudo ./uninstall_service.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Удаление systemd service для icecast-checker ===${NC}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Ошибка: Запустите скрипт с правами root (sudo)${NC}"
    exit 1
fi

# Определяем пути
SERVICE_NAME="icecast-checker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_DIR="/opt/icecast-checker"
LOG_DIR="/var/log/scripts/check_streaming"

echo -e "${YELLOW}1. Остановка и отключение сервиса...${NC}"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl stop "$SERVICE_NAME"
    echo -e "${GREEN}Сервис остановлен${NC}"
else
    echo -e "${GREEN}Сервис не запущен${NC}"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    systemctl disable "$SERVICE_NAME"
    echo -e "${GREEN}Автозапуск отключен${NC}"
else
    echo -e "${GREEN}Автозапуск не был включен${NC}"
fi

echo -e "${YELLOW}2. Удаление systemd service файла...${NC}"
if [ -f "$SERVICE_FILE" ]; then
    rm "$SERVICE_FILE"
    echo -e "${GREEN}Service файл удален${NC}"
else
    echo -e "${GREEN}Service файл не найден${NC}"
fi

echo -e "${YELLOW}3. Перезагрузка systemd...${NC}"
systemctl daemon-reload

echo -e "${YELLOW}4. Удаление файлов приложения...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}Директория приложения удалена: $INSTALL_DIR${NC}"
else
    echo -e "${GREEN}Директория приложения не найдена${NC}"
fi

echo -e "${YELLOW}5. Удаление пользователя icecast...${NC}"
if id "icecast" &>/dev/null; then
    userdel icecast
    echo -e "${GREEN}Пользователь icecast удален${NC}"
else
    echo -e "${GREEN}Пользователь icecast не найден${NC}"
fi

echo -e "${YELLOW}6. Удаление логов (опционально)...${NC}"
read -p "Удалить логи? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$LOG_DIR" ]; then
        rm -rf "$LOG_DIR"
        echo -e "${GREEN}Логи удалены: $LOG_DIR${NC}"
    else
        echo -e "${GREEN}Директория логов не найдена${NC}"
    fi
else
    echo -e "${GREEN}Логи сохранены: $LOG_DIR${NC}"
fi

echo -e "${GREEN}=== Удаление завершено! ===${NC}"
echo ""
echo -e "${YELLOW}Примечание:${NC}"
echo -e "  Если вы хотите полностью очистить систему, также удалите:"
echo -e "  - Python пакеты: ${GREEN}pip3 uninstall requests beautifulsoup4${NC}"
echo -e "  - Остальные логи: ${GREEN}sudo journalctl --vacuum-time=1d${NC}"

