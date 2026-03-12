FROM python:3.14.3-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем скрипты и README
COPY icecast_checker.py custom_checker.py global-checker.py logging_utils.py README.md ./

# Опционально: копии примеров конфигов (для удобства внутри контейнера)
COPY config_icecast_example.json config_custom_example.json ./

# По умолчанию ожидаем, что реальный config.json проброшен томом
# и лежит рядом с приложением в /app/config.json

ENV PYTHONUNBUFFERED=1

CMD ["python", "global-checker.py"]

