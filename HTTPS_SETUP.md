# Настройка HTTPS/HTTP для бэкенд сервера

Бэкенд сервер поддерживает работу как в режиме HTTP, так и в режиме HTTPS. Вы можете выбрать режим при запуске контейнера.

## Выбор режима работы

### Режим HTTP (по умолчанию)

Для запуска в режиме HTTP:

**Linux/Mac (Bash):**
```bash
docker-compose up --build
```

**Windows PowerShell:**
```powershell
docker-compose up --build
```

Или явно указать:

**Linux/Mac (Bash):**
```bash
USE_HTTPS=false docker-compose up --build
```

**Windows PowerShell:**
```powershell
$env:USE_HTTPS="false"; docker-compose up --build
```

Сервер будет доступен по адресу: **http://localhost:8000**

### Режим HTTPS

Для запуска в режиме HTTPS:

**Linux/Mac (Bash):**
```bash
USE_HTTPS=true docker-compose up --build
```

**Windows PowerShell:**
```powershell
$env:USE_HTTPS="true"; docker-compose up --build
```

**SSL сертификаты генерируются автоматически** при первом запуске контейнера в режиме HTTPS, если их еще нет. Они будут созданы в директории `keys/`:
- `cert.pem` - SSL сертификат
- `key.pem` - Приватный ключ

Сервер будет доступен по адресу: **https://localhost:8443**

> 💡 **Примечание**: Если вы хотите сгенерировать сертификаты вручную перед запуском, выполните:
> ```bash
> python keys/generate_cert.py
> ```

### Использование .env файла (рекомендуется)

Самый удобный способ - создать файл `.env` в корне проекта. Docker Compose автоматически загрузит переменные из этого файла.

**Создайте файл `.env` в корне проекта:**

Для HTTP режима:
```env
USE_HTTPS=false
HTTP_PORT=8000
HTTPS_PORT=8443
```

Для HTTPS режима:
```env
USE_HTTPS=true
HTTP_PORT=8000
HTTPS_PORT=8443
```

После создания файла `.env` просто запускайте:
```bash
docker-compose up --build
```

> 💡 **Совет**: Файл `.env` уже должен быть в `.gitignore`, чтобы не попадать в репозиторий. Используйте `env.example` как шаблон.

### Использование PowerShell скрипта (только для Windows)

Для упрощения запуска в Windows PowerShell можно использовать скрипт `start.ps1`:

**HTTP режим:**
```powershell
.\start.ps1 -Mode http
```

**HTTPS режим:**
```powershell
.\start.ps1 -Mode https
```

Или просто:
```powershell
.\start.ps1
```
(по умолчанию используется HTTP режим)

## Локальный запуск (без Docker)

### HTTP режим:

```bash
# Установите зависимости
pip install -r requirements.txt

# Выполните миграции
python manage.py migrate

# Запустите сервер с Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 wells_project.wsgi:application
```

### HTTPS режим:

```bash
# Установите зависимости
pip install -r requirements.txt

# Выполните миграции
python manage.py migrate

# Сгенерируйте сертификаты (если их нет)
python keys/generate_cert.py

# Запустите сервер с Gunicorn и SSL
gunicorn --bind 0.0.0.0:8443 --keyfile keys/key.pem --certfile keys/cert.pem --workers 3 --timeout 120 wells_project.wsgi:application
```

## Доступ к серверу

- **HTTP URL**: `http://localhost:8000` (режим HTTP)
- **HTTPS URL**: `https://localhost:8443` (режим HTTPS)

⚠️ **Важно**: При использовании self-signed сертификатов браузер покажет предупреждение о безопасности. Это нормально для разработки. Нажмите "Продолжить" или "Advanced" → "Proceed to localhost".

## Настройки

### Изменение настроек HTTPS

В файле `wells_project/settings.py` можно настроить:

- `SECURE_SSL_REDIRECT` - автоматическое перенаправление HTTP на HTTPS (по умолчанию отключено для разработки)
- `SESSION_COOKIE_SECURE` - безопасные cookies только через HTTPS
- `CSRF_COOKIE_SECURE` - безопасные CSRF cookies только через HTTPS

### Изменение портов

Вы можете изменить порты через переменные окружения:

**Linux/Mac (Bash):**
```bash
HTTP_PORT=8080 HTTPS_PORT=9443 USE_HTTPS=true docker-compose up --build
```

**Windows PowerShell:**
```powershell
$env:HTTP_PORT="8080"; $env:HTTPS_PORT="9443"; $env:USE_HTTPS="true"; docker-compose up --build
```

Или в файле `.env` (рекомендуется):
```env
HTTP_PORT=8080
HTTPS_PORT=9443
USE_HTTPS=true
```

## Production

Для production окружения:

1. Используйте режим HTTPS: `USE_HTTPS=true`
2. Используйте сертификаты от доверенного CA (например, Let's Encrypt)
3. Включите `SECURE_SSL_REDIRECT = True` в settings.py
4. Настройте Nginx как reverse proxy для лучшей производительности
5. Используйте переменные окружения для секретных ключей
