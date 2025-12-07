"""
Утилиты для работы с Redis через Lua скрипты
"""
import redis
from django.conf import settings


def get_redis_client():
    """Получить клиент Redis"""
    return redis.StrictRedis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=False
    )


GET_ACTIVE_USERS_WITH_SESSIONS_SCRIPT = """
local active_sessions = {}
local cursor = "0"
local pattern = "*"

repeat
    local result = redis.call("SCAN", cursor, "MATCH", pattern, "COUNT", 100)
    cursor = result[1]
    local keys = result[2]
    
    for i, key in ipairs(keys) do
        local username = redis.call("GET", key)
        if username then
            local username_str = tostring(username)
            -- Фильтруем: исключаем пустые строки и значения с двоеточиями (Django кэш)
            if username_str ~= "" and username_str ~= nil and string.find(username_str, ":") == nil then
                local key_str = tostring(key)
                table.insert(active_sessions, username_str)
                table.insert(active_sessions, key_str)
            end
        end
    end
until cursor == "0"

return active_sessions
"""


def get_active_users_with_sessions_lua():
    """
    Получить список активных пользователей с их сессиями через Lua скрипт
    Возвращает словарь: {username: [session_ids]}
    """
    redis_client = get_redis_client()
    
    try:
        script_sha = redis_client.script_load(GET_ACTIVE_USERS_WITH_SESSIONS_SCRIPT)
        result = redis_client.evalsha(script_sha, 0)
        
        # Преобразуем результат в словарь
        users_sessions = {}
        if result:
            i = 0
            while i < len(result):
                username_bytes = result[i]
                session_id_bytes = result[i + 1] if i + 1 < len(result) else None
                
                username = username_bytes.decode('utf-8') if isinstance(username_bytes, bytes) else username_bytes
                session_id = session_id_bytes.decode('utf-8') if session_id_bytes and isinstance(session_id_bytes, bytes) else session_id_bytes
                
                if username:
                    if username not in users_sessions:
                        users_sessions[username] = []
                    if session_id:
                        users_sessions[username].append(session_id)
                
                i += 2
        
        return users_sessions
    except redis.exceptions.ResponseError as e:
        if "NOSCRIPT" in str(e):
            script_sha = redis_client.script_load(GET_ACTIVE_USERS_WITH_SESSIONS_SCRIPT)
            result = redis_client.evalsha(script_sha, 0)
            users_sessions = {}
            if result:
                i = 0
                while i < len(result):
                    username_bytes = result[i]
                    session_id_bytes = result[i + 1] if i + 1 < len(result) else None
                    
                    username = username_bytes.decode('utf-8') if isinstance(username_bytes, bytes) else username_bytes
                    session_id = session_id_bytes.decode('utf-8') if session_id_bytes and isinstance(session_id_bytes, bytes) else session_id_bytes
                    
                    if username:
                        if username not in users_sessions:
                            users_sessions[username] = []
                        if session_id:
                            users_sessions[username].append(session_id)
                    
                    i += 2
            
            return users_sessions
        raise