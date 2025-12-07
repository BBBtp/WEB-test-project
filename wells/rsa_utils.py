"""
Утилиты для работы с RSA шифрованием для аутентификации
"""
import os
import base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

# Путь к директории с ключами
KEYS_DIR = Path(__file__).parent.parent / 'keys'
KEYS_DIR.mkdir(exist_ok=True)

PRIVATE_KEY_PATH = KEYS_DIR / 'private_key.pem'
PUBLIC_KEY_PATH = KEYS_DIR / 'public_key.pem'


def generate_rsa_keys():
    """Генерация пары RSA ключей (приватный и публичный)"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(PRIVATE_KEY_PATH, 'wb') as f:
        f.write(private_pem)

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    with open(PUBLIC_KEY_PATH, 'wb') as f:
        f.write(public_pem)
    return private_key, public_key


def load_private_key():
    """Загрузка приватного ключа из файла"""
    if not PRIVATE_KEY_PATH.exists():
        generate_rsa_keys()
    
    with open(PRIVATE_KEY_PATH, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    return private_key


def load_public_key():
    """Загрузка публичного ключа из файла"""
    if not PUBLIC_KEY_PATH.exists():
        generate_rsa_keys()
    
    with open(PUBLIC_KEY_PATH, 'rb') as f:
        public_key = serialization.load_pem_public_key(
            f.read(),
            backend=default_backend()
        )
    return public_key


def get_public_key_pem():
    """Получить публичный ключ в формате PEM (для передачи клиенту)"""
    if not PUBLIC_KEY_PATH.exists():
        generate_rsa_keys()
    
    with open(PUBLIC_KEY_PATH, 'rb') as f:
        return f.read().decode('utf-8')


def encrypt_with_public_key(data: str) -> str:
    """
    Шифрование данных публичным ключом
    Возвращает base64-encoded строку
    """
    public_key = load_public_key()
    encrypted = public_key.encrypt(
        data.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return base64.b64encode(encrypted).decode('utf-8')


def decrypt_with_private_key(encrypted_data: str) -> str:
    """
    Дешифрование данных приватным ключом
    Принимает base64-encoded строку
    """
    private_key = load_private_key()
    
    try:
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted = private_key.decrypt(
            encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Ошибка дешифрования: {str(e)}")


def create_auth_token(username: str, session_id: str) -> str:
    """
    Создание токена аутентификации в формате: username:session_id
    Токен шифруется публичным ключом
    """
    token_data = f"{username}:{session_id}"
    return encrypt_with_public_key(token_data)


def parse_auth_token(encrypted_token: str) -> tuple:
    """
    Парсинг токена аутентификации
    Возвращает (username, session_id)
    """
    decrypted = decrypt_with_private_key(encrypted_token)
    username, session_id = decrypted.split(':', 1)
    return username, session_id

