# Скрипт проверки Icecast потока

Этот скрипт предназначен для мониторинга состояния Icecast потока и отправки уведомлений в Telegram при его недоступности.

## Возможности

- ✅ **Мониторинг множественных потоков** - проверка нескольких mount point'ов одновременно
- ✅ **Работа с удаленными серверами** - внешний мониторинг Icecast серверов
- ✅ **HTTP Basic Authentication** - поддержка авторизации на защищенных серверах
- ✅ **Гибкие endpoints** - автоматическое определение доступных API endpoints (`/admin/stats`, `/status-json.xsl`, `/admin/listmounts.xsl`, `/status.xsl`)
- ✅ **JSON статус файл** - автоматическое создание `status-online.json` с детальной информацией о всех потоках
- ✅ **Умные уведомления в Telegram**:
  - 🚨 Уведомления о проблемах с cooldown периодом (избежание спама)
  - ✅ Уведомления о восстановлении (без cooldown, отправляются сразу)
  - 📊 Детальная информация о потоке (слушатели, битрейт, трек и т.д.)
- ✅ **Логирование с датой** - файлы логов создаются с датой в имени (`2024-09-14-icecast_check.log`)
- ✅ **Systemd сервис** - автозапуск и управление через systemctl
- ✅ **Виртуальное окружение** - изолированная установка зависимостей
- ✅ **Настраиваемые параметры** - интервалы проверки, cooldown периоды, размеры логов
- ✅ **Обработка ошибок** - повторные попытки и детальное логирование
- ✅ **Поддержка HTTP/HTTPS** - автоматическое определение стандартных портов

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации

Отредактируйте файл `config.json`:

```json
{
    "icecast": {
        "host": "your-icecast-server.com", // IP адрес или домен Icecast сервера
        "port": 8000,                      // Порт Icecast сервера (443 для HTTPS, 80 для HTTP)
        "timeout": 15,                     // Таймаут подключения (сек)
        "check_interval": 60,              // Интервал проверки (сек)
        "use_https": false,                // Использовать HTTPS (true/false)
        "user_agent": "IcecastChecker/1.0", // User-Agent для запросов
        "endpoint": "/admin/stats",         // Предпочтительный endpoint (опционально)
        "endpoint_only": false,            // Использовать только указанный endpoint (true/false)
        "auth": {                          // Настройки авторизации
            "username": "",                // Имя пользователя для HTTP Basic Auth
            "password": "",                // Пароль для HTTP Basic Auth
            "enabled": false               // Включить авторизацию (true/false)
        },
        "streams": [                       // Массив потоков для проверки
            {
                "mount_point": "/stream",  // Mount point потока
                "name": "Основной поток",  // Человекочитаемое имя
                "enabled": true            // Включить/выключить проверку
            },
            {
                "mount_point": "/backup",
                "name": "Резервный поток",
                "enabled": true
            },
            {
                "mount_point": "/test",
                "name": "Тестовый поток",
                "enabled": false
            }
        ]
    },
    "telegram": {
        "bot_token": "YOUR_BOT_TOKEN", // Токен Telegram бота
        "chat_id": "YOUR_CHAT_ID",     // ID чата для уведомлений
        "enabled": true                // Включить/выключить уведомления
    },
    "logging": {
        "log_file": "/var/log/scripts/check_streaming/{YYYY}-{MM}-{DD}-icecast_check.log",
        "log_level": "INFO",           // DEBUG, INFO, WARNING, ERROR
        "max_file_size": 10485760,     // Максимальный размер лога (байт)
        "backup_count": 5              // Количество архивных файлов логов
    },
    "status_json": {
        "enabled": true,               // Включить создание JSON статус файла
        "file_path": "status-online.json", // Путь к JSON файлу
        "update_interval": 30          // Интервал обновления (сек)
    },
    "notifications": {
        "retry_attempts": 3,           // Количество попыток отправки
        "retry_delay": 30,             // Задержка между попытками (сек)
        "cooldown_period": 300         // Период между уведомлениями (сек)
    }
}
```

### 3. Настройка Icecast сервера

Для работы с удаленным мониторингом убедитесь, что:

1. **Icecast сервер доступен извне** - проверьте настройки файрвола
2. **Порт открыт** - обычно это порт 8000 (или другой настроенный)
3. **Статистика включена** - в конфигурации Icecast должен быть включен вывод статистики
4. **Доступ к `/status-json.xsl`** - этот endpoint должен быть доступен

Пример настройки в `icecast.xml`:
```xml
<location>/status-json.xsl</location>
<admin>admin@yourdomain.com</admin>
```

### 4. Настройка endpoints

Скрипт поддерживает различные Icecast API endpoints и автоматически определяет доступный:

**Доступные endpoints:**
- `/admin/stats` - XML статистика (рекомендуется)
- `/status-json.xsl` - JSON статистика
- `/admin/listmounts.xsl` - HTML список mount points
- `/status.xsl` - альтернативный JSON endpoint

**Параметры конфигурации:**
- `endpoint` - предпочтительный endpoint (например, `/admin/stats`)
- `endpoint_only` - использовать только указанный endpoint (`true`/`false`)

**Примеры использования:**

```json
// Использовать только XML endpoint
{
    "icecast": {
        "endpoint": "/admin/stats",
        "endpoint_only": true
    }
}

// Предпочитать XML endpoint, но пробовать другие при недоступности
{
    "icecast": {
        "endpoint": "/admin/stats",
        "endpoint_only": false
    }
}

// Автоматическое определение (по умолчанию)
{
    "icecast": {
        "endpoint_only": false
    }
}
```

### 5. Особенности работы с портами

Скрипт автоматически обрабатывает стандартные порты:

- **Порт 443 (HTTPS)**: URL формируется как `https://hostname/endpoint` (без указания порта)
- **Порт 80 (HTTP)**: URL формируется как `http://hostname/endpoint` (без указания порта)  
- **Другие порты**: URL формируется как `protocol://hostname:port/endpoint`

**Примеры конфигурации:**

```json
// HTTPS на стандартном порту 443
{
    "icecast": {
        "host": "live1.zharafm.ru",
        "port": 443,
        "use_https": true
    }
}
// Результат: https://live1.zharafm.ru/status-json.xsl

// HTTP на стандартном порту 80  
{
    "icecast": {
        "host": "radio.example.com",
        "port": 80,
        "use_https": false
    }
}
// Результат: http://radio.example.com/status-json.xsl

// Кастомный порт
{
    "icecast": {
        "host": "icecast.example.com", 
        "port": 8080,
        "use_https": false
    }
}
// Результат: http://icecast.example.com:8080/status-json.xsl
```

### 5. Настройка авторизации

Если ваш Icecast сервер защищен паролем:

1. **Включите авторизацию** в конфигурации: `"enabled": true`
2. **Укажите учетные данные**:
   - `username` - имя пользователя для HTTP Basic Auth
   - `password` - пароль для HTTP Basic Auth
3. **Проверьте права доступа** - пользователь должен иметь доступ к статистике

**Пример конфигурации с авторизацией:**
```json
{
    "icecast": {
        "host": "secure-icecast.example.com",
        "port": 8000,
        "auth": {
            "username": "monitor_user",
            "password": "secure_password",
            "enabled": true
        }
    }
}
```

### 6. Настройка множественных потоков

Скрипт поддерживает проверку нескольких потоков одновременно:

- **`mount_point`** - путь к потоку на сервере (например `/stream`, `/backup`)
- **`name`** - человекочитаемое имя для логов и уведомлений
- **`enabled`** - включить/выключить проверку конкретного потока

**Примеры использования:**
- Основной и резервный потоки
- Разные качества одного потока (`/stream128`, `/stream320`)
- Тестовые и продакшн потоки
- Потоки разных радиостанций

### 6. Настройка Telegram бота

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота
3. Узнайте ID чата (можно использовать [@userinfobot](https://t.me/userinfobot))
4. Добавьте токен и ID в конфигурацию

### 7. Настройка JSON статус файла

Скрипт автоматически создает JSON файл со статусом всех потоков:

- **`enabled`** - включить/выключить создание JSON файла
- **`file_path`** - путь к JSON файлу (по умолчанию `status-online.json`)
- **`update_interval`** - интервал обновления файла (сек)

**Пример содержимого `status-online.json`:**
```json
{
  "last_update": "2024-01-15 14:30:25",
  "server": {
    "host": "radio.example.com",
    "port": 8000,
    "protocol": "http"
  },
  "streams": [
    {
      "mount_point": "/COMEDY-1065FM",
      "name": "Comedy Radio",
      "status": "online",
      "listeners": 10,
      "stream_started": "Sat, 13 Sep 2025 00:46:41 +0300",
      "currently_playing": "Comedy Radio",
      "bitrate": "128",
      "server_description": "Comedy Radio Server",
      "genre": "Comedy",
      "last_check": "2024-01-15 14:30:25"
    }
  ]
}
```

## Использование

### Рекомендуемый способ: Docker

1. Скопируйте пример конфига в `config.json` и заполните реальные значения: для Icecast — `config_icecast_example.json`, для кастомных проверок — `config_custom_example.json`.
2. Соберите и запустите контейнер:

```bash
docker compose up -d
```

При этом:
- `config.json` монтируется в контейнер только для чтения;
- `status-online.json` и логи пишутся в локальные файлы/директории.

Контейнер автоматически перезапускается при сбоях (`restart: always` в `docker-compose.yml`).

### Легаси-скрипты (без Docker)

Если Docker недоступен, в директории `legacy/` сохранены:
- shell-скрипты для Linux/macOS (`run_icecast_checker.sh`, `run_icecast_checker_background.sh`, `stop_icecast_checker.sh`);
- batch-скрипты для Windows (`run_icecast_checker.bat`, `run_icecast_checker_background.bat`);
- скрипты установки/удаления systemd-сервиса и Windows-службы.

Эти варианты запуска поддерживаются как «legacy» и не используются в Docker-сценарии.

## Логирование с датой

Все события записываются в лог файлы с датой в имени и ротацией. По умолчанию логи сохраняются в `/var/log/scripts/check_streaming/YYYY-MM-DD-icecast_check.log`.

**Примеры файлов логов:**
- `2024-09-14-icecast_check.log` - лог за 14 сентября 2024
- `2024-09-15-icecast_check.log` - лог за 15 сентября 2024

**Уровни логирования:**
- `DEBUG` - подробная отладочная информация (endpoints, конфигурация, парсинг)
- `INFO` - общая информация о работе (статус потоков, уведомления)
- `WARNING` - предупреждения (потоки недоступны)
- `ERROR` - ошибки (проблемы подключения, парсинга)

**Просмотр логов:**
```bash
# Текущий лог
tail -f /var/log/scripts/check_streaming/$(date +%Y-%m-%d)-icecast_check.log

# Все логи
ls -la /var/log/scripts/check_streaming/
```

## Принцип работы

1. Скрипт подключается к Icecast серверу через API статистики (`/status-json.xsl`)
2. **Проверяет все активные потоки** из массива `streams` в конфигурации
3. Для каждого потока проверяет наличие указанного mount point в списке активных потоков
4. При недоступности потока отправляет **индивидуальное уведомление** в Telegram
5. Использует **отдельные cooldown периоды** для каждого потока
6. Ведет **отдельные счетчики** последовательных неудач для каждого потока
7. **Умное логирование** - избегает спама в логах при длительных проблемах
8. **Периодические уведомления** о длительных проблемах (каждые 30 попыток)
9. **Автоматическое создание JSON файла** со статусом всех потоков для веб-интерфейса
10. Логирует статус каждого потока с человекочитаемыми именами

## Умные уведомления в Telegram

Скрипт отправляет два типа уведомлений:

### 🚨 Уведомления о проблемах
Отправляются при обнаружении недоступности потока с cooldown периодом (избежание спама):

```
🚨 ВНИМАНИЕ!

Поток 'Основной поток' недоступен!
Сервер: radio.example.com
Протокол: HTTP
Mount point: /stream

**ПЕРЕЗАПУСТИТЕ СТРИМИНГ**
```

### ✅ Уведомления о восстановлении
Отправляются сразу при восстановлении потока (без cooldown):

```
✅ ВОССТАНОВЛЕНИЕ!

Поток 'Основной поток' снова доступен!
Сервер: radio.example.com
Mount point: /stream
Слушателей: 5
```

### ⚠️ Периодические напоминания
При длительных проблемах (каждые 30 попыток):

```
⚠️ ПРОДОЛЖАЮЩАЯСЯ ПРОБЛЕМА

Поток 'Основной поток' все еще недоступен!
Попытка: 30
Сервер: radio.example.com:8000
Протокол: HTTP
Mount point: /stream
Проверка с внешней площадки
```

**Пример периодического уведомления:**
```
⚠️ ПРОДОЛЖАЮЩАЯСЯ ПРОБЛЕМА

Поток 'Основной поток' все еще недоступен!
Время: 2024-01-15 15:00:25
Попытка: 30
Сервер: radio.example.com:8000
Протокол: HTTP
Mount point: /stream
Проверка с внешней площадки
```

## Остановка скрипта

- **Windows**: Найдите процесс `python.exe` в диспетчере задач и завершите его
- **Linux/macOS**: 
  - Для обычного запуска: используйте `Ctrl+C`
  - Для фонового режима: используйте `./stop_icecast_checker.sh`
  - Или найдите процесс: `ps aux | grep icecast_checker` и завершите его: `kill <PID>`

## Диагностика проблем

### Проверка доступности сервера

1. **Тест подключения к порту**:
   ```bash
   telnet your-icecast-server.com 8000
   ```

2. **Проверка HTTP ответа**:
   ```bash
   curl http://your-icecast-server.com:8000/status-json.xsl
   ```

3. **Проверка с HTTPS** (если используется):
   ```bash
   curl -k https://your-icecast-server.com:8000/status-json.xsl
   ```

4. **Проверка с авторизацией**:
   ```bash
   curl -u username:password http://your-icecast-server.com:8000/status-json.xsl
   ```

5. **Проверка с авторизацией и HTTPS**:
   ```bash
   curl -k -u username:password https://your-icecast-server.com:8000/status-json.xsl
   ```

### Частые проблемы

- **Connection refused** - сервер недоступен или порт закрыт
- **Timeout** - медленное соединение, увеличьте timeout в конфигурации
- **HTTP 401** - ошибка авторизации, проверьте username и password
- **HTTP 403** - доступ запрещен, недостаточно прав пользователя
- **HTTP 404** - endpoint `/status-json.xsl` не настроен на сервере
- **JSON parse error** - сервер возвращает не JSON данные

### Логи

Все события записываются в лог файл. Для отладки установите `log_level: "DEBUG"` в конфигурации.

**Умное логирование:**
- Первые 3 неудачи логируются всегда
- После 3 неудач логируется только каждые 10 попыток
- Дополнительно логируется каждые 5 минут для длительных проблем
- При восстановлении потока счетчики сбрасываются

## Примеры конфигураций

### Радиостанция с основным и резервным потоком
```json
{
    "icecast": {
        "host": "radio.example.com",
        "port": 8000,
        "streams": [
            {
                "mount_point": "/main",
                "name": "Основной поток 128k",
                "enabled": true
            },
            {
                "mount_point": "/backup",
                "name": "Резервный поток 64k",
                "enabled": true
            }
        ]
    }
}
```

### Множественные качества одного потока
```json
{
    "icecast": {
        "host": "stream.example.com",
        "port": 8000,
        "streams": [
            {
                "mount_point": "/stream320",
                "name": "Высокое качество 320k",
                "enabled": true
            },
            {
                "mount_point": "/stream128",
                "name": "Стандартное качество 128k",
                "enabled": true
            },
            {
                "mount_point": "/stream64",
                "name": "Низкое качество 64k",
                "enabled": true
            }
        ]
    }
}
```

### Тестовые и продакшн потоки
```json
{
    "icecast": {
        "host": "icecast.example.com",
        "port": 8000,
        "streams": [
            {
                "mount_point": "/live",
                "name": "Продакшн поток",
                "enabled": true
            },
            {
                "mount_point": "/test",
                "name": "Тестовый поток",
                "enabled": false
            }
        ]
    }
}
```

### Защищенный сервер с авторизацией
```json
{
    "icecast": {
        "host": "secure-radio.example.com",
        "port": 8000,
        "use_https": true,
        "auth": {
            "username": "monitor_user",
            "password": "secure_password_123",
            "enabled": true
        },
        "streams": [
            {
                "mount_point": "/main",
                "name": "Основной поток",
                "enabled": true
            },
            {
                "mount_point": "/backup",
                "name": "Резервный поток",
                "enabled": true
            }
        ]
    }
}
```

## Docker-конфигурация

В репозитории есть:
- `Dockerfile` — образ на базе `python:3.14.3-slim`;
- `docker-compose.yml` — готовый сервис `icecast-checker` с томами для `config.json`, `status-online.json` и логов.

Запуск:

```bash
docker compose up -d
```


## Требования

- Python 3.6+
- Библиотека `requests`
- Доступ к интернету для отправки уведомлений в Telegram
- Доступ к Icecast серверу для проверки статистики
- Icecast сервер должен быть доступен извне (для удаленного мониторинга)
