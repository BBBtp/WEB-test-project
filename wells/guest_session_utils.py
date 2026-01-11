"""
Утилиты для работы с гостевой сессией
Гостевая сессия не связана с авторизацией, хранится в Redis, действует 20 минут
"""
import json
import time
import uuid
from datetime import datetime, timedelta
from django.conf import settings
import redis

# Подключение к Redis для гостевых сессий
guest_session_storage = redis.StrictRedis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=2  # Используем отдельную БД для гостевых сессий
)

# Время жизни гостевой сессии (20 минут в секундах)
GUEST_SESSION_TTL = 20 * 60  # 1200 секунд


def get_or_create_guest_session(session_id=None):
    """
    Получить существующую гостевую сессию или создать новую.
    
    Args:
        session_id: ID существующей сессии (из cookie)
        
    Returns:
        tuple: (session_id, session_data, is_new)
    """
    if session_id:
        # Проверяем существующую сессию
        session_data = guest_session_storage.get(f"guest_session:{session_id}")
        if session_data:
            try:
                data = json.loads(session_data.decode('utf-8'))
                created_at = datetime.fromisoformat(data['created_at'])
                
                # Проверяем, не истекла ли сессия
                if datetime.now() - created_at < timedelta(seconds=GUEST_SESSION_TTL):
                    # Обновляем TTL при использовании
                    guest_session_storage.expire(f"guest_session:{session_id}", GUEST_SESSION_TTL)
                    return session_id, data, False
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
    
    # Создаем новую сессию
    new_session_id = str(uuid.uuid4())
    session_data = {
        'created_at': datetime.now().isoformat(),
        'viewed_symptoms': []  # Список ID просмотренных симптомов
    }
    
    # Сохраняем в Redis с TTL 20 минут
    guest_session_storage.setex(
        f"guest_session:{new_session_id}",
        GUEST_SESSION_TTL,
        json.dumps(session_data)
    )
    
    return new_session_id, session_data, True


def add_viewed_symptom(session_id, symptom_id):
    """
    Добавить симптом в список просмотренных для гостевой сессии.
    
    Args:
        session_id: ID гостевой сессии
        symptom_id: ID симптома
    """
    if not session_id:
        return
    
    key = f"guest_session:{session_id}"
    session_data = guest_session_storage.get(key)
    
    if not session_data:
        return
    
    try:
        data = json.loads(session_data.decode('utf-8'))
        viewed_symptoms = data.get('viewed_symptoms', [])
        
        # Добавляем симптом, если его еще нет
        if symptom_id not in viewed_symptoms:
            viewed_symptoms.append(symptom_id)
            # Ограничиваем список последними 20 просмотренными
            if len(viewed_symptoms) > 20:
                viewed_symptoms = viewed_symptoms[-20:]
            
            data['viewed_symptoms'] = viewed_symptoms
            
            # Обновляем в Redis с обновленным TTL
            guest_session_storage.setex(
                key,
                GUEST_SESSION_TTL,
                json.dumps(data)
            )
    except (json.JSONDecodeError, KeyError):
        pass


def get_viewed_symptoms(session_id):
    """
    Получить список ID просмотренных симптомов для гостевой сессии.
    
    Args:
        session_id: ID гостевой сессии
        
    Returns:
        list: Список ID симптомов
    """
    if not session_id:
        return []
    
    key = f"guest_session:{session_id}"
    session_data = guest_session_storage.get(key)
    
    if not session_data:
        return []
    
    try:
        data = json.loads(session_data.decode('utf-8'))
        return data.get('viewed_symptoms', [])
    except (json.JSONDecodeError, KeyError):
        return []


def refresh_guest_session(session_id):
    """
    Обновить время жизни гостевой сессии.
    
    Args:
        session_id: ID гостевой сессии
    """
    if not session_id:
        return
    
    key = f"guest_session:{session_id}"
    if guest_session_storage.exists(key):
        guest_session_storage.expire(key, GUEST_SESSION_TTL)
