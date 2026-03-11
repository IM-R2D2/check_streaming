#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Глобальный чекер:
- читает config.json
- по полю type выбирает, какой чекер запускать:
  - type: "icecast"  -> IcecastChecker из icecast_checker.py
  - type: "custom"   -> CustomChecker из custom_checker.py
"""

import json
import os
import sys

from icecast_checker import IcecastChecker
from custom_checker import CustomChecker


def load_config(config_path: str = "config.json") -> dict:
    abs_path = os.path.abspath(config_path)
    if not os.path.exists(abs_path):
        print(f"Ошибка: Файл конфигурации {abs_path} не найден")
        sys.exit(1)

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Ошибка в файле конфигурации {abs_path}: {e}")
        sys.exit(1)


def main():
    """Точка входа для выбора подходящего чекера."""
    config = load_config()
    icecast_cfg = config.get("icecast", {})
    checker_type = icecast_cfg.get("type", "icecast").lower()

    once = len(sys.argv) > 1 and sys.argv[1] == "--once"

    if checker_type == "custom":
        checker = CustomChecker()
    else:
        checker = IcecastChecker()

    if once:
        success = checker.run_check()
        sys.exit(0 if success else 1)
    else:
        checker.run_continuous()


if __name__ == "__main__":
    main()

