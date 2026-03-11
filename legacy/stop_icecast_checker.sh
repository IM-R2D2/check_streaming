#!/bin/bash
# Скрипт остановки проверки Icecast потока
# Автор: AI Assistant
# Дата: $(date)

echo "Остановка проверки Icecast потока..."

PID_FILE="icecast_checker.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "PID файл не найден. Скрипт может быть не запущен."
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! ps -p $PID > /dev/null 2>&1; then
    echo "Процесс с PID $PID не найден. Возможно, скрипт уже остановлен."
    rm -f "$PID_FILE"
    exit 1
fi

echo "Остановка процесса с PID: $PID"
kill $PID

# Ждем завершения процесса
sleep 2

# Проверяем, завершился ли процесс
if ps -p $PID > /dev/null 2>&1; then
    echo "Процесс не завершился. Принудительная остановка..."
    kill -9 $PID
    sleep 1
fi

# Проверяем финальный статус
if ps -p $PID > /dev/null 2>&1; then
    echo "Ошибка: Не удалось остановить процесс"
    exit 1
else
    echo "Процесс успешно остановлен"
    rm -f "$PID_FILE"
fi

