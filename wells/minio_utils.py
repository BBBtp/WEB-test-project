import os
import uuid
from django.conf import settings
from minio import Minio
from minio.error import S3Error
import json

def get_minio_client():
    """Получить клиент MinIO"""
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )

def ensure_bucket_public(client, bucket_name):
    """Делает бакет публичным для чтения объектов"""
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
        }]
    }
    client.set_bucket_policy(bucket_name, json.dumps(policy))

def generate_image_name(original_filename):
    """Генерировать имя файла на латинице"""
    # Получаем расширение файла
    _, ext = os.path.splitext(original_filename)
    if not ext:
        ext = '.jpg'
    
    # Генерируем уникальное имя на латинице
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{ext}"


def upload_image(file, image_name):
    """Загрузить изображение в MinIO"""
    try:
        client = get_minio_client()

        if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
            client.make_bucket(settings.MINIO_BUCKET_NAME)
            ensure_bucket_public(client, settings.MINIO_BUCKET_NAME)

        file.seek(0)
        client.put_object(
            settings.MINIO_BUCKET_NAME,
            image_name,
            file,
            length=-1,
            part_size=10 * 1024 * 1024,
            content_type = "image/png"
        )
        return True
    except S3Error as e:
        print(f"Ошибка загрузки в MinIO: {e}")
        return False


def delete_image(image_name):
    """Удалить изображение из MinIO"""
    try:
        client = get_minio_client()
        client.remove_object(settings.MINIO_BUCKET_NAME, image_name)
        return True
    except S3Error as e:
        print(f"Ошибка удаления из MinIO: {e}")
        return False


def get_image_url(image_name):
    """Получить URL изображения"""
    return f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{image_name}"
