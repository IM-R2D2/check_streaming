#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from datetime import datetime

import requests

from icecast_checker import IcecastChecker


class CustomChecker(IcecastChecker):
    """Checker for custom JSON API (mount -> listeners). Notifications and status-online.json logic inherited from IcecastChecker."""

    def check_icecast_stream(self, stream_config):
        icecast_config = self.config.get("icecast", {})

        host = icecast_config.get("host", "localhost")
        port = icecast_config.get("port", 8000)
        mount_point = stream_config.get("mount_point", "/stream")
        stream_name = stream_config.get("name", mount_point)
        timeout = icecast_config.get("timeout", 15)
        use_https = icecast_config.get("use_https", False)
        user_agent = icecast_config.get("user_agent", "IcecastChecker/1.0")
        endpoint = icecast_config.get("endpoint", "/status-json.xsl")

        auth_config = icecast_config.get("auth", {})
        auth_enabled = auth_config.get("enabled", False)
        auth_username = auth_config.get("username", "")
        auth_password = auth_config.get("password", "")

        self.logger.debug(
            f"[custom] host={host}, port={port}, use_https={use_https}, endpoint={endpoint}"
        )

        protocol = "https" if use_https else "http"

        if (use_https and port == 443) or (not use_https and port == 80):
            base_url = f"{protocol}://{host}"
        else:
            base_url = f"{protocol}://{host}:{port}"

        stats_url = f"{base_url}{endpoint}"
        self.logger.debug(f"[custom] Using endpoint: {stats_url}")

        headers = {
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Connection": "close",
        }

        auth = None
        if auth_enabled and auth_username and auth_password:
            auth = (auth_username, auth_password)

        try:
            response = requests.get(
                stats_url, timeout=timeout, headers=headers, auth=auth
            )
            response.raise_for_status()

            stats_map = response.json()
            return self.parse_simple_map_response(stats_map, mount_point, stream_name)

        except requests.exceptions.ConnectionError as e:
            self.logger.error(
                f"[custom] Connection error to {host}:{port}: {e}"
            )
            return self.create_offline_stream_info(
                mount_point, stream_name, f"Connection error: {e}"
            )
        except requests.exceptions.Timeout as e:
            self.logger.error(
                f"[custom] Timeout connecting to {host}:{port}: {e}"
            )
            return self.create_offline_stream_info(
                mount_point, stream_name, f"Timeout: {e}"
            )
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"[custom] HTTP error: {e}")
            return self.create_offline_stream_info(
                mount_point, stream_name, f"HTTP error: {e}"
            )
        except ValueError as e:
            self.logger.error(f"[custom] JSON parse error: {e}")
            return self.create_offline_stream_info(
                mount_point, stream_name, f"JSON parse error: {e}"
            )
        except Exception as e:
            self.logger.error(f"[custom] Unexpected error checking stream: {e}")
            return self.create_offline_stream_info(
                mount_point, stream_name, f"Unexpected error: {e}"
            )

    def parse_simple_map_response(self, stats_map, mount_point, stream_name):
        if not isinstance(stats_map, dict):
            self.logger.error("[custom] Invalid JSON: expected object {mount: listeners}")
            return self.create_offline_stream_info(
                mount_point, stream_name, "Invalid custom JSON format"
            )

        if mount_point not in stats_map:
            self.logger.warning(
                f"[custom] Stream '{stream_name}' ({mount_point}) not found in custom stats"
            )
            return self.create_offline_stream_info(
                mount_point,
                stream_name,
                "Mount point not found in custom statistics",
            )

        try:
            listeners = int(stats_map.get(mount_point, 0))
        except (TypeError, ValueError):
            listeners = 0

        self.logger.info(
            f"[custom] Stream '{stream_name}' ({mount_point}) online, listeners: {listeners}"
        )

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
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        checker = CustomChecker()
        success = checker.run_check()
        sys.exit(0 if success else 1)
    else:
        checker = CustomChecker()
        checker.run_continuous()


if __name__ == "__main__":
    main()

