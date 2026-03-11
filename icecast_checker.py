#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт проверки наличия потока Icecast
Отправляет уведомления в Telegram при отсутствии потока
"""

import json
import logging
import os
import sys
import time
import smtplib
import requests
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from email.mime.text import MIMEText


class IcecastChecker:
    """Класс для проверки состояния Icecast потока"""
    
    def __init__(self, config_path="config.json"):
        """Инициализация с загрузкой конфигурации"""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.last_notification_time = {}
        self.consecutive_failures = {}
        self.stream_status = {}
        self.last_log_time = {}  # Время последнего логирования для каждого потока
        self.last_success_time = None  # Время последнего успешного прохода проверки
        self.last_error_time = None    # Время последнего прохода с ошибками (offline потоки)
        
    def _load_config(self, config_path):
        """Загрузка конфигурации из JSON файла"""
        try:
            # Получаем абсолютный путь к файлу
            abs_config_path = os.path.abspath(config_path)
            print(f"DEBUG: Абсолютный путь к конфигурации: {abs_config_path}")
            print(f"DEBUG: Файл существует: {os.path.exists(abs_config_path)}")
            
            with open(abs_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            print(f"DEBUG: Загружена конфигурация из {abs_config_path}")
            print(f"DEBUG: Конфигурация icecast: {config.get('icecast', {})}")
            return config
        except FileNotFoundError:
            print(f"Ошибка: Файл конфигурации {config_path} не найден")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Ошибка в файле конфигурации: {e}")
            sys.exit(1)

    
    def _setup_logging(self):
        """Настройка системы логирования"""
        log_config = self.config.get('logging', {})
        log_file_template = log_config.get('log_file', 'icecast_check.log')
        log_level = log_config.get('log_level', 'INFO')
        max_size = log_config.get('max_file_size', 10485760)  # 10MB
        backup_count = log_config.get('backup_count', 5)
        
        # Обрабатываем шаблон с датой
        now = datetime.now()
        log_file = log_file_template.format(
            YYYY=now.strftime('%Y'),
            MM=now.strftime('%m'),
            DD=now.strftime('%d')
        )
        
        # Создаем директорию для логов если её нет
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Настройка логгера
        self.logger = logging.getLogger('icecast_checker')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Обработчик для файла с ротацией
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_size, 
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Форматтер
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
        # Также выводим в консоль для отладки
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def test_endpoint_availability(self, url, headers, auth_enabled, auth_username, auth_password, timeout):
        """Проверка доступности endpoint"""
        try:
            import requests
            
            # Настройка авторизации
            auth = None
            if auth_enabled and auth_username and auth_password:
                auth = (auth_username, auth_password)
            
            # Быстрая проверка доступности endpoint
            self.logger.debug(f"Тестируем endpoint: {url}")
            response = requests.get(url, headers=headers, auth=auth, timeout=5, verify=False)
            self.logger.debug(f"Endpoint {url} ответил с кодом: {response.status_code}")
            return response.status_code == 200
            
        except Exception as e:
            self.logger.debug(f"Endpoint {url} недоступен: {e}")
            return False
    
    def check_server_connectivity(self, host, port, timeout):
        """Проверка базовой доступности сервера"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            self.logger.debug(f"Ошибка проверки подключения к {host}:{port}: {e}")
            return False
    
    def get_enabled_streams(self):
        """Получение списка активных потоков для проверки"""
        icecast_config = self.config.get('icecast', {})
        streams = icecast_config.get('streams', [])
        
        enabled_streams = []
        for stream in streams:
            if stream.get('enabled', True):
                enabled_streams.append(stream)
        
        return enabled_streams
    
    def should_log_failure(self, stream_key, consecutive_failures):
        """Определяет, нужно ли логировать неудачу для избежания спама"""
        current_time = time.time()
        
        # Логируем первые 3 неудачи всегда
        if consecutive_failures <= 3:
            return True
        
        # После 3 неудач логируем только каждые 10 попыток
        if consecutive_failures % 10 == 0:
            return True
        
        # Логируем каждые 5 минут для длительных проблем
        if stream_key in self.last_log_time:
            if current_time - self.last_log_time[stream_key] >= 300:  # 5 минут
                return True
        
        return False
    
    def check_icecast_stream(self, stream_config):
        """Проверка доступности конкретного Icecast потока"""
        icecast_config = self.config.get('icecast', {})
        
        # Отладочная информация о конфигурации
        self.logger.debug(f"Полная конфигурация icecast: {icecast_config}")
        
        host = icecast_config.get('host', 'localhost')
        port = icecast_config.get('port', 8000)
        mount_point = stream_config.get('mount_point', '/stream')
        stream_name = stream_config.get('name', mount_point)
        timeout = icecast_config.get('timeout', 15)
        use_https = icecast_config.get('use_https', False)
        user_agent = icecast_config.get('user_agent', 'IcecastChecker/1.0')
        preferred_endpoint = icecast_config.get('endpoint', None)
        endpoint_only = icecast_config.get('endpoint_only', False)
        
        # Настройка авторизации
        auth_config = icecast_config.get('auth', {})
        auth_enabled = auth_config.get('enabled', False)
        auth_username = auth_config.get('username', '')
        auth_password = auth_config.get('password', '')
        
        # Пропускаем базовую проверку для HTTPS соединений
        self.logger.debug(f"Конфигурация: host={host}, port={port}, use_https={use_https}")
        if not use_https:
            # Сначала проверяем базовую доступность сервера только для HTTP
            self.logger.debug(f"Выполняем базовую проверку подключения для HTTP: {host}:{port}")
            if not self.check_server_connectivity(host, port, timeout):
                display_host = f"{host}:{port}" if port != 80 else host
                self.logger.error(f"Сервер {display_host} недоступен")
                return self.create_offline_stream_info(mount_point, stream_name, "Server unavailable")
        else:
            # Для HTTPS пропускаем базовую проверку подключения
            self.logger.debug(f"Пропускаем базовую проверку подключения для HTTPS: {host}:{port}")
            self.logger.debug(f"Переходим к проверке endpoints для HTTPS")
        
        # Формируем URL для проверки статистики Icecast
        protocol = 'https' if use_https else 'http'
        
        # Если порт 443 для HTTPS или 80 для HTTP, не указываем порт в URL
        if (use_https and port == 443) or (not use_https and port == 80):
            base_url = f"{protocol}://{host}"
        else:
            base_url = f"{protocol}://{host}:{port}"
        
        # Список возможных endpoints для получения статистики
        possible_endpoints = [
            "/status-json.xsl",      # Стандартный JSON endpoint
            "/admin/listmounts.xsl", # HTML список mount points
            "/admin/stats",          # XML статистика
            "/status.xsl"            # Альтернативный JSON endpoint
        ]
        
        # Если указан предпочтительный endpoint, ставим его первым
        if preferred_endpoint:
            if endpoint_only:
                # Используем только указанный endpoint
                possible_endpoints = [preferred_endpoint]
                self.logger.debug(f"Используем только указанный endpoint: {preferred_endpoint}")
            else:
                # Перемещаем предпочтительный endpoint в начало списка
                if preferred_endpoint not in possible_endpoints:
                    possible_endpoints.insert(0, preferred_endpoint)
                else:
                    possible_endpoints.remove(preferred_endpoint)
                    possible_endpoints.insert(0, preferred_endpoint)
                self.logger.debug(f"Используем предпочтительный endpoint: {preferred_endpoint}")
        
        # Пробуем каждый endpoint
        stats_url = None
        self.logger.debug(f"Пробуем найти доступный endpoint на сервере {base_url}")
        
        # Настройка заголовков для запроса
        headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Connection': 'close'
        }
        
        for endpoint in possible_endpoints:
            test_url = f"{base_url}{endpoint}"
            self.logger.debug(f"Проверяем endpoint: {endpoint}")
            if self.test_endpoint_availability(test_url, headers, auth_enabled, auth_username, auth_password, timeout):
                stats_url = test_url
                self.logger.debug(f"Найден доступный endpoint: {endpoint}")
                break
        
        if not stats_url:
            self.logger.error(f"Ни один из endpoints недоступен на сервере {base_url}")
            return self.create_offline_stream_info(mount_point, stream_name, "No available endpoints")
        
        try:
            auth_info = f" с авторизацией ({auth_username})" if auth_enabled else ""
            display_url = f"{protocol}://{host}" if ((use_https and port == 443) or (not use_https and port == 80)) else f"{protocol}://{host}:{port}"
            self.logger.debug(f"Проверяем поток '{stream_name}' ({mount_point}) на {display_url}{auth_info}")
            
            # Настройка авторизации
            auth = None
            if auth_enabled and auth_username and auth_password:
                auth = (auth_username, auth_password)
            elif auth_enabled:
                self.logger.warning("Авторизация включена, но не указаны username или password")
            
            response = requests.get(stats_url, timeout=timeout, headers=headers, auth=auth)
            response.raise_for_status()
            
            # Определяем тип endpoint и парсим соответственно
            if '/status-json.xsl' in stats_url or '/status.xsl' in stats_url:
                # JSON endpoints
                stats = response.json()
                return self.parse_json_response(stats, mount_point, stream_name)
            elif '/admin/listmounts.xsl' in stats_url:
                # HTML endpoint
                html_content = response.text
                return self.parse_html_response(html_content, mount_point, stream_name)
            elif '/admin/stats' in stats_url:
                # XML endpoint
                xml_content = response.text
                # Временный патч - добавляем метод прямо здесь
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(xml_content)
                    
                    # Ищем наш mount point в XML
                    for source in root.findall('.//source'):
                        mount_attr = source.get('mount')
                        if mount_attr == mount_point:
                            listeners = 0
                            try:
                                listeners_text = source.find('listeners')
                                if listeners_text is not None:
                                    listeners = int(listeners_text.text)
                            except:
                                pass
                            
                            # Получаем дополнительную информацию
                            title = "Unknown"
                            title_elem = source.find('title')
                            if title_elem is not None and title_elem.text:
                                title = title_elem.text
                            
                            bitrate = "Unknown"
                            bitrate_elem = source.find('bitrate')
                            if bitrate_elem is not None and bitrate_elem.text:
                                bitrate = bitrate_elem.text
                            
                            server_description = "Unknown"
                            desc_elem = source.find('server_description')
                            if desc_elem is not None and desc_elem.text:
                                server_description = desc_elem.text
                            
                            genre = "Unknown"
                            genre_elem = source.find('genre')
                            if genre_elem is not None and genre_elem.text:
                                genre = genre_elem.text
                            
                            stream_started = "Unknown"
                            start_elem = source.find('stream_start')
                            if start_elem is not None and start_elem.text:
                                stream_started = start_elem.text
                            
                            self.logger.info(f"Поток '{stream_name}' ({mount_point}) активен, слушателей: {listeners}")
                            return {
                                "mount_point": mount_point,
                                "name": stream_name,
                                "status": "online",
                                "listeners": listeners,
                                "stream_started": stream_started,
                                "currently_playing": title,
                                "bitrate": bitrate,
                                "server_description": server_description,
                                "genre": genre,
                                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                    
                    self.logger.warning(f"Поток '{stream_name}' ({mount_point}) не найден в XML статистике")
                    return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in XML statistics")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка парсинга XML: {e}")
                    return self.create_offline_stream_info(mount_point, stream_name, f"XML parsing error: {e}")
            else:
                # Пробуем как JSON по умолчанию
                try:
                    stats = response.json()
                    return self.parse_json_response(stats, mount_point, stream_name)
                except:
                    # Если не JSON, пробуем как HTML
                    html_content = response.text
                    return self.parse_html_response(html_content, mount_point, stream_name)
                
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Ошибка подключения к Icecast серверу {host}:{port}: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Connection error: {e}")
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Таймаут подключения к Icecast серверу {host}:{port}: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Timeout: {e}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.logger.error(f"Ошибка авторизации на Icecast сервере {host}:{port} - неверные учетные данные")
                return self.create_offline_stream_info(mount_point, stream_name, "Authentication failed")
            elif e.response.status_code == 403:
                self.logger.error(f"Доступ запрещен на Icecast сервере {host}:{port} - недостаточно прав")
                return self.create_offline_stream_info(mount_point, stream_name, "Access forbidden")
            else:
                self.logger.error(f"HTTP ошибка при подключении к Icecast: {e}")
                return self.create_offline_stream_info(mount_point, stream_name, f"HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка запроса к Icecast: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Request error: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Ошибка парсинга JSON ответа: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"JSON parse error: {e}")
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при проверке потока: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Unexpected error: {e}")
    
    def send_telegram_notification(self, message, stream_key, skip_cooldown=False):
        """Отправка уведомления в Telegram для конкретного потока.
        
        Используется один Telegram-бот на весь конфиг (на один id сервера).
        """
        telegram_config = self.config.get('telegram', {})
        
        if not telegram_config.get('enabled', False):
            self.logger.debug("Уведомления в Telegram отключены")
            return False
        
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('chat_id')
        
        if not bot_token or not chat_id:
            self.logger.error("Не настроены bot_token или chat_id для Telegram")
            return False
        
        current_time = time.time()
        notifications_config = self.config.get('notifications', {})
        
        # Проверяем период cooldown для конкретного потока (если не пропускаем)
        if not skip_cooldown:
            cooldown_period = notifications_config.get('cooldown_period', 300)
            if stream_key in self.last_notification_time:
                if current_time - self.last_notification_time[stream_key] < cooldown_period:
                    self.logger.debug(f"Пропускаем уведомление для потока {stream_key} из-за cooldown периода ({cooldown_period} сек)")
                    return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        retry_attempts = notifications_config.get('retry_attempts', 3)
        retry_delay = notifications_config.get('retry_delay', 30)
        
        for attempt in range(retry_attempts):
            try:
                response = requests.post(url, data=data, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                if result.get('ok'):
                    self.logger.info(f"Уведомление в Telegram для потока {stream_key} отправлено успешно")
                    self.last_notification_time[stream_key] = current_time
                    return True
                else:
                    self.logger.error(f"Ошибка Telegram API: {result.get('description')}")
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Ошибка отправки в Telegram для потока {stream_key} (попытка {attempt + 1}): {e}")
                if attempt < retry_attempts - 1:
                    time.sleep(retry_delay)
        
        return False

    def send_email_notification(self, subject, message, stream_key, skip_cooldown=False):
        """Отправка уведомления на email для конкретного потока"""
        email_config = self.config.get('email', {})

        if not email_config.get('enabled', False):
            self.logger.debug("Email-уведомления отключены")
            return False

        smtp_host = email_config.get('smtp_host')
        smtp_port = email_config.get('smtp_port', 587)
        use_tls = email_config.get('use_tls', True)
        username = email_config.get('username')
        password = email_config.get('password')
        from_addr = email_config.get('from_addr')
        to_addr = email_config.get('to_addr')
        subject_prefix = email_config.get('subject_prefix', '[IcecastChecker]')

        if not (smtp_host and from_addr and to_addr):
            self.logger.error("Не настроены параметры SMTP или адреса email")
            return False

        # Получаем конфигурацию уведомлений (для общего cooldown)
        notifications_config = self.config.get('notifications', {})

        # Проверяем период cooldown для конкретного потока (если не пропускаем)
        if not skip_cooldown:
            cooldown_period = notifications_config.get('cooldown_period', 300)

            current_time = time.time()
            if stream_key in self.last_notification_time:
                if current_time - self.last_notification_time[stream_key] < cooldown_period:
                    self.logger.debug(f"Пропускаем email-уведомление для потока {stream_key} из-за cooldown периода ({cooldown_period} сек)")
                    return False
        else:
            current_time = time.time()

        full_subject = f"{subject_prefix} {subject}" if subject_prefix else subject

        msg = MIMEText(message)
        msg['Subject'] = full_subject
        msg['From'] = from_addr
        msg['To'] = to_addr

        try:
            if use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)

            if username and password:
                server.login(username, password)

            server.sendmail(from_addr, [to_addr], msg.as_string())
            server.quit()

            self.logger.info(f"Email-уведомление для потока {stream_key} отправлено успешно")
            self.last_notification_time[stream_key] = current_time
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отправки email для потока {stream_key}: {e}")
            return False
    
    def create_offline_stream_info(self, mount_point, stream_name, error_msg="Server unavailable"):
        """Создает информацию о недоступном потоке"""
        return {
            "mount_point": mount_point,
            "name": stream_name,
            "status": "offline",
            "listeners": 0,
            "stream_started": "Unknown",
            "currently_playing": "Unknown",
            "bitrate": "Unknown",
            "server_description": "Unknown",
            "genre": "Unknown",
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": error_msg
        }
    
    def write_status_json(self, streams_data):
        """Запись статуса потоков в JSON файл"""
        status_config = self.config.get('status_json', {})
        
        if not status_config.get('enabled', False):
            return
        
        file_path = status_config.get('file_path', 'status-online.json')
        
        try:
            # Получаем конфигурацию сервера
            icecast_config = self.config['icecast']
            host = icecast_config['host']
            port = icecast_config['port']
            use_https = icecast_config.get('use_https', False)
            protocol = "https" if use_https else "http"
            
            # Формируем URL для отображения (без стандартных портов)
            if (use_https and port == 443) or (not use_https and port == 80):
                server_url = f"{protocol}://{host}"
            else:
                server_url = f"{protocol}://{host}:{port}"

            # Подсчитываем простые метрики по потокам
            total_streams = len(streams_data)
            online_streams = sum(1 for s in streams_data if s.get("status") == "online")
            offline_streams = total_streams - online_streams

            total_listeners = 0
            for s in streams_data:
                try:
                    total_listeners += int(s.get("listeners", 0) or 0)
                except (TypeError, ValueError):
                    continue

            # Формируем структуру данных
            status_data = {
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "server": {
                    "host": host,
                    "port": port,
                    "protocol": protocol,
                    "url": server_url
                },
                "metrics": {
                    "total_streams": total_streams,
                    "online_streams": online_streams,
                    "offline_streams": offline_streams,
                    "total_listeners": total_listeners,
                    "last_success": self.last_success_time,
                    "last_error": self.last_error_time
                },
                "streams": streams_data
            }
            
            # Записываем в файл
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Статус записан в {file_path}")
            
        except Exception as e:
            self.logger.error(f"Ошибка записи статуса в JSON: {e}")
    
    def _load_previous_status(self):
        """Загружает последний сохранённый статус потоков из JSON.
        Возвращает dict: stream_key -> 'online'|'offline'.
        Используется для отправки уведомления только при переходе в offline (смена статуса).
        Для работы нужна запись статуса: в конфиге должен быть включён status_json.enabled.
        """
        status_config = self.config.get('status_json', {})
        file_path = status_config.get('file_path', 'status-online.json')
        result = {}
        try:
            if not os.path.exists(file_path):
                return result
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            streams = data.get('streams', [])
            for s in streams:
                mp = s.get('mount_point', '')
                name = s.get('name', mp)
                key = f"{mp}_{name}"
                st = s.get('status')
                if st in ('online', 'offline'):
                    result[key] = st
            return result
        except Exception as e:
            self.logger.debug(f"Не удалось загрузить предыдущий статус из {file_path}: {e}")
            return result
    
    def run_check(self):
        """Выполнение проверки всех потоков"""
        self.logger.info("Запуск проверки Icecast потоков")
        
        enabled_streams = self.get_enabled_streams()
        if not enabled_streams:
            self.logger.warning("Нет активных потоков для проверки")
            return True
        
        # Статус с прошлого прохода: уведомление только при переходе в offline
        previous_run_status = self._load_previous_status()
        
        all_streams_ok = True
        streams_data = []  # Собираем данные о всех потоках для JSON
        icecast_config = self.config['icecast']
        protocol = 'https' if icecast_config.get('use_https', False) else 'http'
        
        for stream_config in enabled_streams:
            mount_point = stream_config.get('mount_point')
            stream_name = stream_config.get('name', mount_point)
            stream_key = f"{mount_point}_{stream_name}"
            
            # Инициализируем счетчики для нового потока
            if stream_key not in self.consecutive_failures:
                self.consecutive_failures[stream_key] = 0
            if stream_key not in self.stream_status:
                self.stream_status[stream_key] = True
            
            stream_info = self.check_icecast_stream(stream_config)
            
            # Добавляем информацию о потоке в общий список
            streams_data.append(stream_info)
            
            if stream_info.get('status') == 'online':
                # Проверяем, был ли поток ранее недоступен (для уведомления о восстановлении)
                was_offline = self.consecutive_failures[stream_key] > 0
                
                # Отладочная информация
                self.logger.debug(f"Поток '{stream_name}' онлайн. Было ошибок: {self.consecutive_failures[stream_key]}, was_offline: {was_offline}")
                
                self.consecutive_failures[stream_key] = 0
                self.stream_status[stream_key] = True
                
                # Сбрасываем время последнего логирования при восстановлении
                if stream_key in self.last_log_time:
                    del self.last_log_time[stream_key]
                
                # Отправляем уведомление о восстановлении, если поток был недоступен
                if was_offline:
                    self.logger.info(f"Отправляем уведомление о восстановлении для потока '{stream_name}'")
                    #timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message = f"✅ <b>ВОССТАНОВЛЕНИЕ!</b>\n\n"
                    message += f"Поток '{stream_name}' снова доступен!\n"
                    #message += f"Время восстановления: {timestamp}\n"
                    message += f"Сервер: {icecast_config['host']}\n"
                    message += f"Mount point: {mount_point}\n"
                    message += f"Слушателей: {stream_info.get('listeners', 0)}"
                    
                    self.send_telegram_notification(message, stream_key, skip_cooldown=True)
                    self.send_email_notification(
                        subject=f"Восстановление потока '{stream_name}'",
                        message=message,
                        stream_key=stream_key,
                        skip_cooldown=True
                    )
            else:
                self.consecutive_failures[stream_key] += 1
                self.stream_status[stream_key] = False
                all_streams_ok = False
                
                # Отладочная информация
                self.logger.debug(f"Поток '{stream_name}' офлайн. Ошибок подряд: {self.consecutive_failures[stream_key]}")
                
                # Умное логирование: не заваливаем лог, логируем только при смене на offline или редко
                if self.should_log_failure(stream_key, self.consecutive_failures[stream_key]):
                    self.logger.warning(f"Поток '{stream_name}' недоступен (попытка {self.consecutive_failures[stream_key]})")
                    self.last_log_time[stream_key] = time.time()
                
                # Уведомление только при переходе в offline (смена статуса с прошлого прохода).
                # Пока статус остаётся "offline" — только проверяем, не шлём в Telegram и не спамим в лог.
                was_online_or_new = previous_run_status.get(stream_key) != "offline"
                if was_online_or_new:
                    auth_config = icecast_config.get('auth', {})
                    auth_enabled = auth_config.get('enabled', False)
                    
                    message = f"🚨 <b>ВНИМАНИЕ!</b>\n\n"
                    message += f"Поток '{stream_name}' недоступен!\n"
                    message += f"Сервер: {icecast_config['host']}\n"
                    message += f"Протокол: {protocol.upper()}\n"
                    message += f"Mount point: {mount_point}\n \n"
                    message += f"**ПЕРЕЗАПУСТИТЕ СТРИМИНГ**"
                    
                    self.send_telegram_notification(message, stream_key)
                    self.send_email_notification(
                        subject=f"Поток '{stream_name}' недоступен",
                        message=message,
                        stream_key=stream_key
                    )
        
        # Обновляем метрики успешного/проблемного прохода
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if all_streams_ok:
            self.last_success_time = now_str
        else:
            self.last_error_time = now_str

        # Записываем статус всех потоков в JSON файл
        self.write_status_json(streams_data)
        
        return all_streams_ok
    
    def run_continuous(self):
        """Непрерывная проверка с интервалами"""
        check_interval = self.config.get('icecast', {}).get('check_interval', 60)
        
        self.logger.info(f"Запуск непрерывной проверки с интервалом {check_interval} секунд")
        
        try:
            while True:
                self.run_check()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            self.logger.info("Получен сигнал прерывания, завершение работы")
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
            sys.exit(1)


def main():
    """Основная функция"""
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Однократная проверка
        checker = IcecastChecker()
        success = checker.run_check()
        sys.exit(0 if success else 1)
    else:
        # Непрерывная проверка
        checker = IcecastChecker()
        checker.run_continuous()


    def parse_json_response(self, stats, mount_point, stream_name):
        """Парсинг JSON ответа от Icecast"""
        # Проверяем наличие нашего mount point
        if 'icestats' in stats and 'source' in stats['icestats']:
            sources = stats['icestats']['source']
            if not isinstance(sources, list):
                sources = [sources]
            
            for source in sources:
                if source.get('mount') == mount_point:
                    listeners = source.get('listeners', 0)
                    self.logger.info(f"Поток '{stream_name}' ({mount_point}) активен, слушателей: {listeners}")
                    
                    # Возвращаем подробную информацию о потоке
                    stream_info = {
                        "mount_point": mount_point,
                        "name": stream_name,
                        "status": "online",
                        "listeners": listeners,
                        "stream_started": source.get('stream_started', 'Unknown'),
                        "currently_playing": source.get('title', 'Unknown'),
                        "bitrate": source.get('bitrate', 'Unknown'),
                        "server_description": source.get('server_description', 'Unknown'),
                        "genre": source.get('genre', 'Unknown'),
                        "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    return stream_info
            
            self.logger.warning(f"Поток '{stream_name}' ({mount_point}) не найден в статистике")
            return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in statistics")
        else:
            self.logger.error("Неверный формат JSON ответа от Icecast")
            return self.create_offline_stream_info(mount_point, stream_name, "Invalid JSON response format")
    
    def parse_html_response(self, html_content, mount_point, stream_name):
        """Парсинг HTML ответа от /admin/listmounts.xsl"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Ищем таблицу с mount points
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        mount_cell = cells[0].get_text().strip()
                        if mount_cell == mount_point:
                            # Найден наш mount point
                            listeners = 0
                            if len(cells) >= 3:
                                try:
                                    listeners = int(cells[2].get_text().strip())
                                except:
                                    pass
                            
                            self.logger.info(f"Поток '{stream_name}' ({mount_point}) активен, слушателей: {listeners}")
                            return {
                                "mount_point": mount_point,
                                "name": stream_name,
                                "status": "online",
                                "listeners": listeners,
                                "stream_started": "Unknown",
                                "currently_playing": "Unknown",
                                "bitrate": "Unknown",
                                "server_description": "Unknown",
                                "genre": "Unknown",
                                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
            
            self.logger.warning(f"Поток '{stream_name}' ({mount_point}) не найден в HTML статистике")
            return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in HTML statistics")
            
        except ImportError:
            self.logger.error("BeautifulSoup не установлен. Установите: pip install beautifulsoup4")
            return self.create_offline_stream_info(mount_point, stream_name, "HTML parsing requires beautifulsoup4")
        except Exception as e:
            self.logger.error(f"Ошибка парсинга HTML: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"HTML parsing error: {e}")
    
    def parse_xml_response(self, xml_content, mount_point, stream_name):
        """Парсинг XML ответа от /admin/stats"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_content)
            
            # Ищем наш mount point в XML
            for source in root.findall('.//source'):
                mount_attr = source.get('mount')
                if mount_attr == mount_point:
                    listeners = 0
                    try:
                        listeners_text = source.find('listeners')
                        if listeners_text is not None:
                            listeners = int(listeners_text.text)
                    except:
                        pass
                    
                    # Получаем дополнительную информацию
                    title = "Unknown"
                    title_elem = source.find('title')
                    if title_elem is not None and title_elem.text:
                        title = title_elem.text
                    
                    bitrate = "Unknown"
                    bitrate_elem = source.find('bitrate')
                    if bitrate_elem is not None and bitrate_elem.text:
                        bitrate = bitrate_elem.text
                    
                    server_description = "Unknown"
                    desc_elem = source.find('server_description')
                    if desc_elem is not None and desc_elem.text:
                        server_description = desc_elem.text
                    
                    genre = "Unknown"
                    genre_elem = source.find('genre')
                    if genre_elem is not None and genre_elem.text:
                        genre = genre_elem.text
                    
                    stream_started = "Unknown"
                    start_elem = source.find('stream_start')
                    if start_elem is not None and start_elem.text:
                        stream_started = start_elem.text
                    
                    self.logger.info(f"Поток '{stream_name}' ({mount_point}) активен, слушателей: {listeners}")
                    return {
                        "mount_point": mount_point,
                        "name": stream_name,
                        "status": "online",
                        "listeners": listeners,
                        "stream_started": stream_started,
                        "currently_playing": title,
                        "bitrate": bitrate,
                        "server_description": server_description,
                        "genre": genre,
                        "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
            
            self.logger.warning(f"Поток '{stream_name}' ({mount_point}) не найден в XML статистике")
            return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in XML statistics")
            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга XML: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"XML parsing error: {e}")


if __name__ == "__main__":
    main()
