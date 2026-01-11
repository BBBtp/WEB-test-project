# Асинхронный сервис для расчета risk_level

Сервис на FastAPI + asyncio для асинхронного вычисления уровня риска и рекомендаций.

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Запуск сервиса

```bash
python -m async_service.main
```

Или через uvicorn:

```bash
uvicorn async_service.main:app --host 0.0.0.0 --port 8001
```

## Переменные окружения

- `DJANGO_SERVICE_URL` - URL основного Django сервиса (по умолчанию: `http://localhost:8000`)
- `API_TOKEN` - Токен для обратного вызова (по умолчанию: `secret123`)
- `ASYNC_SERVICE_PORT` - Порт для запуска сервиса (по умолчанию: `8001`)

## API Endpoints

### POST /calculate

Запускает асинхронный расчет risk_level и recommendation.

**Тело запроса:**
```json
{
    "assessment_id": 1,
    "total_score": 5
}
```

**Ответ:**
```json
{
    "message": "Расчет запущен",
    "assessment_id": 1,
    "status": "processing"
}
```

### GET /health

Проверка работоспособности сервиса.

## Как работает асинхронность

1. **asyncio.sleep()** - используется для имитации задержки 5-10 секунд. Не блокирует event loop, позволяя обрабатывать другие запросы.

2. **async/await** - все HTTP-запросы выполняются асинхронно через aiohttp, не блокируя выполнение других задач.

3. **asyncio.create_task()** - запускает расчет в фоне, позволяя сразу вернуть ответ клиенту.

4. **Event Loop** - FastAPI использует asyncio event loop для обработки всех асинхронных операций.
