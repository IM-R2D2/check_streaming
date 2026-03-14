#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Icecast stream availability checker. Sends Telegram notifications when a stream is down.
"""

import json
import logging
import os
import sys
import time
import smtplib
import requests
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText

from logging_utils import setup_logging_from_config


class IcecastChecker:
    """Icecast stream status checker."""

    def __init__(self, config_path="config.json"):
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.last_notification_time = {}
        self.consecutive_failures = {}
        self.stream_status = {}
        self.last_log_time = {}
        self.last_success_time = None
        self.last_error_time = None
        
    def _load_config(self, config_path):
        try:
            abs_config_path = os.path.abspath(config_path)
            with open(abs_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            sys.stderr.write(f"Error: Config file not found: {config_path}\n")
            sys.exit(1)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Error in config file: {e}\n")
            sys.exit(1)

    
    def _setup_logging(self):
        self.logger = setup_logging_from_config(self.config, logger_name="icecast_checker")
    
    def test_endpoint_availability(self, url, headers, auth_enabled, auth_username, auth_password, timeout):
        try:
            import requests

            auth = None
            if auth_enabled and auth_username and auth_password:
                auth = (auth_username, auth_password)

            self.logger.debug(f"Testing endpoint: {url}")
            response = requests.get(url, headers=headers, auth=auth, timeout=5, verify=False)
            self.logger.debug(f"Endpoint {url} responded with code: {response.status_code}")
            return response.status_code == 200

        except Exception as e:
            self.logger.debug(f"Endpoint {url} unavailable: {e}")
            return False

    def check_server_connectivity(self, host, port, timeout):
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            self.logger.debug(f"Connectivity check failed for {host}:{port}: {e}")
            return False

    def get_enabled_streams(self):
        icecast_config = self.config.get('icecast', {})
        streams = icecast_config.get('streams', [])
        
        enabled_streams = []
        for stream in streams:
            if stream.get('enabled', True):
                enabled_streams.append(stream)
        
        return enabled_streams
    
    def should_log_failure(self, stream_key, consecutive_failures):
        current_time = time.time()

        if consecutive_failures <= 3:
            return True

        if consecutive_failures % 10 == 0:
            return True

        if stream_key in self.last_log_time:
            if current_time - self.last_log_time[stream_key] >= 300:
                return True
        
        return False
    
    def check_icecast_stream(self, stream_config):
        icecast_config = self.config.get('icecast', {})

        self.logger.debug(f"Icecast config: {icecast_config}")

        host = icecast_config.get('host', 'localhost')
        port = icecast_config.get('port', 8000)
        mount_point = stream_config.get('mount_point', '/stream')
        stream_name = stream_config.get('name', mount_point)
        timeout = icecast_config.get('timeout', 15)
        use_https = icecast_config.get('use_https', False)
        user_agent = icecast_config.get('user_agent', 'IcecastChecker/1.0')
        preferred_endpoint = icecast_config.get('endpoint', None)
        endpoint_only = icecast_config.get('endpoint_only', False)

        auth_config = icecast_config.get('auth', {})
        auth_enabled = auth_config.get('enabled', False)
        auth_username = auth_config.get('username', '')
        auth_password = auth_config.get('password', '')

        self.logger.debug(f"Config: host={host}, port={port}, use_https={use_https}")
        if not use_https:
            self.logger.debug(f"Checking HTTP connectivity: {host}:{port}")
            if not self.check_server_connectivity(host, port, timeout):
                display_host = f"{host}:{port}" if port != 80 else host
                self.logger.error(f"Server {display_host} unavailable")
                return self.create_offline_stream_info(mount_point, stream_name, "Server unavailable")
        else:
            self.logger.debug(f"Skipping connectivity check for HTTPS: {host}:{port}")
            self.logger.debug("Checking HTTPS endpoints")

        protocol = 'https' if use_https else 'http'

        if (use_https and port == 443) or (not use_https and port == 80):
            base_url = f"{protocol}://{host}"
        else:
            base_url = f"{protocol}://{host}:{port}"

        possible_endpoints = [
            "/status-json.xsl",
            "/admin/listmounts.xsl",
            "/admin/stats",
            "/status.xsl"
        ]

        if preferred_endpoint:
            if endpoint_only:
                possible_endpoints = [preferred_endpoint]
                self.logger.debug(f"Using only specified endpoint: {preferred_endpoint}")
            else:
                if preferred_endpoint not in possible_endpoints:
                    possible_endpoints.insert(0, preferred_endpoint)
                else:
                    possible_endpoints.remove(preferred_endpoint)
                    possible_endpoints.insert(0, preferred_endpoint)
                self.logger.debug(f"Using preferred endpoint: {preferred_endpoint}")

        stats_url = None
        self.logger.debug(f"Finding available endpoint on {base_url}")

        headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Connection': 'close'
        }
        
        for endpoint in possible_endpoints:
            test_url = f"{base_url}{endpoint}"
            self.logger.debug(f"Checking endpoint: {endpoint}")
            if self.test_endpoint_availability(test_url, headers, auth_enabled, auth_username, auth_password, timeout):
                stats_url = test_url
                self.logger.debug(f"Available endpoint found: {endpoint}")
                break

        if not stats_url:
            self.logger.error(f"No endpoints available on server {base_url}")
            return self.create_offline_stream_info(mount_point, stream_name, "No available endpoints")
        
        try:
            auth_info = f" with auth ({auth_username})" if auth_enabled else ""
            display_url = f"{protocol}://{host}" if ((use_https and port == 443) or (not use_https and port == 80)) else f"{protocol}://{host}:{port}"
            self.logger.debug(f"Checking stream '{stream_name}' ({mount_point}) at {display_url}{auth_info}")

            auth = None
            if auth_enabled and auth_username and auth_password:
                auth = (auth_username, auth_password)
            elif auth_enabled:
                self.logger.warning("Auth enabled but username or password not set")
            
            response = requests.get(stats_url, timeout=timeout, headers=headers, auth=auth)
            response.raise_for_status()

            if '/status-json.xsl' in stats_url or '/status.xsl' in stats_url:
                stats = response.json()
                return self.parse_json_response(stats, mount_point, stream_name)
            elif '/admin/listmounts.xsl' in stats_url:
                html_content = response.text
                return self.parse_html_response(html_content, mount_point, stream_name)
            elif '/admin/stats' in stats_url:
                xml_content = response.text
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(xml_content)

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
                            
                            self.logger.info(f"Stream '{stream_name}' ({mount_point}) online, listeners: {listeners}")
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
                    
                    self.logger.warning(f"Stream '{stream_name}' ({mount_point}) not found in XML stats")
                    return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in XML statistics")
                    
                except Exception as e:
                    self.logger.error(f"XML parsing error: {e}")
                    return self.create_offline_stream_info(mount_point, stream_name, f"XML parsing error: {e}")
            else:
                try:
                    stats = response.json()
                    return self.parse_json_response(stats, mount_point, stream_name)
                except:
                    html_content = response.text
                    return self.parse_html_response(html_content, mount_point, stream_name)
                
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error to Icecast {host}:{port}: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Connection error: {e}")
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout connecting to Icecast {host}:{port}: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Timeout: {e}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.logger.error(f"Auth failed on Icecast {host}:{port}")
                return self.create_offline_stream_info(mount_point, stream_name, "Authentication failed")
            elif e.response.status_code == 403:
                self.logger.error(f"Access denied on Icecast {host}:{port}")
                return self.create_offline_stream_info(mount_point, stream_name, "Access forbidden")
            else:
                self.logger.error(f"HTTP error connecting to Icecast: {e}")
                return self.create_offline_stream_info(mount_point, stream_name, f"HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error to Icecast: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Request error: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"JSON parse error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error checking stream: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"Unexpected error: {e}")
    
    def send_telegram_notification(self, message, stream_key, skip_cooldown=False):
        telegram_config = self.config.get('telegram', {})

        if not telegram_config.get('enabled', False):
            self.logger.debug("Telegram notifications disabled")
            return False

        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('chat_id')

        if not bot_token or not chat_id:
            self.logger.error("Telegram bot_token or chat_id not set")
            return False

        current_time = time.time()
        notifications_config = self.config.get('notifications', {})

        if not skip_cooldown:
            cooldown_period = notifications_config.get('cooldown_period', 300)
            if stream_key in self.last_notification_time:
                if current_time - self.last_notification_time[stream_key] < cooldown_period:
                    self.logger.debug(f"Skipping Telegram notification for {stream_key} (cooldown {cooldown_period}s)")
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
                    self.logger.info(f"Telegram notification sent for {stream_key}")
                    self.last_notification_time[stream_key] = current_time
                    return True
                else:
                    self.logger.error(f"Telegram API error: {result.get('description')}")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Telegram send failed for {stream_key} (attempt {attempt + 1}): {e}")
                if attempt < retry_attempts - 1:
                    time.sleep(retry_delay)
        
        return False

    def send_email_notification(self, subject, message, stream_key, skip_cooldown=False):
        email_config = self.config.get('email', {})

        if not email_config.get('enabled', False):
            self.logger.debug("Email notifications disabled")
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
            self.logger.error("SMTP or email addresses not configured")
            return False

        notifications_config = self.config.get('notifications', {})

        if not skip_cooldown:
            cooldown_period = notifications_config.get('cooldown_period', 300)

            current_time = time.time()
            if stream_key in self.last_notification_time:
                if current_time - self.last_notification_time[stream_key] < cooldown_period:
                    self.logger.debug(f"Skipping email notification for {stream_key} (cooldown {cooldown_period}s)")
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

            self.logger.info(f"Email notification sent for {stream_key}")
            self.last_notification_time[stream_key] = current_time
            return True
        except Exception as e:
            self.logger.error(f"Email send failed for {stream_key}: {e}")
            return False
    
    def create_offline_stream_info(self, mount_point, stream_name, error_msg="Server unavailable"):
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
        status_config = self.config.get('status_json', {})
        
        if not status_config.get('enabled', False):
            return
        
        file_path = status_config.get('file_path', 'status-online.json')
        
        try:
            icecast_config = self.config['icecast']
            host = icecast_config['host']
            port = icecast_config['port']
            use_https = icecast_config.get('use_https', False)
            protocol = "https" if use_https else "http"

            if (use_https and port == 443) or (not use_https and port == 80):
                server_url = f"{protocol}://{host}"
            else:
                server_url = f"{protocol}://{host}:{port}"

            total_streams = len(streams_data)
            online_streams = sum(1 for s in streams_data if s.get("status") == "online")
            offline_streams = total_streams - online_streams

            total_listeners = 0
            for s in streams_data:
                try:
                    total_listeners += int(s.get("listeners", 0) or 0)
                except (TypeError, ValueError):
                    continue

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

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Status written to {file_path}")

        except Exception as e:
            self.logger.error(f"Failed to write status JSON: {e}")

    def _write_recovery_state_for_stream(self, mount_point, stream_name):
        """Обновляет в status-online.json состояние потока на 'recovered' до отправки
        RECOVERY, чтобы другой процесс (например healthcheck) не отправил дубликат.
        """
        status_config = self.config.get('status_json', {})
        if not status_config.get('enabled', False):
            return
        file_path = status_config.get('file_path', 'status-online.json')
        try:
            if not os.path.exists(file_path):
                return
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            streams = data.get('streams', [])
            for s in streams:
                if s.get('mount_point') == mount_point and s.get('name') == stream_name:
                    s['status'] = 'online'
                    s['count_error'] = 0
                    s['first_offline_time'] = None
                    break
            else:
                return
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Recovery state written for {mount_point}_{stream_name}")
        except Exception as e:
            self.logger.warning(f"Could not write recovery state to {file_path}: {e}")

    def _write_stream_offline_state(self, mount_point, stream_name, count_error, first_offline_time):
        """Обновляет в status-online.json состояние потока (offline, count_error) до отправки
        ALERT, чтобы другой процесс не отправил дубликат при одновременном запуске.
        """
        status_config = self.config.get('status_json', {})
        if not status_config.get('enabled', False):
            return
        file_path = status_config.get('file_path', 'status-online.json')
        try:
            if not os.path.exists(file_path):
                return
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            streams = data.get('streams', [])
            for s in streams:
                if s.get('mount_point') == mount_point and s.get('name') == stream_name:
                    s['status'] = 'offline'
                    s['count_error'] = count_error
                    s['first_offline_time'] = first_offline_time
                    break
            else:
                return
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Offline state written for {mount_point}_{stream_name}")
        except Exception as e:
            self.logger.warning(f"Could not write offline state to {file_path}: {e}")

    def _load_previous_status(self):
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
                count_error = s.get('count_error', 0)
                first_offline_time = s.get('first_offline_time')
                if st in ('online', 'offline'):
                    result[key] = {
                        'status': st,
                        'count_error': count_error,
                        'first_offline_time': first_offline_time,
                    }
            return result
        except Exception as e:
            self.logger.debug(f"Could not load previous status from {file_path}: {e}")
            return result

    def run_check(self):
        self.logger.info("Running Icecast stream check")

        enabled_streams = self.get_enabled_streams()
        if not enabled_streams:
            self.logger.warning("No streams enabled for check")
            return True

        previous_run_status = self._load_previous_status()
        
        all_streams_ok = True
        streams_data = []
        icecast_config = self.config['icecast']
        protocol = 'https' if icecast_config.get('use_https', False) else 'http'
        
        for stream_config in enabled_streams:
            mount_point = stream_config.get('mount_point')
            stream_name = stream_config.get('name', mount_point)
            stream_key = f"{mount_point}_{stream_name}"

            prev_state = previous_run_status.get(stream_key, {})
            if isinstance(prev_state, dict):
                prev_status = prev_state.get('status')
                prev_count_error = int(prev_state.get('count_error', 0) or 0)
                prev_first_offline_time = prev_state.get('first_offline_time')
            else:
                prev_status = prev_state
                prev_count_error = 0
                prev_first_offline_time = None

            if stream_key not in self.consecutive_failures:
                self.consecutive_failures[stream_key] = 0
            if stream_key not in self.stream_status:
                self.stream_status[stream_key] = True
            
            stream_info = self.check_icecast_stream(stream_config)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if stream_info.get('status') == 'online':
                was_offline = prev_count_error >= 3

                self.logger.debug(
                    f"Stream '{stream_name}' online. "
                    f"Prev count_error: {prev_count_error}, was_offline: {was_offline}"
                )

                self.consecutive_failures[stream_key] = 0
                self.stream_status[stream_key] = True
                count_error = 0

                if stream_key in self.last_log_time:
                    del self.last_log_time[stream_key]

                if was_offline:
                    downtime_info = ""
                    if prev_first_offline_time:
                        try:
                            start_dt = datetime.strptime(prev_first_offline_time, "%Y-%m-%d %H:%M:%S")
                            end_dt = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
                            minutes_down = int((end_dt - start_dt).total_seconds() // 60)
                            downtime_info = (
                                f"\n\nDown since: {prev_first_offline_time}\n"
                                f"Total downtime: {minutes_down} min"
                            )
                        except Exception:
                            downtime_info = f"\n\nDown since: {prev_first_offline_time}"

                    self.logger.info(f"Sending recovery notification for stream '{stream_name}'")
                    # Сначала обновить файл статуса, чтобы второй процесс (напр. healthcheck)
                    # при чтении увидел count_error=0 и не отправил дубликат RECOVERY.
                    self._write_recovery_state_for_stream(mount_point, stream_name)
                    message = f"✅ <b>RECOVERY</b>\n\n"
                    message += f"Stream '{stream_name}' is back online.\n"
                    message += f"Server: {icecast_config['host']}\n"
                    message += f"Mount point: {mount_point}\n"
                    message += f"Listeners: {stream_info.get('listeners', 0)}"
                    message += downtime_info

                    self.send_telegram_notification(message, stream_key, skip_cooldown=True)
                    self.send_email_notification(
                        subject=f"Stream '{stream_name}' recovered",
                        message=message,
                        stream_key=stream_key,
                        skip_cooldown=True
                    )
            else:
                # первый оффлайн в серии — запоминаем время начала простоя
                if prev_count_error == 0:
                    first_offline_time = now_str
                else:
                    first_offline_time = prev_first_offline_time or now_str

                count_error = prev_count_error + 1
                self.consecutive_failures[stream_key] = count_error
                self.stream_status[stream_key] = False
                all_streams_ok = False

                self.logger.debug(
                    f"Stream '{stream_name}' offline. "
                    f"Consecutive failures (count_error): {count_error}"
                )

                if self.should_log_failure(stream_key, count_error):
                    self.logger.warning(
                        f"Stream '{stream_name}' unavailable (attempt {count_error})"
                    )
                    self.last_log_time[stream_key] = time.time()

                if count_error == 3:
                    # Сначала обновить файл статуса, чтобы второй процесс не отправил дубликат ALERT.
                    self._write_stream_offline_state(mount_point, stream_name, count_error, first_offline_time)
                    auth_config = icecast_config.get('auth', {})
                    auth_enabled = auth_config.get('enabled', False)
                    
                    message = f"🚨 <b>ALERT</b>\n\n"
                    message += f"Stream '{stream_name}' is down.\n"
                    message += f"Server: {icecast_config['host']}\n"
                    message += f"Protocol: {protocol.upper()}\n"
                    message += f"Mount point: {mount_point}\n"
                    if first_offline_time:
                        message += f"Down since: {first_offline_time}\n"
                    message += "\n"
                    message += f"**RESTART STREAMING**"

                    self.send_telegram_notification(message, stream_key)
                    self.logger.info(
                        f"Offline notification sent for stream '{stream_name}' "
                        f"after {count_error} consecutive errors"
                    )
                    self.send_email_notification(
                        subject=f"Stream '{stream_name}' down",
                        message=message,
                        stream_key=stream_key
                    )

            # сохранить текущее значение счётчика ошибок и время начала простоя
            if stream_info.get('status') == 'offline':
                stream_info['count_error'] = count_error
                stream_info['first_offline_time'] = first_offline_time
            else:
                stream_info['count_error'] = 0
                stream_info['first_offline_time'] = None
            streams_data.append(stream_info)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if all_streams_ok:
            self.last_success_time = now_str
        else:
            self.last_error_time = now_str

        self.write_status_json(streams_data)
        
        return all_streams_ok
    
    def run_continuous(self):
        check_interval = self.config.get('icecast', {}).get('check_interval', 60)
        self.logger.info(f"Starting continuous check every {check_interval}s")
        try:
            while True:
                self.run_check()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            self.logger.info("Interrupt received, shutting down")
        except Exception as e:
            self.logger.error(f"Critical error: {e}")
            sys.exit(1)

    def parse_json_response(self, stats, mount_point, stream_name):
        if 'icestats' in stats and 'source' in stats['icestats']:
            sources = stats['icestats']['source']
            if not isinstance(sources, list):
                sources = [sources]

            for source in sources:
                if source.get('mount') == mount_point:
                    listeners = source.get('listeners', 0)
                    self.logger.info(f"Stream '{stream_name}' ({mount_point}) online, listeners: {listeners}")

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

            self.logger.warning(f"Stream '{stream_name}' ({mount_point}) not found in statistics")
            return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in statistics")
        else:
            self.logger.error("Invalid Icecast JSON response format")
            return self.create_offline_stream_info(mount_point, stream_name, "Invalid JSON response format")

    def parse_html_response(self, html_content, mount_point, stream_name):
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        mount_cell = cells[0].get_text().strip()
                        if mount_cell == mount_point:
                            listeners = 0
                            if len(cells) >= 3:
                                try:
                                    listeners = int(cells[2].get_text().strip())
                                except:
                                    pass

                            self.logger.info(f"Stream '{stream_name}' ({mount_point}) online, listeners: {listeners}")
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

            self.logger.warning(f"Stream '{stream_name}' ({mount_point}) not found in HTML statistics")
            return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in HTML statistics")

        except ImportError:
            self.logger.error("BeautifulSoup not installed. pip install beautifulsoup4")
            return self.create_offline_stream_info(mount_point, stream_name, "HTML parsing requires beautifulsoup4")
        except Exception as e:
            self.logger.error(f"HTML parsing error: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"HTML parsing error: {e}")

    def parse_xml_response(self, xml_content, mount_point, stream_name):
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_content)

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

                    self.logger.info(f"Stream '{stream_name}' ({mount_point}) online, listeners: {listeners}")
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

            self.logger.warning(f"Stream '{stream_name}' ({mount_point}) not found in XML statistics")
            return self.create_offline_stream_info(mount_point, stream_name, "Mount point not found in XML statistics")

        except Exception as e:
            self.logger.error(f"XML parsing error: {e}")
            return self.create_offline_stream_info(mount_point, stream_name, f"XML parsing error: {e}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        checker = IcecastChecker()
        success = checker.run_check()
        sys.exit(0 if success else 1)
    else:
        checker = IcecastChecker()
        checker.run_continuous()


if __name__ == "__main__":
    main()
