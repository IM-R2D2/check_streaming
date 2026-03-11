#!/bin/bash
# Скрипт запуска проверки Icecast потока
# Автор: AI Assistant
# Дата: $(date)

echo "Запуск проверки Icecast потока..."

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python3 не найден в системе"
    echo "Установите Python3: sudo apt install python3 python3-pip"
    exit 1
fi

# Проверяем наличие файла конфигурации
if [ ! -f "config.json" ]; then
    echo "Ошибка: Файл config.json не найден"
    echo "Создайте файл конфигурации перед запуском"
    exit 1
fi

# Создаем виртуальное окружение если его нет
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "Активация виртуального окружения..."
source venv/bin/activate

# Устанавливаем зависимости
echo "Установка зависимостей..."
pip install -r requirements.txt

# Запуск скрипта
echo "Запуск проверки Icecast..."
python3 icecast_checker.py

# Деактивируем виртуальное окружение
deactivate

echo "Скрипт завершен"

