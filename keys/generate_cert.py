#!/usr/bin/env python3
"""
Скрипт для генерации self-signed SSL сертификатов с помощью cryptography
"""
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta
from pathlib import Path
import ipaddress

# Определяем путь к директории keys
# Если скрипт запускается из контейнера, используем /app/keys
# Иначе используем директорию, где находится скрипт
if Path("/app/keys").exists() or Path("/app").exists():
    keys_dir = Path("/app/keys")
else:
    keys_dir = Path(__file__).parent

# Создаем директорию, если её нет
keys_dir.mkdir(parents=True, exist_ok=True)

# Генерируем приватный ключ
print("Генерация приватного ключа...")
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=4096,
)

# Создаем самоподписанный сертификат
print("Создание сертификата...")
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Moscow"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "Moscow"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Wells"),
    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
])

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365)
).add_extension(
    x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.DNSName("127.0.0.1"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]),
    critical=False,
).sign(private_key, hashes.SHA256())

# Сохраняем приватный ключ
print("Сохранение приватного ключа...")
key_path = keys_dir / "key.pem"
with open(key_path, "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

# Сохраняем сертификат
print("Сохранение сертификата...")
cert_path = keys_dir / "cert.pem"
with open(cert_path, "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print("✓ SSL сертификаты успешно созданы!")
print(f"  - cert.pem: {cert_path}")
print(f"  - key.pem: {key_path}")
