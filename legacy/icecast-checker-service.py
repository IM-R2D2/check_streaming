#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows Service для мониторинга Icecast потоков
"""

import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import time
import logging

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from icecast_checker import IcecastChecker

class IcecastCheckerService(win32serviceutil.ServiceFramework):
    """Windows служба для мониторинга Icecast"""
    
    _svc_name_ = "IcecastChecker"
    _svc_display_name_ = "Icecast Stream Monitor"
    _svc_description_ = "Мониторинг Icecast потоков с уведомлениями в Telegram"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True
        
        # Настройка логирования для службы
        self.setup_logging()
        
    def setup_logging(self):
        """Настройка логирования для службы"""
        try:
            # Создаем директорию для логов если не существует
            log_dir = os.path.join(os.path.dirname(__file__), 'logs')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            log_file = os.path.join(log_dir, 'icecast_service.log')
            
            # Настройка логирования
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file, encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )
            
            self.logger = logging.getLogger('IcecastService')
            self.logger.info("Служба Icecast Checker инициализирована")
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Ошибка настройки логирования: {e}")
    
    def SvcStop(self):
        """Остановка службы"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        self.logger.info("Получен сигнал остановки службы")
    
    def SvcDoRun(self):
        """Основной цикл службы"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        self.logger.info("Служба Icecast Checker запущена")
        
        try:
            # Инициализируем монитор
            checker = IcecastChecker()
            
            while self.is_running:
                try:
                    # Выполняем проверку
                    checker.run_check()
                    
                    # Ждем интервал проверки или сигнал остановки
                    icecast_config = checker.config.get('icecast', {})
                    check_interval = icecast_config.get('check_interval', 60)
                    
                    # Ждем с возможностью прерывания
                    result = win32event.WaitForSingleObject(
                        self.hWaitStop, 
                        check_interval * 1000
                    )
                    
                    if result == win32event.WAIT_OBJECT_0:
                        # Получен сигнал остановки
                        break
                        
                except Exception as e:
                    self.logger.error(f"Ошибка в цикле мониторинга: {e}")
                    time.sleep(30)  # Ждем 30 секунд перед повтором
                    
        except Exception as e:
            self.logger.error(f"Критическая ошибка службы: {e}")
            servicemanager.LogErrorMsg(f"Критическая ошибка: {e}")
        
        self.logger.info("Служба Icecast Checker остановлена")

def main():
    """Точка входа для службы"""
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(IcecastCheckerService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(IcecastCheckerService)

if __name__ == '__main__':
    main()

