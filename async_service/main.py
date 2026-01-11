"""
Асинхронный сервис на FastAPI + asyncio для расчета risk_level и recommendation
"""
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import DJANGO_SERVICE_URL, API_TOKEN
from calculator import calculate_risk_assessment

app = FastAPI(title="Async Risk Assessment Service", version="1.0.0")


class CalculateRequest(BaseModel):
    """Модель запроса для расчета"""
    assessment_id: int
    total_score: int


@app.post("/calculate")
async def calculate_risk_level(request: CalculateRequest):
    """
    Асинхронный endpoint для расчета risk_level и recommendation.
    
    Использует asyncio.sleep() для имитации отложенного действия (5-10 секунд).
    После вычисления отправляет результат обратно в Django сервис.
    
    Args:
        request: Запрос с assessment_id и total_score
        
    Returns:
        Подтверждение, что расчет запущен
    """
    assessment_id = request.assessment_id
    total_score = request.total_score
    
    # Запускаем асинхронную задачу в фоне
    # Это позволяет вернуть ответ сразу, не дожидаясь завершения расчета
    asyncio.create_task(process_calculation(assessment_id, total_score))
    
    return {
        "message": "Расчет запущен",
        "assessment_id": assessment_id,
        "status": "processing"
    }


async def process_calculation(assessment_id: int, total_score: int):
    """
    Асинхронная функция для обработки расчета.
    
    Использует asyncio.sleep() для задержки 5-10 секунд (имитация долгой операции).
    Затем вычисляет результат и отправляет его в Django сервис.
    
    Args:
        assessment_id: ID заявки
        total_score: Сумма баллов симптомов
    """
    # Имитация отложенного действия через asyncio.sleep()
    # Используем случайную задержку от 5 до 10 секунд
    import random
    delay = random.uniform(5.0, 10.0)
    
    # asyncio.sleep() - это асинхронная функция, которая не блокирует event loop
    # Пока мы ждем, другие запросы могут обрабатываться
    await asyncio.sleep(delay)
    
    # Вычисление результата (синхронная операция, но выполняется быстро)
    result = calculate_risk_assessment(total_score)
    
    # Отправка результата в Django сервис через асинхронный HTTP-запрос
    # aiohttp.ClientSession() использует asyncio для неблокирующих HTTP-запросов
    # Для работы с self-signed сертификатами отключаем проверку SSL
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        callback_url = f"{DJANGO_SERVICE_URL}/api/deep-vein-thrombosis/{assessment_id}/result/"
        
        # Подготовка данных для отправки
        payload = {
            "result_value": result["result_value"],
            "risk_level": result["risk_level"],
            "recommendation": result["recommendation"]
        }
        
        # Асинхронный HTTP POST запрос с заголовком X-API-TOKEN
        # await позволяет event loop обрабатывать другие задачи во время ожидания ответа
        headers = {
            "X-API-TOKEN": API_TOKEN,
            "Content-Type": "application/json"
        }
        
        try:
            async with session.post(callback_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    print(f"Результат успешно отправлен для assessment_id={assessment_id}")
                elif response.status == 403:
                    print(f"Ошибка авторизации при отправке результата для assessment_id={assessment_id}")
                else:
                    print(f"Ошибка при отправке результата: статус {response.status}")
        except Exception as e:
            print(f"Ошибка при отправке результата в Django: {e}")


@app.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    return {"status": "ok", "service": "async-risk-assessment"}


if __name__ == "__main__":
    import uvicorn
    from config import ASYNC_SERVICE_PORT
    
    # Запуск FastAPI приложения через uvicorn
    # uvicorn использует asyncio event loop для обработки асинхронных запросов
    uvicorn.run(app, host="0.0.0.0", port=ASYNC_SERVICE_PORT)
