#!/bin/bash
# Скрипт запуска сервера с поддержкой выбора HTTP/HTTPS режима

set -e

# Выполняем миграции
echo "Выполнение миграций..."
python manage.py makemigrations
python manage.py migrate

# Создаем суперпользователя, если его нет
echo "Проверка суперпользователя..."
echo 'from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username="admin").exists() or User.objects.create_superuser("admin", "admin@example.com", "admin")' | python manage.py shell

# Проверяем режим работы (USE_HTTPS из переменной окружения)
USE_HTTPS=${USE_HTTPS:-false}

if [ "$USE_HTTPS" = "true" ] || [ "$USE_HTTPS" = "1" ]; then
    echo "=== Запуск в режиме HTTPS ==="
    
    # Создаем директорию для сертификатов
    mkdir -p /app/keys
    
    # Генерируем сертификаты, если их нет
    if [ ! -f /app/keys/cert.pem ] || [ ! -f /app/keys/key.pem ]; then
        echo "SSL сертификаты не найдены. Генерация..."
        python /app/keys/generate_cert.py
    else
        echo "SSL сертификаты уже существуют."
    fi
    
    # Запускаем Gunicorn с SSL
    echo "Запуск Gunicorn на порту 8443 (HTTPS)..."
    exec gunicorn --bind 0.0.0.0:8443 \
        --keyfile /app/keys/key.pem \
        --certfile /app/keys/cert.pem \
        --workers 3 \
        --timeout 120 \
        wells_project.wsgi:application
else
    echo "=== Запуск в режиме HTTP ==="
    echo "Запуск Gunicorn на порту 8000 (HTTP)..."
    exec gunicorn --bind 0.0.0.0:8000 \
        --workers 3 \
        --timeout 120 \
        wells_project.wsgi:application
fi


