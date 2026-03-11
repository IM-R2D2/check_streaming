@echo off
REM Скрипт запуска проверки Icecast потока
REM Автор: AI Assistant
REM Дата: %date%

echo Запуск проверки Icecast потока...

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Ошибка: Python не найден в системе
    echo Установите Python с https://python.org
    pause
    exit /b 1
)

REM Проверяем наличие файла конфигурации
if not exist "config.json" (
    echo Ошибка: Файл config.json не найден
    echo Создайте файл конфигурации перед запуском
    pause
    exit /b 1
)

REM Устанавливаем зависимости если нужно
if not exist "venv" (
    echo Создание виртуального окружения...
    python -m venv venv
)

echo Активация виртуального окружения...
call venv\Scripts\activate.bat

echo Установка зависимостей...
pip install -r requirements.txt

REM Запуск скрипта
echo Запуск проверки Icecast...
python icecast_checker.py

REM Пауза для просмотра результатов
pause

