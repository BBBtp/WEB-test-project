# Описание изменений

## 1. Асинхронный сервис для расчета risk_level

### Созданные файлы

#### `async_service/` - Новый асинхронный сервис на FastAPI
- **`async_service/__init__.py`** - Инициализация модуля
- **`async_service/main.py`** - FastAPI приложение с endpoint `/calculate`
  - Принимает `assessment_id` и `total_score`
  - Использует `asyncio.sleep(5-10 сек)` для задержки
  - Вычисляет `risk_level` и `recommendation` через `calculator.py`
  - Отправляет результат обратно в Django через HTTP с заголовком `X-API-TOKEN`
- **`async_service/calculator.py`** - Логика вычисления risk_level и recommendation
- **`async_service/config.py`** - Конфигурация (URL Django, токен, порты)
- **`async_service/requirements.txt`** - Зависимости (fastapi, uvicorn, aiohttp, cryptography)
- **`async_service/Dockerfile`** - Docker образ для асинхронного сервиса
- **`async_service/generate_cert.py`** - Генерация SSL сертификатов для HTTPS
- **`async_service/README.md`** - Документация сервиса
- **`async_service/.dockerignore`** - Исключения для Docker сборки

### Измененные файлы

#### Django (основной сервис)

**`wells/models.py`**
- Добавлено поле `result_value = models.DecimalField(...)` в модель `RiskAssessment`

**`wells/migrations/0006_add_result_value.py`**
- Миграция для добавления поля `result_value`

**`wells/serializers.py`**
- Добавлено поле `result_value` в `RiskAssessmentSerializer`

**`wells/api_views.py`**
- Добавлен метод `start_async_calculation()` - `POST /api/deep-vein-thrombosis/{id}/calculate/`
  - Запускает асинхронный расчет, отправляет запрос в async_service
  - Возвращает `202 Accepted`
- Добавлен метод `receive_calculation_result()` - `POST /api/deep-vein-thrombosis/{id}/result/`
  - Принимает результат от async_service
  - Проверяет заголовок `X-API-TOKEN` (константа `"secret123"`)
  - При неверном токене возвращает `403 Forbidden`
  - Обновляет поля: `result_value`, `risk_level`, `recommendation`
- Обновлен метод `complete_assessment()` - автоматически запускает расчет, если `result_value` отсутствует

**`wells/api_urls.py`**
- Добавлены маршруты:
  - `deep-vein-thrombosis/<int:assessment_id>/calculate/`
  - `deep-vein-thrombosis/<int:assessment_id>/result/`

**`requirements.txt`**
- Добавлен `requests==2.32.3` для HTTP-запросов к async_service

**`docker-compose.yml`**
- Добавлен сервис `async_service`:
  - Порт 8001 (HTTP), 8444 (HTTPS)
  - Поддержка HTTPS режима
  - Автоматическая генерация SSL сертификатов
- Обновлен сервис `web`:
  - Добавлена переменная окружения `ASYNC_SERVICE_URL`
  - Добавлена зависимость от `async_service`

---

## 2. Гостевая сессия с просмотренными услугами

### Созданные файлы

**`wells/guest_session_utils.py`**
- Утилиты для работы с гостевой сессией в Redis
- Функции:
  - `get_or_create_guest_session()` - создание/получение сессии
  - `add_viewed_symptom()` - добавление симптома в просмотренные
  - `get_viewed_symptoms()` - получение списка просмотренных симптомов
  - `refresh_guest_session()` - обновление TTL сессии
- Хранение в Redis (db=2), TTL = 20 минут

### Измененные файлы

**`wells/middleware.py`**
- Добавлен класс `GuestSessionMiddleware`:
  - Создает/обновляет гостевую сессию для неавторизованных пользователей
  - Устанавливает cookie `guest_session_id` (20 минут)
  - Сохраняет `guest_session_id` в `request.guest_session_id`

**`wells_project/settings.py`**
- Добавлен `'wells.middleware.GuestSessionMiddleware'` в `MIDDLEWARE`

**`wells/api_views.py`**
- Обновлен `ClinicalSymptomListAPIView`:
  - Добавлен параметр `recently_viewed` (query param)
  - Фильтрация по недавно просмотренным симптомам из Redis
  - Работает только для неавторизованных пользователей
  - Сохраняет порядок просмотра (последние первыми)
- Обновлен `ClinicalSymptomDetailAPIView`:
  - При просмотре детальной страницы автоматически добавляет симптом в просмотренные
  - Работает только для неавторизованных пользователей

**`wells/api_urls.py`**
- Изменений нет (используются существующие маршруты)

---

## API Endpoints

### Асинхронный сервис

- `POST /api/deep-vein-thrombosis/{id}/calculate/` - Запуск асинхронного расчета
- `POST /api/deep-vein-thrombosis/{id}/result/` - Прием результата (требует `X-API-TOKEN: secret123`)

### Гостевая сессия

- `GET /api/symptoms/?recently_viewed=true` - Список недавно просмотренных симптомов

---

## Конфигурация

### Переменные окружения

**Django:**
- `ASYNC_SERVICE_URL` - URL асинхронного сервиса (по умолчанию: `http://async_service:8001`)

**Async Service:**
- `DJANGO_SERVICE_URL` - URL Django сервиса (по умолчанию: `http://localhost:8000`)
- `DJANGO_USE_HTTPS` - Использование HTTPS для Django (по умолчанию: `false`)
- `API_TOKEN` - Токен для обратного вызова (по умолчанию: `secret123`)
- `USE_HTTPS` - Режим HTTPS для async_service (по умолчанию: `false`)
- `ASYNC_SERVICE_PORT` - Порт HTTP (по умолчанию: `8001`)
- `ASYNC_SERVICE_HTTPS_PORT` - Порт HTTPS (по умолчанию: `8444`)

### Константы

- `API_TOKEN = "secret123"` - Токен для авторизации (8 байт)
- `GUEST_SESSION_TTL = 20 * 60` - Время жизни гостевой сессии (20 минут)

---

## Запуск

```bash
docker-compose up --build
```

Сервисы:
- Django: `http://localhost:8000` (HTTP), `https://localhost:8443` (HTTPS)
- Async Service: `http://localhost:8001` (HTTP), `https://localhost:8444` (HTTPS)
