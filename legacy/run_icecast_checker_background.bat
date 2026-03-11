@echo off
REM Скрипт запуска проверки Icecast потока в фоновом режиме
REM Автор: AI Assistant
REM Дата: %date%

echo Запуск проверки Icecast потока в фоновом режиме...

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

REM Запуск скрипта в фоновом режиме
echo Запуск проверки Icecast в фоновом режиме...
start /B python icecast_checker.py

echo Скрипт запущен в фоновом режиме
echo Для остановки найдите процесс python.exe в диспетчере задач
pause

