# SSL Сертификаты

Эта директория содержит SSL сертификаты для HTTPS соединения.

## Генерация сертификатов

Для генерации self-signed SSL сертификатов выполните:

```bash
python keys/generate_cert.py
```

Или используйте OpenSSL напрямую:

```bash
cd keys
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/C=RU/ST=Moscow/L=Moscow/O=Wells/CN=localhost"
```

## Файлы

- `cert.pem` - SSL сертификат
- `key.pem` - Приватный ключ

## Важно

⚠️ Эти сертификаты являются self-signed (самоподписанными) и подходят только для разработки.

Для production используйте сертификаты от доверенного CA (например, Let's Encrypt).


