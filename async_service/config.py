"""
Конфигурация асинхронного сервиса
"""
import os

# Режим HTTPS (true/false)
USE_HTTPS = os.getenv('USE_HTTPS', 'false').lower() in ('true', '1')

# URL основного Django сервиса
# В Docker использует имя контейнера 'web', локально - 'localhost'
# Автоматически определяет протокол (http/https) в зависимости от USE_HTTPS Django
django_url = os.getenv('DJANGO_SERVICE_URL', 'http://localhost:8000')
# Если Django использует HTTPS, обновляем URL
django_use_https = os.getenv('DJANGO_USE_HTTPS', 'false').lower() in ('true', '1')
if django_use_https:
    if django_url.startswith('http://'):
        django_url = django_url.replace('http://', 'https://')
        # Если порт 8000, меняем на 8443 (HTTPS порт Django)
        if ':8000' in django_url:
            django_url = django_url.replace(':8000', ':8443')

DJANGO_SERVICE_URL = django_url

# API токен для обратного вызова в Django (8 байт)
# Должен совпадать с константой в Django сервисе
API_TOKEN = os.getenv('API_TOKEN', 'secret123')

# Порт для запуска асинхронного сервиса
ASYNC_SERVICE_PORT = int(os.getenv('ASYNC_SERVICE_PORT', '8001'))
ASYNC_SERVICE_HTTPS_PORT = int(os.getenv('ASYNC_SERVICE_HTTPS_PORT', '8444'))
