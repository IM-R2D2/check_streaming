#!/bin/bash
# Скрипт запуска проверки Icecast потока в фоновом режиме
# Автор: AI Assistant
# Дата: $(date)

echo "Запуск проверки Icecast потока в фоновом режиме..."

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

# Проверяем, не запущен ли уже скрипт
PID_FILE="icecast_checker.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "Скрипт уже запущен (PID: $PID)"
        echo "Для остановки выполните: kill $PID"
        exit 1
    else
        echo "Удаляем устаревший PID файл..."
        rm -f "$PID_FILE"
    fi
fi

# Запуск скрипта в фоновом режиме
echo "Запуск проверки Icecast в фоновом режиме..."
nohup python3 icecast_checker.py > icecast_checker.log 2>&1 &
PID=$!

# Сохраняем PID процесса
echo $PID > "$PID_FILE"

echo "Скрипт запущен в фоновом режиме (PID: $PID)"
echo "Логи сохраняются в файл: icecast_checker.log"
echo "Для остановки выполните: kill $PID"
echo "Или используйте: ./stop_icecast_checker.sh"

# Деактивируем виртуальное окружение
deactivate

